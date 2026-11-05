"""Hybrid retrieval: BM25 (always available) + local sentence-transformer embeddings.

Scores are fused with Reciprocal Rank Fusion (RRF), which is robust to the very
different scales of BM25 and cosine similarity. If the embedding index has not
been built (``make index``) or sentence-transformers is not installed, search
falls back to BM25 only and reports ``mode="bm25"`` so the UI can say so.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from . import paths
from .store import Corpus

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RRF_K = 60

_STOP = set(
    ["a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "for", "from", "had", "has", "have", "if", "in", "into", "is", "it", "its", "may", "not", "of", "on", "or", "our", "such", "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "were", "which", "will", "with", "would", "we", "any", "all", "also", "other", "than", "under", "section", "sec"]
)
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def tokenize(text: str) -> list[str]:
    toks = _TOKEN.findall(text.lower())
    out = []
    for t in toks:
        if t in _STOP or len(t) < 2:
            continue
        # light plural folding: "standards" -> "standard", "policies" -> "policy"
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


class BM25:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(texts)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.doc_len = np.zeros(self.n, dtype=np.float32)
        for i, t in enumerate(texts):
            toks = tokenize(t)
            self.doc_len[i] = len(toks)
            for term, tf in Counter(toks).items():
                self.postings[term].append((i, tf))
        self.avgdl = float(self.doc_len.mean()) if self.n else 0.0
        self.idf = {
            term: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5))
            for term, p in self.postings.items()
        }

    def scores(self, query: str) -> np.ndarray:
        s = np.zeros(self.n, dtype=np.float32)
        norm = self.k1 * (1 - self.b + self.b * self.doc_len / max(self.avgdl, 1e-9))
        for term in set(tokenize(query)):
            post = self.postings.get(term)
            if not post:
                continue
            idx = np.fromiter((p[0] for p in post), dtype=np.int64)
            tf = np.fromiter((p[1] for p in post), dtype=np.float32)
            s[idx] += self.idf[term] * tf * (self.k1 + 1) / (tf + norm[idx])
        return s


class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.name = model_name
        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(
            texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(v, dtype=np.float32)


class HashingEmbedder:
    """Deterministic bag-of-words hashing embedder.

    Not semantic: used only in tests and CI so the hybrid code path is exercised
    without downloading a model.
    """

    name = "hashing-bow-256"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in tokenize(t):
                h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(norms, 1e-9)


def _chunk_ids_hash(chunks: list[dict]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c["chunk_id"].encode())
    return h.hexdigest()[:16]


def build_embedding_index(corpus: Corpus, embedder: Embedder | None = None) -> dict:
    """Embed every chunk and write data/index/ (gitignored)."""
    embedder = embedder or SentenceTransformerEmbedder()
    texts = [_embed_text(c, corpus) for c in corpus.chunks]
    vecs = embedder.encode(texts).astype(np.float16)
    paths.INDEX.mkdir(parents=True, exist_ok=True)
    np.save(paths.INDEX / "embeddings.npy", vecs)
    meta = {
        "model": embedder.name,
        "n_chunks": len(corpus.chunks),
        "chunk_ids_hash": _chunk_ids_hash(corpus.chunks),
        "dim": int(vecs.shape[1]),
    }
    (paths.INDEX / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def _embed_text(chunk: dict, corpus: Corpus) -> str:
    doc = corpus.documents.get(chunk["doc_number"], {})
    return f"{doc.get('title', '')}. {chunk.get('section', '')}. {chunk['text']}"


@dataclass
class SearchResult:
    chunk: dict
    document: dict
    score: float
    bm25_rank: int | None
    dense_rank: int | None


@dataclass
class Filters:
    agencies: list[str] | None = None
    topics: list[str] | None = None
    doc_numbers: list[str] | None = None
    date_from: str | None = None  # ISO yyyy-mm-dd
    date_to: str | None = None
    document_types: list[str] | None = None

    def mask(self, corpus: Corpus) -> np.ndarray:
        keep = np.ones(len(corpus.chunks), dtype=bool)
        for i, c in enumerate(corpus.chunks):
            d = corpus.documents[c["doc_number"]]
            if self.doc_numbers and c["doc_number"] not in self.doc_numbers or self.agencies and d["agency"] not in self.agencies or self.topics and not set(d["topics"]) & set(self.topics) or self.document_types and d["document_type"] not in self.document_types or self.date_from and d["publication_date"] < self.date_from or self.date_to and d["publication_date"] > self.date_to:
                keep[i] = False
        return keep


class HybridRetriever:
    def __init__(
        self,
        corpus: Corpus,
        embedder: Embedder | None = None,
        embeddings: np.ndarray | None = None,
    ):
        self.corpus = corpus
        self.bm25 = BM25([_embed_text(c, corpus) for c in corpus.chunks])
        self.embedder = embedder
        self.embeddings = embeddings
        if embedder is not None and embeddings is None:
            self.embeddings = embedder.encode([_embed_text(c, corpus) for c in corpus.chunks])

    @property
    def mode(self) -> str:
        return "hybrid" if self.embeddings is not None and self.embedder is not None else "bm25"

    @classmethod
    def from_disk(cls, corpus: Corpus, load_model: bool = True) -> HybridRetriever:
        """Use the prebuilt index when it matches the corpus; otherwise BM25 only."""
        meta_path = paths.INDEX / "meta.json"
        if load_model and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("chunk_ids_hash") == _chunk_ids_hash(corpus.chunks):
                try:
                    emb = SentenceTransformerEmbedder(meta["model"])
                except Exception:  # model or library unavailable -> BM25 only
                    emb = None
                if emb is not None:
                    vecs = np.load(paths.INDEX / "embeddings.npy").astype(np.float32)
                    return cls(corpus, emb, vecs)
        return cls(corpus)

    def search(
        self, query: str, k: int = 10, filters: Filters | None = None, pool: int = 100
    ) -> list[SearchResult]:
        if not query.strip():
            return []
        mask = (filters or Filters()).mask(self.corpus)
        if not mask.any():
            return []
        bm = self.bm25.scores(query)
        bm[~mask] = -np.inf
        bm_order = [i for i in np.argsort(-bm)[:pool] if np.isfinite(bm[i]) and bm[i] > 0]
        bm_rank = {int(i): r for r, i in enumerate(bm_order)}

        dense_rank: dict[int, int] = {}
        if self.mode == "hybrid":
            qv = self.embedder.encode([query])[0]
            sims = self.embeddings @ qv
            sims[~mask] = -np.inf
            dense_order = np.argsort(-sims)[:pool]
            dense_rank = {int(i): r for r, i in enumerate(dense_order) if np.isfinite(sims[i])}

        fused: dict[int, float] = defaultdict(float)
        for i, r in bm_rank.items():
            fused[i] += 1.0 / (RRF_K + r + 1)
        for i, r in dense_rank.items():
            fused[i] += 1.0 / (RRF_K + r + 1)
        top = sorted(fused.items(), key=lambda x: -x[1])[:k]
        out = []
        for i, s in top:
            c = self.corpus.chunks[i]
            out.append(
                SearchResult(
                    chunk=c,
                    document=self.corpus.documents[c["doc_number"]],
                    score=float(s),
                    bm25_rank=bm_rank.get(i),
                    dense_rank=dense_rank.get(i),
                )
            )
        return out


def main() -> None:
    """``make index``: build the local embedding index for hybrid search."""
    from .store import load_corpus

    corpus = load_corpus()
    meta = build_embedding_index(corpus)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
