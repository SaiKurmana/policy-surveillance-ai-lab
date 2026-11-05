from policylab.llm import MockProvider, get_provider
from policylab.qa import ask
from policylab.schemas import AnswerSentence, GroundedAnswer
from policylab.verify import verify_answer

PASSAGES = {
    "D:p0001-0001": "Breakfast cereals are limited to no more than 6 grams of added sugars per dry ounce.",
    "D:p0002-0002": "Schools must comply by school year 2025-2026.",
}


def _ans(*sents):
    return GroundedAnswer(
        insufficient_evidence=False,
        sentences=[AnswerSentence(text=t, citations=c) for t, c in sents],
        missing_information="",
    )


def test_verifier_accepts_supported_sentence():
    v = verify_answer(
        _ans(
            (
                "Breakfast cereals are limited to 6 grams of added sugars per dry ounce.",
                ["D:p0001-0001"],
            )
        ),
        PASSAGES,
    )
    assert v.sentences[0].status == "supported"
    assert v.citation_precision == 1.0


def test_verifier_flags_changed_number():
    v = verify_answer(
        _ans(
            (
                "Breakfast cereals are limited to 9 grams of added sugars per dry ounce.",
                ["D:p0001-0001"],
            )
        ),
        PASSAGES,
    )
    assert v.sentences[0].status == "unsupported"
    assert v.citation_precision == 0.0


def test_verifier_flags_fabricated_and_missing_citations():
    v = verify_answer(
        _ans(("Cereals are limited.", ["X:p9999-9999"]), ("No source here.", [])), PASSAGES
    )
    assert [s.status for s in v.sentences] == ["invalid_citation", "uncited"]
    assert len(v.flagged) == 2


def test_verifier_flags_wrong_passage():
    v = verify_answer(
        _ans(
            (
                "Breakfast cereals are limited to 6 grams of added sugars per dry ounce.",
                ["D:p0002-0002"],
            )
        ),
        PASSAGES,
    )
    assert v.sentences[0].status == "unsupported"


def test_default_provider_without_key_is_offline_baseline(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("POLICYLAB_PROVIDER", raising=False)
    p = get_provider()
    assert isinstance(p, MockProvider) and not p.is_live_llm


def test_ask_cites_only_retrieved_chunks(bm25):
    r = ask(
        "What added sugars limit applies to breakfast cereals?",
        ["2024-08098"],
        bm25,
        MockProvider(),
    )
    assert not r.answer.insufficient_evidence
    shown = {c["chunk_id"] for c in r.chunks}
    for s in r.answer.sentences:
        assert s.citations and set(s.citations) <= shown
    assert r.verification.citation_precision == 1.0


def test_ask_abstains_when_nothing_matches(bm25):
    r = ask("zebra quantum volcano telescope", ["2024-08758"], bm25, MockProvider())
    assert r.answer.insufficient_evidence
    assert r.answer.sentences == []


def test_ask_requires_documents(bm25):
    import pytest

    with pytest.raises(ValueError):
        ask("anything", [], bm25, MockProvider())
