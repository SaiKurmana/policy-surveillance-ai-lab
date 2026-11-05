"""Small text helpers shared by the verifier and the offline baseline."""

from __future__ import annotations

import re

from .retrieval import tokenize

_SENT = re.compile(r"(?<=[.!?”])\s+(?=[A-Z“(\[])")
_NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
_WS = re.compile(r"\s+")


def sentences(text: str) -> list[str]:
    out = []
    for para in text.split("\n\n"):
        for s in _SENT.split(para.strip()):
            s = s.strip()
            if s:
                out.append(s)
    return out


def content_tokens(text: str) -> set[str]:
    return set(tokenize(text))


def numbers(text: str) -> set[str]:
    """Numbers as written, without thousands separators ("1,500" -> "1500")."""
    return {n.replace(",", "") for n in _NUM.findall(text)}


def normalize(text: str) -> str:
    t = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return _WS.sub(" ", t).strip().lower()


def quote_in(quote: str, passage: str) -> bool:
    q = normalize(quote).strip(" .\"'")
    return bool(q) and q in normalize(passage)


def overlap(claim: str, passage: str) -> float:
    """Share of the claim's content words that appear in the passage."""
    c = content_tokens(claim)
    if not c:
        return 0.0
    return len(c & content_tokens(passage)) / len(c)
