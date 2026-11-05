import math

import yaml

from policylab import paths
from policylab.evaluation import (
    cohen_kappa,
    gold_tier,
    jaccard,
    load_gold,
    multilabel_kappa,
    relevant_chunks,
)
from policylab.textutil import quote_in


def test_cohen_kappa_known_values():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    # Classic example: po = 0.7, pe = 0.5 -> 0.4
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert math.isclose(cohen_kappa(a, b), 0.4)
    assert cohen_kappa(["a", "a"], ["a", "a"]) == 1.0
    assert cohen_kappa([], []) is None


def test_jaccard_and_multilabel_kappa():
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard(set(), set()) == 1.0
    k = multilabel_kappa([{"a"}, {"b"}], [{"a"}, {"b"}], ["a", "b", "c"])
    assert k == 1.0


def test_gold_file_is_labeled_and_quotes_exist(corpus, codebook):
    rows = load_gold()
    assert len({r.doc_number for r in rows}) >= 20
    statuses = {r.status for r in rows}
    assert statuses <= {"draft_unverified", "verified", "todo"}
    for r in rows:
        if r.status == "draft_unverified":
            assert r.coder_id == "assistant-draft", "starter drafts must stay labeled"
        if not r.values:
            continue
        assert codebook.get(r.variable).validate_values(r.values) == [], (r.doc_number, r.variable)
        if r.quote:
            chunk = corpus.by_id.get(r.chunk_id)
            assert chunk is not None, (r.doc_number, r.variable, r.chunk_id)
            assert quote_in(r.quote, chunk["text"]), (r.doc_number, r.variable)


def test_gold_tier_prefers_verified_rows():
    rows = load_gold()
    tier, used = gold_tier(rows)
    if any(r.status == "verified" for r in rows):
        assert tier == "verified" and all(r.status == "verified" for r in used)
    else:
        assert tier == "draft_unverified"


def test_every_retrieval_pair_has_a_relevant_chunk(corpus):
    pairs = yaml.safe_load(paths.RETRIEVAL_PAIRS.read_text())["pairs"]
    assert len(pairs) >= 20
    for p in pairs:
        assert relevant_chunks(p, corpus), p["id"]


def test_qa_questions_reference_real_documents(corpus):
    qs = yaml.safe_load(paths.QA_QUESTIONS.read_text())["questions"]
    assert any(not q["answerable"] for q in qs)
    for q in qs:
        assert set(q["docs"]) <= set(corpus.documents), q["id"]
