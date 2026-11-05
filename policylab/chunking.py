"""Turn GovInfo Federal Register HTML into paragraphs and stable, citable chunks.

Chunk IDs look like ``2024-08098:p0012-0015``: the document number plus the
first and last paragraph index (zero-based, after cleaning) covered by the chunk.
Given the same source text and the same CHUNKER_VERSION, IDs are reproducible,
so a citation can always be traced back to the exact passage.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass

CHUNKER_VERSION = "v1"
TARGET_WORDS = 220
MAX_WORDS = 360
MAX_PARAGRAPH_WORDS = 300  # longer paragraphs (often tables) are split

_PAGE = re.compile(r"\[\[Page (\d+)\]\]")
_PRE = re.compile(r"<pre>(.*?)</pre>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_RULE_LINE = re.compile(r"^-{10,}$")
_HEADING_START = re.compile(
    r"^(?:[IVXLC]+\.|[A-Z]\.|\d{1,2}\.|\(\d{1,2}\)|\([a-z]\)|Sec\.|§|PART\s+\d+|Subpart\s+[A-Z])\s"
)


@dataclass
class Paragraph:
    index: int
    text: str
    page: int | None
    is_heading: bool


@dataclass
class Chunk:
    chunk_id: str
    doc_number: str
    para_start: int
    para_end: int
    char_start: int
    char_end: int
    section: str
    fr_page: int | None
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def extract_pre_text(raw_html: str) -> str:
    """GovInfo FR HTML wraps the whole document in one <pre> block."""
    m = _PRE.search(raw_html)
    body = m.group(1) if m else raw_html
    body = _TAG.sub("", body)
    return html.unescape(body).replace("\r\n", "\n")


def _looks_like_table(lines: list[str]) -> bool:
    spaced = sum(1 for ln in lines if re.search(r"\S {3,}\S", ln) or ln.strip().startswith("|"))
    return len(lines) >= 3 and spaced / len(lines) > 0.5


def _is_heading(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 28:
        return False
    if len(words) > 16 and not re.match(r"^[IVXLC]+\.\s", text):
        return False
    if text.endswith((".", ",", ";")) and not _HEADING_START.match(text + " "):
        return False
    if text.isupper() and len(text) > 3:
        return True
    if text.endswith(":") and len(words) <= 6:
        return True
    return bool(_HEADING_START.match(text + " ")) and not text.endswith(".")


def _split_long(text: str, limit: int) -> list[str]:
    words = text.split(" ")
    if len(words) <= limit:
        return [text]
    # prefer sentence boundaries
    sentences = re.split(r"(?<=[.;])\s+(?=[A-Z(])", text)
    out, cur = [], []
    for s in sentences:
        if cur and len(" ".join(cur + [s]).split()) > limit:
            out.append(" ".join(cur))
            cur = []
        cur.append(s)
    if cur:
        out.append(" ".join(cur))
    # hard split anything still too long (e.g. tables without periods)
    final = []
    for piece in out:
        w = piece.split(" ")
        for i in range(0, len(w), limit):
            final.append(" ".join(w[i : i + limit]))
    return final


_PAGE_BREAK = re.compile(r"([^\n]*)\n[ \t]*\n[ \t]*(\[\[Page \d+\]\])[ \t]*\n[ \t]*\n([^\n]*)")


def _join_page_breaks(text: str) -> str:
    """Re-join paragraphs that the printed page layout split in two.

    GovInfo inserts ``[[Page N]]`` surrounded by blank lines, even mid-sentence.
    If the text before the marker does not end a sentence, or the text after it
    starts in lower case, the marker is kept inline so the paragraph stays whole.
    """

    def repl(m: re.Match) -> str:
        before, marker, after = m.group(1), m.group(2), m.group(3)
        ends_sentence = before.rstrip().endswith((".", ":", ";", "?", "!", ".\u201d", ".''"))
        starts_lower = after.lstrip()[:1].islower()
        if not ends_sentence or starts_lower:
            return f"{before}\n{marker}\n{after}"
        return m.group(0)

    return _PAGE_BREAK.sub(repl, text)


def paragraphs_from_text(text: str) -> list[Paragraph]:
    """Split GovInfo plain text into cleaned paragraphs, tracking FR page numbers."""
    text = _join_page_breaks(text)
    page: int | None = None
    blocks: list[tuple[list[str], int | None]] = []
    cur: list[str] = []
    cur_page: int | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        pm = _PAGE.fullmatch(stripped)
        if pm:
            page = int(pm.group(1))
            continue
        if not stripped or _RULE_LINE.match(stripped):
            if cur:
                blocks.append((cur, cur_page))
                cur = []
            continue
        if not cur:
            cur_page = page
        cur.append(line.rstrip())
    if cur:
        blocks.append((cur, cur_page))

    paras: list[Paragraph] = []
    for lines, pg in blocks:
        if _looks_like_table(lines):
            joined = " | ".join(re.sub(r"\s{2,}", "  ", ln.strip()) for ln in lines)
        else:
            joined = " ".join(ln.strip() for ln in lines)
        joined = _PAGE.sub(" ", joined)
        joined = re.sub(r"\s+", " ", joined).strip()
        # GovInfo uses TeX-style quotes; normalise so quotes match user text.
        joined = joined.replace("``", "“").replace("''", "”")
        if not joined:
            continue
        for piece in _split_long(joined, MAX_PARAGRAPH_WORDS):
            paras.append(Paragraph(len(paras), piece, pg, _is_heading(piece)))
    return paras


def chunk_paragraphs(doc_number: str, paras: list[Paragraph]) -> list[Chunk]:
    """Greedy paragraph packing; a heading always starts a new chunk."""
    chunks: list[Chunk] = []
    offsets, pos = [], 0
    for p in paras:
        offsets.append(pos)
        pos += len(p.text) + 2  # paragraphs joined with "\n\n"

    section = ""
    group: list[Paragraph] = []
    group_section = ""

    def flush() -> None:
        if not group:
            return
        first, last = group[0], group[-1]
        chunks.append(
            Chunk(
                chunk_id=f"{doc_number}:p{first.index:04d}-{last.index:04d}",
                doc_number=doc_number,
                para_start=first.index,
                para_end=last.index,
                char_start=offsets[first.index],
                char_end=offsets[last.index] + len(last.text),
                section=group_section,
                fr_page=first.page,
                text="\n\n".join(p.text for p in group),
            )
        )
        group.clear()

    words = 0
    for p in paras:
        n = len(p.text.split())
        if p.is_heading:
            # keep the heading with the text that follows it
            if group and not all(g.is_heading for g in group):
                flush()
                words = 0
            section = p.text[:120]
            if not group:
                group_section = section
            group.append(p)
            words += n
            continue
        if group and not all(g.is_heading for g in group) and (
            words + n > MAX_WORDS or words >= TARGET_WORDS
        ):
            flush()
            words = 0
        if not group:
            group_section = section
        group.append(p)
        words += n
    flush()
    return chunks


def chunk_document(doc_number: str, raw_html: str) -> tuple[list[Paragraph], list[Chunk]]:
    paras = paragraphs_from_text(extract_pre_text(raw_html))
    return paras, chunk_paragraphs(doc_number, paras)
