"""Pydantic models for every structured LLM output.

The same models produce the JSON schema sent to the model (structured outputs)
and validate whatever comes back, so malformed output never reaches a reviewer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .codebook import Codebook

# Values that can be justified by the *absence* of evidence; these may be
# coded without a quote. Every other coded value needs a quote + chunk ID.
ABSENCE_VALUES = {"no", "none", "not_stated", "not_applicable"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- grounded Q&A -----------------------------------------------------------
class AnswerSentence(_Strict):
    text: str = Field(description="One sentence of the answer.")
    citations: list[str] = Field(
        description="Chunk IDs (e.g. '2024-08098:p0012-0015') that directly support this sentence."
    )


class GroundedAnswer(_Strict):
    insufficient_evidence: bool = Field(
        description="True if the provided passages do not contain enough information to answer."
    )
    sentences: list[AnswerSentence] = Field(
        description="The answer, one sentence per item. Empty if insufficient_evidence is true."
    )
    missing_information: str = Field(
        description="If evidence is insufficient or partial, what is missing. Otherwise empty string."
    )


# ---- policy coding -----------------------------------------------------------
class CodedVariable(_Strict):
    variable: str = Field(description="Codebook variable id.")
    status: Literal["coded", "insufficient_evidence"]
    values: list[str] = Field(
        description="Allowed value ids. One item for single/date variables. Empty if insufficient_evidence."
    )
    supporting_quote: str = Field(
        description="Exact quote copied from the cited chunk. Empty if insufficient_evidence."
    )
    chunk_id: str = Field(
        description="Chunk ID containing the quote. Empty if insufficient_evidence."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Self-reported confidence 0-1.")
    rationale: str = Field(description="One or two sentences explaining the code.")


class DocumentCoding(_Strict):
    doc_number: str
    codes: list[CodedVariable]

    def validate_against(self, codebook: Codebook) -> list[str]:
        """Codebook-level checks pydantic alone cannot express."""
        problems = []
        seen = set()
        for c in self.codes:
            if c.variable not in codebook.ids:
                problems.append(f"unknown variable {c.variable!r}")
                continue
            if c.variable in seen:
                problems.append(f"duplicate variable {c.variable!r}")
            seen.add(c.variable)
            if c.status == "coded":
                problems += codebook.get(c.variable).validate_values(c.values)
                absence_only = set(c.values) <= ABSENCE_VALUES
                if not absence_only and (not c.chunk_id or not c.supporting_quote):
                    problems.append(f"{c.variable}: coded without quote and chunk_id")
        missing = set(codebook.ids) - seen
        if missing:
            problems.append(f"missing variables: {sorted(missing)}")
        return problems


class CodingRequestMeta(_Strict):
    """Not sent to the model; recorded for the audit trail."""

    provider: str
    model: str
    prompt_version: str
    prompt_sha256: str
    codebook_version: str

    @model_validator(mode="after")
    def _nonempty(self) -> CodingRequestMeta:
        if not self.model:
            raise ValueError("model must be recorded")
        return self
