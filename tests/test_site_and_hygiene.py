import re
import subprocess

from policylab import paths
from policylab.site import APP_URL, DISCLAIMER, build

REQUIRED_DISCLAIMER = (
    "Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or any "
    "government agency. Uses only public-domain documents. AI outputs require human review."
)


def test_disclaimer_text_is_exact_everywhere():
    assert DISCLAIMER == REQUIRED_DISCLAIMER
    assert REQUIRED_DISCLAIMER in (paths.ROOT / "README.md").read_text()


def test_site_builds_with_docs_and_disclaimer(tmp_path):
    out = build(tmp_path / "site")
    index = (out / "index.html").read_text()
    assert REQUIRED_DISCLAIMER in index
    assert "{{" not in index
    for name in ("responsible_use", "model_card", "data_governance", "evaluation_protocol"):
        page = (out / "docs" / f"{name}.html").read_text()
        assert REQUIRED_DISCLAIMER in page
        assert '.md"' not in page


def test_no_api_keys_committed():
    pattern = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
    for f, text in _tracked_text_files():
        assert not pattern.search(text), f


def test_root_requirements_stay_light_for_streamlit_cloud():
    """The app runs without the embedding model (BM25 fallback), so keep torch out of the deploy."""
    reqs = (paths.ROOT / "requirements.txt").read_text().lower()
    for heavy in ("torch", "sentence-transformers", "sentence_transformers"):
        assert heavy not in reqs


# Built from parts so this file does not match its own scan.
LIVE_APP_PLACEHOLDERS = [
    "coming" + " soon",
    "not yet" + " deployed",
    "will be added after" + " deployment",
]


def _tracked_text_files():
    files = subprocess.run(
        ["git", "ls-files"], cwd=paths.ROOT, capture_output=True, text=True
    ).stdout.split()
    for f in files:
        p = paths.ROOT / f
        if p.suffix in {".gz", ".png", ".webp", ".duckdb"} or not p.is_file():
            continue
        yield f, p.read_text(errors="ignore")


def test_no_live_app_placeholder_text():
    for f, text in _tracked_text_files():
        for phrase in LIVE_APP_PLACEHOLDERS:
            assert phrase not in text.lower(), f"{f} still says '{phrase}'"


def test_live_app_url_is_linked(tmp_path):
    assert APP_URL == "https://policy-ai-lab.streamlit.app/"
    assert APP_URL in (paths.ROOT / "README.md").read_text()
    out = build(tmp_path / "site")
    index = (out / "index.html").read_text()
    assert f'<a class="btn primary" href="{APP_URL}">' in index  # landing page button
    assert index.count(f'href="{APP_URL}"') >= 3  # nav, button, footer
    assert "disabled" not in index
    for name in ("responsible_use", "model_card", "data_governance", "evaluation_protocol"):
        assert f'href="{APP_URL}"' in (out / "docs" / f"{name}.html").read_text()
