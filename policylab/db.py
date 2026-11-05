"""DuckDB storage: AI coding runs, AI codes, and the human review audit trail.

Tables are append-only. A review never overwrites an AI code; it adds a row to
``review_decisions`` that records who decided what, when, why, and which model
and prompt version produced the code being reviewed.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

import duckdb

from . import paths
from .coding import CodingRun

SCHEMA = """
CREATE TABLE IF NOT EXISTS coding_runs (
    run_id VARCHAR PRIMARY KEY,
    doc_number VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    served_model VARCHAR,
    is_live_llm BOOLEAN NOT NULL,
    prompt_version VARCHAR NOT NULL,
    prompt_sha VARCHAR NOT NULL,
    codebook_version VARCHAR NOT NULL,
    chunk_ids JSON,
    problems JSON,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_codes (
    code_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    doc_number VARCHAR NOT NULL,
    variable VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    ai_values JSON,
    supporting_quote VARCHAR,
    chunk_id VARCHAR,
    confidence DOUBLE,
    rationale VARCHAR,
    quote_check VARCHAR
);
CREATE TABLE IF NOT EXISTS review_decisions (
    decision_id VARCHAR PRIMARY KEY,
    code_id VARCHAR NOT NULL,
    run_id VARCHAR NOT NULL,
    doc_number VARCHAR NOT NULL,
    variable VARCHAR NOT NULL,
    decision VARCHAR NOT NULL CHECK (decision IN ('accept', 'edit', 'reject')),
    final_values JSON,
    reason VARCHAR,
    reviewer_id VARCHAR NOT NULL,
    decided_at TIMESTAMP NOT NULL,
    seconds_spent DOUBLE,
    model VARCHAR NOT NULL,
    served_model VARCHAR,
    prompt_version VARCHAR NOT NULL,
    codebook_version VARCHAR NOT NULL
);
"""


def connect(path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    path = str(path or paths.DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path)
    con.execute(SCHEMA)
    return con


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def save_run(con: duckdb.DuckDBPyConnection, run: CodingRun) -> None:
    con.execute(
        "INSERT INTO coding_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [run.run_id, run.doc_number, run.provider, run.model, run.served_model, run.is_live_llm,
         run.prompt_version, run.prompt_sha, run.codebook_version, json.dumps(run.chunk_ids),
         json.dumps(run.problems), dt.datetime.fromisoformat(run.created_at).replace(tzinfo=None)],
    )
    for c in run.coding.codes:
        con.execute(
            "INSERT INTO ai_codes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [f"{run.run_id}-{c.variable}", run.run_id, run.doc_number, c.variable, c.status,
             json.dumps(c.values), c.supporting_quote, c.chunk_id, c.confidence, c.rationale,
             run.quote_checks.get(c.variable)],
        )


def record_decision(
    con: duckdb.DuckDBPyConnection,
    code_id: str,
    decision: str,
    reviewer_id: str,
    reason: str = "",
    final_values: list[str] | None = None,
    seconds_spent: float | None = None,
) -> str:
    if decision not in ("accept", "edit", "reject"):
        raise ValueError("decision must be accept, edit, or reject")
    if not reviewer_id.strip():
        raise ValueError("reviewer_id is required for the audit trail")
    if decision in ("edit", "reject") and not reason.strip():
        raise ValueError("a reason is required when editing or rejecting")
    row = con.execute(
        """SELECT a.run_id, a.doc_number, a.variable, a.ai_values, r.model, r.served_model,
                  r.prompt_version, r.codebook_version
           FROM ai_codes a JOIN coding_runs r USING (run_id) WHERE a.code_id = ?""",
        [code_id],
    ).fetchone()
    if row is None:
        raise KeyError(code_id)
    run_id, doc, var, ai_values, model, served, pv, cbv = row
    if decision == "accept":
        final = json.loads(ai_values)
    elif decision == "reject":
        final = []
    else:
        if not final_values:
            raise ValueError("edited decisions need final_values")
        from .codebook import default_codebook

        problems = default_codebook().get(var).validate_values(final_values)
        if problems:
            raise ValueError("; ".join(problems))
        final = final_values
    decision_id = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO review_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [decision_id, code_id, run_id, doc, var, decision, json.dumps(final), reason,
         reviewer_id.strip(), _now(), seconds_spent, model, served, pv, cbv],
    )
    return decision_id


def review_queue(con: duckdb.DuckDBPyConnection, doc_number: str | None = None):
    """AI codes without any review decision yet, as a DataFrame."""
    q = """
    SELECT a.*, r.model, r.provider, r.is_live_llm, r.prompt_version, r.created_at
    FROM ai_codes a JOIN coding_runs r USING (run_id)
    WHERE a.code_id NOT IN (SELECT code_id FROM review_decisions)
    """
    params: list = []
    if doc_number:
        q += " AND a.doc_number = ?"
        params.append(doc_number)
    q += " ORDER BY r.created_at, a.doc_number, a.code_id"
    return con.execute(q, params).df()


def audit_trail(con: duckdb.DuckDBPyConnection):
    return con.execute(
        "SELECT * FROM review_decisions ORDER BY decided_at DESC"
    ).df()


def review_summary(con: duckdb.DuckDBPyConnection):
    return con.execute(
        """SELECT variable, decision, count(*) AS n FROM review_decisions
           GROUP BY variable, decision ORDER BY variable, decision"""
    ).df()
