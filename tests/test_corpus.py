import csv
import json
import re

from policylab import paths

REQUIRED = ["document_number", "title", "agency", "publication_date", "url", "access_date"]


def manifest():
    with open(paths.MANIFEST, newline="") as f:
        return list(csv.DictReader(f))


def test_manifest_has_required_provenance_fields():
    rows = manifest()
    assert 40 <= len(rows) <= 80
    for r in rows:
        for k in REQUIRED:
            assert r[k], f"{r['document_number']} missing {k}"
        assert r["url"].startswith("https://www.federalregister.gov/documents/")
        assert r["full_text_url"].startswith("https://www.govinfo.gov/content/pkg/FR-")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["access_date"])
        assert int(r["n_chunks"]) > 0


def test_every_query_returned_documents_and_found_curated_docs():
    log = json.loads(paths.QUERY_LOG.read_text())
    assert log, "query log is empty"
    for q in log:
        assert q["count"] > 0, q["topic"]
        assert q["curated_found_by_query"] == q["curated"], q["topic"]


def test_snapshot_matches_manifest(corpus):
    assert set(corpus.documents) == {r["document_number"] for r in manifest()}
    assert {c["doc_number"] for c in corpus.chunks} == set(corpus.documents)


def test_chunk_ids_unique_and_well_formed(corpus):
    ids = [c["chunk_id"] for c in corpus.chunks]
    assert len(ids) == len(set(ids))
    pat = re.compile(r"^[A-Z0-9-]+:p\d{4}-\d{4}$")
    for c in corpus.chunks:
        assert pat.match(c["chunk_id"]), c["chunk_id"]
        assert c["para_start"] <= c["para_end"]
        assert c["text"].strip()


def test_snapshot_is_small():
    size = sum(p.stat().st_size for p in paths.SNAPSHOT.iterdir())
    assert size < 10 * 1024 * 1024
