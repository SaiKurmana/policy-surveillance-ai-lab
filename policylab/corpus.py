"""Build the public-domain corpus: Federal Register metadata + GovInfo full text.

Run with ``make corpus`` (or ``python -m policylab.corpus``). Outputs:

* data/corpus_manifest.csv   - one row per document with provenance + access date
* data/corpus_queries.json   - every discovery query, its hit count, run date
* data/snapshot/documents.jsonl - document metadata used by the app
* data/snapshot/chunks.jsonl.gz - citable chunks (committed; app works offline)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import sys
from pathlib import Path

import yaml

from . import paths
from .chunking import CHUNKER_VERSION, chunk_document
from .fr_client import FederalRegisterClient

MANIFEST_FIELDS = [
    "document_number",
    "title",
    "agency",
    "agencies_all",
    "document_type",
    "publication_date",
    "effective_on",
    "citation",
    "page_length",
    "url",
    "pdf_url",
    "full_text_url",
    "access_date",
    "topics",
    "found_by_query",
    "n_paragraphs",
    "n_chunks",
    "text_sha256",
    "chunker_version",
]


def load_topics(path: Path = paths.CORPUS_CONFIG) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)["topics"]


def _primary_agency(agencies: list[dict]) -> str:
    """Most specific agency (a sub-agency if present, e.g. FNS rather than USDA)."""
    names = [a.get("name") or a.get("raw_name") or "" for a in agencies]
    children = [a for a in agencies if a.get("parent_id")]
    if children:
        return children[0].get("name") or children[0].get("raw_name") or names[0]
    return names[0] if names else "Unknown"


def build(refresh: bool = False, only: list[str] | None = None) -> dict:
    topics = load_topics()
    client = FederalRegisterClient()
    today = dt.date.today().isoformat()
    paths.RAW.mkdir(parents=True, exist_ok=True)
    paths.SNAPSHOT.mkdir(parents=True, exist_ok=True)

    # 1. discovery queries ---------------------------------------------------
    query_log = []
    doc_topics: dict[str, list[str]] = {}
    found: dict[str, set[str]] = {}
    for key, t in topics.items():
        res = client.search(t["query"], t.get("types"))
        if res["count"] == 0:
            raise SystemExit(f"Topic {key!r}: query returned no documents: {t['query']}")
        hits = set(res["document_numbers"])
        query_log.append(
            {
                "topic": key,
                "label": t["label"],
                "query": t["query"],
                "types": t.get("types"),
                "count": res["count"],
                "curated": len(t["documents"]),
                "curated_found_by_query": sum(d in hits for d in t["documents"]),
                "run_date": today,
            }
        )
        print(f"[query] {key}: {res['count']} hits; curated {len(t['documents'])}", file=sys.stderr)
        for d in t["documents"]:
            doc_topics.setdefault(d, []).append(key)
            if d in hits:
                found.setdefault(d, set()).add(key)

    # 2. fetch + chunk every curated document -------------------------------
    numbers = sorted(doc_topics)
    if only:
        numbers = [n for n in numbers if n in only]
    rows, docs, all_chunks = [], [], []
    for n in numbers:
        meta_path = paths.RAW / f"{n}.json"
        html_path = paths.RAW / f"{n}.htm"
        if refresh or not meta_path.exists():
            meta = client.document(n)
            meta["_access_date"] = today
            meta_path.write_text(json.dumps(meta, indent=1))
        meta = json.loads(meta_path.read_text())
        if meta.get("document_number") != n:
            raise SystemExit(f"API returned a different document for {n}")
        if refresh or not html_path.exists():
            html_path.write_text(client.full_text_html(meta))
            meta["_text_access_date"] = today
            meta_path.write_text(json.dumps(meta, indent=1))
        raw_html = html_path.read_text()
        if n not in raw_html:
            raise SystemExit(f"GovInfo text for {n} does not mention its document number")
        paras, chunks = chunk_document(n, raw_html)
        text_hash = hashlib.sha256("\n\n".join(p.text for p in paras).encode()).hexdigest()
        agencies = meta.get("agencies") or []
        access = meta.get("_text_access_date") or meta.get("_access_date") or today
        row = {
            "document_number": n,
            "title": meta["title"],
            "agency": _primary_agency(agencies),
            "agencies_all": "; ".join(a.get("name") or a.get("raw_name") or "" for a in agencies),
            "document_type": meta.get("type"),
            "publication_date": meta.get("publication_date"),
            "effective_on": meta.get("effective_on") or "",
            "citation": meta.get("citation") or "",
            "page_length": meta.get("page_length") or "",
            "url": meta.get("html_url"),
            "pdf_url": meta.get("pdf_url") or "",
            "full_text_url": client.govinfo_url(meta),
            "access_date": access,
            "topics": ";".join(doc_topics[n]),
            "found_by_query": ";".join(sorted(found.get(n, set()))),
            "n_paragraphs": len(paras),
            "n_chunks": len(chunks),
            "text_sha256": text_hash,
            "chunker_version": CHUNKER_VERSION,
        }
        rows.append(row)
        docs.append(
            {
                **{
                    k: row[k]
                    for k in (
                        "document_number",
                        "title",
                        "agency",
                        "document_type",
                        "publication_date",
                        "effective_on",
                        "citation",
                        "url",
                        "full_text_url",
                        "access_date",
                    )
                },
                "topics": doc_topics[n],
                "agencies_all": row["agencies_all"].split("; "),
                "action": meta.get("action"),
                "abstract": meta.get("abstract"),
                "dates": meta.get("dates"),
                "comments_close_on": meta.get("comments_close_on"),
                "fr_topics": meta.get("topics") or [],
                "page_length": meta.get("page_length"),
            }
        )
        all_chunks.extend(c.to_dict() for c in chunks)
        print(f"[doc] {n}: {len(paras)} paragraphs -> {len(chunks)} chunks", file=sys.stderr)

    # 3. write outputs -------------------------------------------------------
    with open(paths.MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)
    paths.QUERY_LOG.write_text(json.dumps(query_log, indent=2) + "\n")
    with open(paths.DOCUMENTS, "w") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with gzip.open(paths.CHUNKS, "wt", encoding="utf-8", compresslevel=9) as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    summary = {"documents": len(rows), "chunks": len(all_chunks)}
    print(f"[done] {summary}", file=sys.stderr)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--only", nargs="*", help="limit to these document numbers")
    args = ap.parse_args()
    build(refresh=args.refresh, only=args.only)


if __name__ == "__main__":
    main()
