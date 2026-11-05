"""Grounded question answering over user-selected documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import paths
from .llm import LLMProvider, Task
from .retrieval import Filters, HybridRetriever
from .schemas import GroundedAnswer
from .verify import AnswerVerification, verify_answer

QA_PROMPT_VERSION = "qa_v1"


def load_prompt(version: str) -> tuple[str, str]:
    text = (paths.PROMPTS / f"{version}.md").read_text()
    return text, hashlib.sha256(text.encode()).hexdigest()[:12]


def format_passages(chunks: list[dict], documents: dict[str, dict]) -> str:
    parts = []
    for c in chunks:
        d = documents.get(c["doc_number"], {})
        head = f"[{c['chunk_id']}] {d.get('title', '')} ({d.get('agency', '')}, {d.get('publication_date', '')})"
        if c.get("section"):
            head += f" - section: {c['section']}"
        parts.append(f"{head}\n{c['text']}")
    return "\n\n---\n\n".join(parts)


@dataclass
class QAResult:
    question: str
    answer: GroundedAnswer
    verification: AnswerVerification
    chunks: list[dict]
    provider: str
    model: str
    served_model: str
    prompt_version: str
    prompt_sha: str
    is_live_llm: bool


def ask(
    question: str,
    doc_numbers: list[str],
    retriever: HybridRetriever,
    provider: LLMProvider,
    k: int = 8,
) -> QAResult:
    """Answer ``question`` using only the top-k chunks from ``doc_numbers``."""
    if not doc_numbers:
        raise ValueError("Select at least one document to ground the answer.")
    hits = retriever.search(question, k=k, filters=Filters(doc_numbers=doc_numbers))
    chunks = [h.chunk for h in hits]
    system, sha = load_prompt(QA_PROMPT_VERSION)
    if not chunks:
        answer = GroundedAnswer(
            insufficient_evidence=True,
            sentences=[],
            missing_information="No passages in the selected documents matched the question.",
        )
        return QAResult(
            question,
            answer,
            verify_answer(answer, {}),
            [],
            provider.name,
            provider.model,
            provider.model,
            QA_PROMPT_VERSION,
            sha,
            provider.is_live_llm,
        )
    user = (
        f"PASSAGES:\n\n{format_passages(chunks, retriever.corpus.documents)}\n\n"
        f"QUESTION: {question}"
    )
    resp = provider.structured(
        system=system,
        user=user,
        output_model=GroundedAnswer,
        task=Task("qa", {"question": question, "chunks": chunks}),
    )
    answer: GroundedAnswer = resp.parsed  # type: ignore[assignment]
    verification = verify_answer(answer, {c["chunk_id"]: c["text"] for c in chunks})
    return QAResult(
        question,
        answer,
        verification,
        chunks,
        resp.provider,
        resp.model,
        resp.served_model,
        QA_PROMPT_VERSION,
        sha,
        provider.is_live_llm,
    )
