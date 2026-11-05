import re
import subprocess

from policylab import paths
from policylab.site import DISCLAIMER, build

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
    files = subprocess.run(
        ["git", "ls-files"], cwd=paths.ROOT, capture_output=True, text=True
    ).stdout.split()
    pattern = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
    for f in files:
        p = paths.ROOT / f
        if p.suffix in {".gz", ".png", ".webp", ".duckdb"} or not p.is_file():
            continue
        assert not pattern.search(p.read_text(errors="ignore")), f
