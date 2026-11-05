"""Load the committed corpus snapshot (documents + chunks)."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import paths


@dataclass
class Corpus:
    documents: dict[str, dict]
    chunks: list[dict]
    by_id: dict[str, dict] = field(init=False)

    def __post_init__(self) -> None:
        self.by_id = {c["chunk_id"]: c for c in self.chunks}

    def chunks_for(self, doc_number: str) -> list[dict]:
        return [c for c in self.chunks if c["doc_number"] == doc_number]

    def doc_for_chunk(self, chunk_id: str) -> dict | None:
        c = self.by_id.get(chunk_id)
        return self.documents.get(c["doc_number"]) if c else None

    @property
    def agencies(self) -> list[str]:
        return sorted({d["agency"] for d in self.documents.values()})

    @property
    def topics(self) -> list[str]:
        return sorted({t for d in self.documents.values() for t in d["topics"]})


def load_corpus(documents: Path | None = None, chunks: Path | None = None) -> Corpus:
    documents = documents or paths.DOCUMENTS
    chunks = chunks or paths.CHUNKS
    docs = {}
    with open(documents, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            docs[d["document_number"]] = d
    with gzip.open(chunks, "rt", encoding="utf-8") as f:
        ch = [json.loads(line) for line in f]
    return Corpus(docs, ch)


@lru_cache(maxsize=1)
def default_corpus() -> Corpus:
    return load_corpus()
