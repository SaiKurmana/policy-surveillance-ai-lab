from policylab.retrieval import BM25, Filters, HashingEmbedder, HybridRetriever, tokenize


def test_tokenize_folds_plurals_and_drops_stopwords():
    assert tokenize("The Standards for policies") == ["standard", "policy"]


def test_bm25_ranks_matching_text_first():
    bm = BM25(["apples and pears", "sodium limits for school lunch", "bicycle lanes"])
    s = bm.scores("school sodium")
    assert s.argmax() == 1


def test_search_finds_known_passage(bm25):
    res = bm25.search("breakfast cereals 6 grams added sugars per dry ounce", k=10)
    assert any("6 grams of added sugars per dry ounce" in r.chunk["text"] for r in res)


def test_filters_restrict_results(bm25):
    res = bm25.search("calories", k=20, filters=Filters(doc_numbers=["2014-27834"]))
    assert res and {r.chunk["doc_number"] for r in res} == {"2014-27834"}
    res = bm25.search("milk", k=20, filters=Filters(agencies=["Food and Drug Administration"]))
    assert all(r.document["agency"] == "Food and Drug Administration" for r in res)
    res = bm25.search("milk", k=20, filters=Filters(date_from="2026-01-01"))
    assert all(r.document["publication_date"] >= "2026-01-01" for r in res)


def test_hybrid_path_runs_without_model(corpus):
    r = HybridRetriever(corpus, embedder=HashingEmbedder())
    assert r.mode == "hybrid"
    res = r.search("WIC food packages fruit and vegetable", k=5)
    assert len(res) == 5
    assert any(x.dense_rank is not None for x in res)


def test_empty_query_returns_nothing(bm25):
    assert bm25.search("   ") == []
