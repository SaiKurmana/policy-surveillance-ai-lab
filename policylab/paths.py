"""Central place for repository paths so scripts, app, and tests agree."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("POLICYLAB_ROOT", Path(__file__).resolve().parents[1]))

DATA = ROOT / "data"
RAW = DATA / "raw"  # gitignored download cache
SNAPSHOT = DATA / "snapshot"  # committed, offline-capable corpus
INDEX = DATA / "index"  # gitignored embedding index
DEMO_OUTPUTS = DATA / "demo_outputs"
MANIFEST = DATA / "corpus_manifest.csv"
QUERY_LOG = DATA / "corpus_queries.json"
DOCUMENTS = SNAPSHOT / "documents.jsonl"
CHUNKS = SNAPSHOT / "chunks.jsonl.gz"
DB_PATH = Path(os.environ.get("POLICYLAB_DB", DATA / "lab.duckdb"))

CORPUS_CONFIG = ROOT / "corpus" / "topics.yaml"
CODEBOOK = ROOT / "codebook" / "policy_codebook.yaml"
PROMPTS = Path(__file__).resolve().parent / "prompts"

EVAL = ROOT / "eval"
GOLD_CODES = EVAL / "gold" / "gold_codes.csv"
GOLD_TEMPLATE = EVAL / "gold" / "gold_codes_template.csv"
RETRIEVAL_PAIRS = EVAL / "gold" / "retrieval_pairs.yaml"
QA_QUESTIONS = EVAL / "gold" / "qa_questions.yaml"
EVAL_RESULTS_MD = EVAL / "results.md"
EVAL_RESULTS_JSON = EVAL / "results.json"
EVAL_CHARTS = EVAL / "charts"

SITE_SRC = ROOT / "site"
SITE_OUT = ROOT / "_site"
DOCS = ROOT / "docs"
