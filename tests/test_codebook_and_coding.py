import pytest
from pydantic import ValidationError

from policylab.coding import code_document, select_chunks
from policylab.llm import MockProvider
from policylab.schemas import CodedVariable, DocumentCoding


def test_codebook_has_8_to_12_variables(codebook):
    assert 8 <= len(codebook.variables) <= 12
    for v in codebook.variables:
        assert v.type in {"single", "multi", "date"}
        assert v.definition
        if v.type != "date":
            assert v.values
        for value in v.cues:
            assert value in v.values, f"{v.id}: cue for unknown value {value}"


def test_value_validation(codebook):
    assert codebook.get("settings").validate_values(["schools", "child_care"]) == []
    assert codebook.get("settings").validate_values(["moon"])
    assert codebook.get("legal_force").validate_values(["mandatory", "voluntary"])
    assert codebook.get("effective_date").validate_values(["2024-07-01"]) == []
    assert codebook.get("effective_date").validate_values(["not_stated"]) == []
    assert codebook.get("effective_date").validate_values(["July 1"])
    assert codebook.get("nutrients_targeted").validate_values(["none", "sodium"])


def test_pydantic_rejects_bad_confidence_and_extra_fields():
    with pytest.raises(ValidationError):
        CodedVariable(
            variable="x",
            status="coded",
            values=[],
            supporting_quote="",
            chunk_id="",
            confidence=1.5,
            rationale="",
        )
    with pytest.raises(ValidationError):
        CodedVariable(
            variable="x",
            status="maybe",
            values=[],
            supporting_quote="",
            chunk_id="",
            confidence=0.5,
            rationale="",
        )
    with pytest.raises(ValidationError):
        DocumentCoding.model_validate({"doc_number": "1", "codes": [], "extra": 1})


def test_document_coding_validation_catches_problems(codebook):
    codes = [
        CodedVariable(
            variable="settings",
            status="coded",
            values=["moon"],
            supporting_quote="q",
            chunk_id="c",
            confidence=0.5,
            rationale="",
        )
    ]
    problems = DocumentCoding(doc_number="1", codes=codes).validate_against(codebook)
    assert any("moon" in p for p in problems)
    assert any("missing variables" in p for p in problems)


def test_absence_values_need_no_quote(codebook):
    codes = [
        CodedVariable(
            variable=v.id,
            status="insufficient_evidence",
            values=[],
            supporting_quote="",
            chunk_id="",
            confidence=0,
            rationale="",
        )
        for v in codebook.variables
    ]
    codes[-1] = CodedVariable(
        variable="public_comment",
        status="coded",
        values=["no"],
        supporting_quote="",
        chunk_id="",
        confidence=0.4,
        rationale="",
    )
    assert DocumentCoding(doc_number="1", codes=codes).validate_against(codebook) == []


def test_select_chunks_stays_in_document_and_is_bounded(codebook, bm25):
    chunks = select_chunks("2024-08098", codebook, bm25)
    assert 6 <= len(chunks) <= 45
    assert {c["doc_number"] for c in chunks} == {"2024-08098"}


def test_coding_run_end_to_end_with_mock(codebook, bm25):
    run = code_document("2014-27834", codebook, bm25, MockProvider())
    assert [c.variable for c in run.coding.codes] == codebook.ids
    assert run.problems == []
    assert not run.is_live_llm
    stage = next(c for c in run.coding.codes if c.variable == "regulatory_stage")
    assert stage.values == ["final_rule"]
    for c in run.coding.codes:
        assert run.quote_checks[c.variable] in {"exact", "absent_ok", "abstained"}
