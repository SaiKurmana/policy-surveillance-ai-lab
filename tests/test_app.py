"""Smoke-test the Streamlit app in demo mode (no key, temp database)."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from policylab import paths  # noqa: E402

PAGES = [
    "Overview",
    "Search",
    "Ask (grounded Q&A)",
    "Code a document",
    "Review queue",
    "Audit trail",
    "Evaluation",
    "Corpus",
]


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "lab.duckdb")
    monkeypatch.setattr(paths, "INDEX", tmp_path / "no-index")  # BM25 only: no model download
    at = AppTest.from_file(str(paths.ROOT / "app" / "streamlit_app.py"), default_timeout=120)
    at.run()
    return at


def test_every_page_renders_in_demo_mode(app):
    assert not app.exception
    assert any("Demo mode" in w.value for w in app.sidebar.warning)
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page


def test_code_then_review_flow(app):
    app.sidebar.radio[0].set_value("Code a document").run()
    app.button[0].click().run()
    assert not app.exception
    assert any("Saved run" in s.value for s in app.success)
    app.sidebar.text_input[0].set_value("test-reviewer").run()
    app.sidebar.radio[0].set_value("Review queue").run()
    assert not app.exception
    assert "awaiting review" in " ".join(c.value for c in app.caption)
