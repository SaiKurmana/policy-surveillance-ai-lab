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


def _live_warning_text(at):
    return " ".join(w.value for w in at.sidebar.warning)


def test_key_alone_does_not_enable_live_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("POLICYLAB_PROVIDER", raising=False)
    monkeypatch.delenv("LIVE_MODE_PASSWORD", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "lab.duckdb")
    monkeypatch.setattr(paths, "INDEX", tmp_path / "no-index")
    at = AppTest.from_file(str(paths.ROOT / "app" / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception
    assert "Demo mode" in _live_warning_text(at)
    assert not at.sidebar.success
    assert all(t.key != "live_password" for t in at.sidebar.text_input)


def test_live_mode_requires_password(tmp_path, monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.delenv("POLICYLAB_PROVIDER", raising=False)
    monkeypatch.delenv("POLICYLAB_MODEL", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("LIVE_MODE_PASSWORD", "open-sesame")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "lab.duckdb")
    monkeypatch.setattr(paths, "INDEX", tmp_path / "no-index")
    at = AppTest.from_file(str(paths.ROOT / "app" / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception
    assert "Demo mode" in _live_warning_text(at)

    at.text_input(key="live_password").set_value("wrong").run()
    assert "Demo mode" in _live_warning_text(at)
    assert any("Incorrect" in e.value for e in at.sidebar.error)

    at.text_input(key="live_password").set_value("open-sesame").run()
    assert not at.exception
    assert not at.sidebar.warning
    assert any("claude-sonnet-5-5" in s.value for s in at.sidebar.success)
