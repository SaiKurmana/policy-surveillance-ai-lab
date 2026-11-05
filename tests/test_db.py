import pytest

from policylab import db
from policylab.coding import code_document
from policylab.llm import MockProvider


@pytest.fixture()
def con_with_run(codebook, bm25):
    con = db.connect(":memory:")
    run = code_document("2024-25567", codebook, bm25, MockProvider())
    db.save_run(con, run)
    return con, run


def test_queue_then_decisions_are_audited(con_with_run):
    con, run = con_with_run
    q = db.review_queue(con)
    assert len(q) == len(run.coding.codes)
    ids = dict(zip(q.variable, q.code_id, strict=True))
    db.record_decision(con, ids["policy_domain"], "accept", "rev-1", seconds_spent=12.5)
    db.record_decision(
        con, ids["settings"], "edit", "rev-1", "missing retail", ["packaged_food_supply"]
    )
    db.record_decision(con, ids["equity_provisions"], "reject", "rev-2", "boilerplate only")
    trail = db.audit_trail(con)
    assert len(trail) == 3
    assert set(trail.reviewer_id) == {"rev-1", "rev-2"}
    assert set(trail.model) == {MockProvider.model}
    assert set(trail.prompt_version) == {"coding_v1"}
    assert len(db.review_queue(con)) == len(run.coding.codes) - 3


def test_decision_rules_enforced(con_with_run):
    con, _ = con_with_run
    cid = db.review_queue(con).code_id.iloc[0]
    with pytest.raises(ValueError):
        db.record_decision(con, cid, "accept", "  ")
    with pytest.raises(ValueError):
        db.record_decision(con, cid, "reject", "rev", reason="")
    with pytest.raises(ValueError):
        db.record_decision(con, cid, "maybe", "rev", reason="x")
    with pytest.raises(KeyError):
        db.record_decision(con, "nope", "accept", "rev")


def test_edit_values_validated_against_codebook(con_with_run):
    con, _ = con_with_run
    q = db.review_queue(con)
    cid = q[q.variable == "settings"].code_id.iloc[0]
    with pytest.raises(ValueError):
        db.record_decision(con, cid, "edit", "rev", "bad", ["the moon"])
