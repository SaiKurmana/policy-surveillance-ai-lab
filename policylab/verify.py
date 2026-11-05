"""Citation verifier for grounded answers and AI codes.

The verifier is deliberately simple and transparent (lexical, no model):

* every answer sentence must cite at least one chunk ID;
* every cited chunk ID must be one of the passages the model was given;
* a citation "supports" a sentence when most of the sentence's content words
  appear in the cited chunk AND every number in the sentence appears there;
* a coding quote must appear verbatim (whitespace/quote-normalized) in its chunk.

Lexical checks catch fabricated citations, wrong-passage citations, and changed
numbers. They cannot catch a claim that reuses the passage's words but reverses
its meaning; that is why human review remains required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .schemas import ABSENCE_VALUES, CodedVariable, GroundedAnswer
from .textutil import numbers, overlap, quote_in

SUPPORT_THRESHOLD = 0.6


@dataclass
class CitationCheck:
    chunk_id: str
    valid_id: bool
    overlap: float
    numbers_ok: bool
    supports: bool


@dataclass
class SentenceCheck:
    text: str
    status: str  # supported | unsupported | uncited | invalid_citation
    citations: list[CitationCheck] = field(default_factory=list)


@dataclass
class AnswerVerification:
    sentences: list[SentenceCheck]
    insufficient_evidence: bool

    @property
    def n_citations(self) -> int:
        return sum(len(s.citations) for s in self.sentences)

    @property
    def citation_precision(self) -> float | None:
        """Share of citations whose chunk supports the sentence that cites it."""
        n = self.n_citations
        if n == 0:
            return None
        return sum(c.supports for s in self.sentences for c in s.citations) / n

    @property
    def supported_sentence_rate(self) -> float | None:
        if not self.sentences:
            return None
        return sum(s.status == "supported" for s in self.sentences) / len(self.sentences)

    @property
    def flagged(self) -> list[SentenceCheck]:
        return [s for s in self.sentences if s.status != "supported"]

    def to_dict(self) -> dict:
        return {
            "insufficient_evidence": self.insufficient_evidence,
            "citation_precision": self.citation_precision,
            "supported_sentence_rate": self.supported_sentence_rate,
            "sentences": [asdict(s) for s in self.sentences],
        }


def check_citation(sentence: str, chunk_id: str, passages: dict[str, str]) -> CitationCheck:
    text = passages.get(chunk_id)
    if text is None:
        return CitationCheck(chunk_id, False, 0.0, False, False)
    ov = overlap(sentence, text)
    nums_ok = numbers(sentence) <= numbers(text)
    return CitationCheck(chunk_id, True, round(ov, 3), nums_ok, ov >= SUPPORT_THRESHOLD and nums_ok)


def verify_answer(answer: GroundedAnswer, passages: dict[str, str]) -> AnswerVerification:
    """passages: chunk_id -> text for exactly the chunks the model was shown."""
    checks = []
    for s in answer.sentences:
        if not s.citations:
            checks.append(SentenceCheck(s.text, "uncited"))
            continue
        cc = [check_citation(s.text, cid, passages) for cid in s.citations]
        if not any(c.valid_id for c in cc):
            status = "invalid_citation"
        elif any(c.supports for c in cc):
            status = "supported"
        else:
            status = "unsupported"
        checks.append(SentenceCheck(s.text, status, cc))
    return AnswerVerification(checks, answer.insufficient_evidence)


def check_quote(code: CodedVariable, passages: dict[str, str]) -> str:
    """exact | not_found | invalid_chunk | absent_ok | abstained"""
    if code.status == "insufficient_evidence":
        return "abstained"
    if not code.supporting_quote and set(code.values) <= ABSENCE_VALUES:
        return "absent_ok"
    if code.chunk_id not in passages:
        return "invalid_chunk"
    return "exact" if quote_in(code.supporting_quote, passages[code.chunk_id]) else "not_found"
