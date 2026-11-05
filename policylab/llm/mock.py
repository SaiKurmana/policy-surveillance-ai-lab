"""Deterministic offline baseline ("mock LLM").

It does not read prompts. It answers questions by extracting the passage
sentences that best overlap the question, and codes documents by counting
codebook cue phrases. It exists so that (1) the app works with no API key,
(2) tests and CI never need a key, and (3) evaluation has a transparent
baseline that a real model must beat. Its outputs are never presented as AI
model results.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from ..codebook import NOT_STATED, Codebook, Variable
from ..schemas import AnswerSentence, CodedVariable, DocumentCoding, GroundedAnswer
from ..textutil import content_tokens, sentences
from .base import LLMResponse, T, Task

_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r" (\d{1,2}), (\d{4})"
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        1,
    )
}


class MockProvider:
    name = "offline-baseline"
    model = "extractive-keyword-baseline-v1"
    is_live_llm = False

    def structured(
        self, *, system: str, user: str, output_model: type[T], task: Task
    ) -> LLMResponse:
        if task.kind == "qa":
            parsed = self._qa(task.payload["question"], task.payload["chunks"])
        elif task.kind == "coding":
            parsed = self._code(
                task.payload["doc_number"], task.payload["chunks"], task.payload["codebook"]
            )
        else:
            raise ValueError(f"unknown task kind {task.kind}")
        if not isinstance(parsed, output_model):
            raise TypeError(
                f"baseline produced {type(parsed).__name__}, expected {output_model.__name__}"
            )
        return LLMResponse(
            parsed=parsed,
            raw_text=parsed.model_dump_json(),
            provider=self.name,
            model=self.model,
            served_model=self.model,
            stop_reason="end_turn",
        )

    # ---- Q&A: extractive ---------------------------------------------------
    def _qa(self, question: str, chunks: list[dict], top: int = 3) -> GroundedAnswer:
        q = content_tokens(question)
        scored = []
        for c in chunks:
            for s in sentences(c["text"]):
                n = len(s.split())
                if n < 6 or n > 80 or s.startswith("[GRAPHIC]") or s.endswith("?"):
                    continue
                hits = len(q & content_tokens(s))
                if hits >= 2:
                    scored.append((hits / max(len(q), 1), s, c["chunk_id"]))
        scored.sort(key=lambda x: -x[0])
        picked, seen = [], set()
        for score, s, cid in scored:
            if score < 0.5 or s in seen:
                continue
            seen.add(s)
            picked.append(AnswerSentence(text=s, citations=[cid]))
            if len(picked) == top:
                break
        if not picked:
            return GroundedAnswer(
                insufficient_evidence=True,
                sentences=[],
                missing_information="No passage sentence shares enough key terms with the question.",
            )
        return GroundedAnswer(insufficient_evidence=False, sentences=picked, missing_information="")

    # ---- coding: cue counting ----------------------------------------------
    def _code(self, doc_number: str, chunks: list[dict], codebook: Codebook) -> DocumentCoding:
        codes = []
        stage = None
        for var in codebook.variables:
            if var.id == "effective_date":
                code = self._effective_date(chunks)
            elif var.id == "regulatory_stage":
                code = self._stage(var, chunks)
                stage = code.values[0] if code.values else None
            elif var.id == "legal_force":
                code = self._legal_force(var, chunks, stage)
            else:
                code = self._cue_code(var, chunks)
            codes.append(code)
        return DocumentCoding(doc_number=doc_number, codes=codes)

    @staticmethod
    def _hits(cue: str, chunks: list[dict]) -> list[tuple[str, str]]:
        pat = re.compile(r"\b" + re.escape(cue.lower()) + r"\b")
        out = []
        for c in chunks:
            for s in sentences(c["text"]):
                if pat.search(s.lower()):
                    out.append((c["chunk_id"], s))
        return out

    def _value_hits(self, var: Variable, chunks: list[dict]) -> dict[str, list[tuple[str, str]]]:
        return {
            v: [h for cue in cues for h in self._hits(cue, chunks)] for v, cues in var.cues.items()
        }

    @staticmethod
    def _quote(s: str) -> str:
        words = s.split()
        return " ".join(words[:40])

    def _cue_code(self, var: Variable, chunks: list[dict]) -> CodedVariable:
        hits = self._value_hits(var, chunks)
        counts = {v: len(h) for v, h in hits.items()}
        total = sum(counts.values())
        if var.type == "single" and set(var.values) == {"yes", "no"}:
            yes = hits.get("yes", [])
            if len(yes) >= 3:
                cid, s = yes[0]
                return CodedVariable(
                    variable=var.id,
                    status="coded",
                    values=["yes"],
                    supporting_quote=self._quote(s),
                    chunk_id=cid,
                    confidence=min(0.9, 0.4 + 0.05 * len(yes)),
                    rationale=f"{len(yes)} sentences contain cue phrases for 'yes'.",
                )
            return CodedVariable(
                variable=var.id,
                status="coded",
                values=["no"],
                supporting_quote="",
                chunk_id="",
                confidence=0.4,
                rationale="Fewer than 3 cue-phrase matches; coded 'no' by absence.",
            )
        if total == 0:
            if "none" in var.values:
                return CodedVariable(
                    variable=var.id,
                    status="coded",
                    values=["none"],
                    supporting_quote="",
                    chunk_id="",
                    confidence=0.4,
                    rationale="No cue phrases found.",
                )
            return CodedVariable(
                variable=var.id,
                status="insufficient_evidence",
                values=[],
                supporting_quote="",
                chunk_id="",
                confidence=0.0,
                rationale="No cue phrases found in the passages.",
            )
        ranked = sorted(counts.items(), key=lambda x: -x[1])
        if var.type == "single":
            top, n = ranked[0]
            values = [top]
            if var.id == "policy_domain" and len(ranked) > 1:
                second, n2 = ranked[1]
                if (
                    {top, second} == {"nutrition", "physical_activity"}
                    and n2 >= 0.5 * n
                    and n2 >= 5
                ):
                    values = ["multiple"]
        else:
            threshold = max(2, int(0.1 * ranked[0][1]))
            values = [v for v, n in ranked if n >= threshold]
            if not values:
                return CodedVariable(
                    variable=var.id,
                    status="insufficient_evidence",
                    values=[],
                    supporting_quote="",
                    chunk_id="",
                    confidence=0.0,
                    rationale="Cue phrases too sparse to code.",
                )
        cid, s = hits[ranked[0][0]][0]
        conf = round(min(0.85, 0.3 + ranked[0][1] / (total + 5)), 2)
        return CodedVariable(
            variable=var.id,
            status="coded",
            values=values,
            supporting_quote=self._quote(s),
            chunk_id=cid,
            confidence=conf,
            rationale="Cue-phrase counts: " + json.dumps(dict(ranked[:5])),
        )

    def _stage(self, var: Variable, chunks: list[dict]) -> CodedVariable:
        for c in chunks[:12]:
            for s in sentences(c["text"]):
                if s.startswith("ACTION:"):
                    a = s.lower()
                    if any(
                        k in a
                        for k in (
                            "correction",
                            "technical amendment",
                            "extension of comment",
                            "delay",
                            "correcting",
                        )
                    ):
                        v = "correction_or_technical"
                    elif "interim" in a or "direct final" in a:
                        v = "interim_or_direct_final"
                    elif "proposed rule" in a:
                        v = "proposed_rule"
                    elif "final rule" in a:
                        v = "final_rule"
                    elif "availability" in a or "guidance" in a:
                        v = "guidance_availability"
                    elif "funding" in a:
                        v = "funding_notice"
                    elif "information collection" in a or "comment request" in a and "omb" in a:
                        v = "information_collection"
                    elif any(
                        k in a
                        for k in ("comment", "meeting", "nomination", "request for information")
                    ):
                        v = "meeting_or_comment_request"
                    else:
                        v = "other"
                    return CodedVariable(
                        variable=var.id,
                        status="coded",
                        values=[v],
                        supporting_quote=self._quote(s),
                        chunk_id=c["chunk_id"],
                        confidence=0.8,
                        rationale="Mapped from the ACTION line.",
                    )
        for c in chunks[:6]:
            low = c["text"].lower()
            if (
                "presidential documents" in low
                or "by the president" in low
                or "executive order" in low
            ):
                s = next(
                    (x for x in sentences(c["text"]) if "President" in x), sentences(c["text"])[0]
                )
                return CodedVariable(
                    variable=var.id,
                    status="coded",
                    values=["presidential_document"],
                    supporting_quote=self._quote(s),
                    chunk_id=c["chunk_id"],
                    confidence=0.6,
                    rationale="Presidential document markers.",
                )
        return CodedVariable(
            variable=var.id,
            status="insufficient_evidence",
            values=[],
            supporting_quote="",
            chunk_id="",
            confidence=0.0,
            rationale="No ACTION line found.",
        )

    def _legal_force(self, var: Variable, chunks: list[dict], stage: str | None) -> CodedVariable:
        hits = self._value_hits(var, chunks)
        if stage in (
            "information_collection",
            "meeting_or_comment_request",
            "presidential_document",
            "funding_notice",
            "correction_or_technical",
        ):
            v = "not_applicable"
        elif stage == "guidance_availability" or len(hits.get("voluntary", [])) > len(
            hits.get("mandatory", [])
        ):
            v = "voluntary"
        elif stage in ("final_rule", "proposed_rule", "interim_or_direct_final"):
            v = "mandatory"
        else:
            v = "not_applicable"
        src = hits.get("voluntary" if v == "voluntary" else "mandatory") or []
        cid, s = src[0] if src else ("", "")
        return CodedVariable(
            variable=var.id,
            status="coded",
            values=[v],
            supporting_quote=self._quote(s),
            chunk_id=cid,
            confidence=0.5,
            rationale=f"Derived from regulatory stage ({stage}) and cue counts.",
        )

    def _effective_date(self, chunks: list[dict]) -> CodedVariable:
        for c in chunks[:15]:
            for s in sentences(c["text"]):
                if "effective" in s.lower() and (
                    "DATES" in s or "rule is effective" in s or "effective date" in s.lower()
                ):
                    m = _DATE.search(s)
                    if m:
                        d = dt.date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))
                        return CodedVariable(
                            variable="effective_date",
                            status="coded",
                            values=[d.isoformat()],
                            supporting_quote=self._quote(s),
                            chunk_id=c["chunk_id"],
                            confidence=0.75,
                            rationale="First dated sentence mentioning 'effective'.",
                        )
        return CodedVariable(
            variable="effective_date",
            status="coded",
            values=[NOT_STATED],
            supporting_quote="",
            chunk_id="",
            confidence=0.5,
            rationale="No effective-date sentence found.",
        )
