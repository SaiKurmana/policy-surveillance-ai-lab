"""AI-assisted policy coding of one document against the codebook."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from .codebook import Codebook
from .llm import LLMProvider, Task
from .qa import format_passages, load_prompt
from .retrieval import Filters, HybridRetriever
from .schemas import DocumentCoding
from .verify import check_quote

CODING_PROMPT_VERSION = "coding_v1"
HEAD_CHUNKS = 6  # header, SUMMARY, DATES, ACTION usually live here
PER_VARIABLE = 4
MAX_CHUNKS = 45


def select_chunks(doc_number: str, codebook: Codebook, retriever: HybridRetriever) -> list[dict]:
    """Evidence passages for coding: the document head plus the top passages for
    each variable's retrieval query. Long rules (150+ pages) do not fit a useful
    prompt, so we retrieve rather than send everything; the selected chunk IDs
    are stored with the run so reviewers see exactly what the model saw."""
    doc_chunks = retriever.corpus.chunks_for(doc_number)
    chosen = {c["chunk_id"]: c for c in doc_chunks[:HEAD_CHUNKS]}
    f = Filters(doc_numbers=[doc_number])
    for var in codebook.variables:
        for h in retriever.search(var.retrieval_query, k=PER_VARIABLE, filters=f):
            chosen.setdefault(h.chunk["chunk_id"], h.chunk)
            if len(chosen) >= MAX_CHUNKS:
                break
    order = {c["chunk_id"]: i for i, c in enumerate(doc_chunks)}
    return sorted(chosen.values(), key=lambda c: order[c["chunk_id"]])


@dataclass
class CodingRun:
    run_id: str
    doc_number: str
    coding: DocumentCoding
    problems: list[str]
    quote_checks: dict[str, str]
    chunk_ids: list[str]
    provider: str
    model: str
    served_model: str
    prompt_version: str
    prompt_sha: str
    codebook_version: str
    is_live_llm: bool
    created_at: str = field(
        default_factory=lambda: dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    )


def code_document(
    doc_number: str, codebook: Codebook, retriever: HybridRetriever, provider: LLMProvider
) -> CodingRun:
    chunks = select_chunks(doc_number, codebook, retriever)
    if not chunks:
        raise ValueError(f"No chunks found for document {doc_number}")
    template, sha = load_prompt(CODING_PROMPT_VERSION)
    system = template.replace("{codebook}", codebook.to_prompt())
    doc = retriever.corpus.documents[doc_number]
    user = (
        f"DOCUMENT {doc_number}: {doc['title']}\n"
        f"Agency: {doc['agency']}; published {doc['publication_date']}\n\n"
        f"PASSAGES:\n\n{format_passages(chunks, retriever.corpus.documents)}\n\n"
        f'Return the coding for document "{doc_number}".'
    )
    resp = provider.structured(
        system=system,
        user=user,
        output_model=DocumentCoding,
        task=Task("coding", {"doc_number": doc_number, "chunks": chunks, "codebook": codebook}),
    )
    coding: DocumentCoding = resp.parsed  # type: ignore[assignment]
    passages = {c["chunk_id"]: c["text"] for c in chunks}
    problems = coding.validate_against(codebook)
    if coding.doc_number != doc_number:
        problems.append(f"model coded {coding.doc_number!r}, expected {doc_number!r}")
        coding.doc_number = doc_number
    checks = {c.variable: check_quote(c, passages) for c in coding.codes}
    return CodingRun(
        run_id=uuid.uuid4().hex[:12],
        doc_number=doc_number,
        coding=coding,
        problems=problems,
        quote_checks=checks,
        chunk_ids=list(passages),
        provider=resp.provider,
        model=resp.model,
        served_model=resp.served_model,
        prompt_version=CODING_PROMPT_VERSION,
        prompt_sha=sha,
        codebook_version=codebook.version,
        is_live_llm=provider.is_live_llm,
    )
