"""Build the static GitHub Pages site into _site/ (``make site``)."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import yaml

from . import paths
from .codebook import load_codebook

REPO_URL = "https://github.com/saikurmana/policy-surveillance-ai-lab"
DISCLAIMER = (
    "Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or "
    "any government agency. Uses only public-domain documents. AI outputs require human review."
)
DOC_PAGES = ["responsible_use", "model_card", "data_governance", "evaluation_protocol"]


def _pct(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def _num(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _fill(template: str, values: dict[str, str]) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    missing = re.findall(r"\{\{(\w+)\}\}", out)
    if missing:
        raise ValueError(f"unfilled placeholders: {sorted(set(missing))}")
    return out


def _bars(per_var: dict) -> str:
    rows = []
    for vid, r in per_var.items():
        if not r.get("n_gold"):
            continue
        acc = r["accuracy"]
        kap = r.get("kappa")
        kw = max(0.0, kap) if kap is not None else 0.0
        rows.append(
            f'<div class="bar-row"><div class="bar-name">{html.escape(r.get("label", vid))}</div>'
            f'<div class="bar-pair">'
            f'<div class="bar acc" title="Accuracy {_pct(acc)}"><span style="width:{acc * 100:.1f}%"></span>'
            f'<em class="bar-val">{_pct(acc)}</em></div>'
            f'<div class="bar kap" title="Kappa {_num(kap)}"><span style="width:{kw * 100:.1f}%"></span>'
            f'<em class="bar-val">{"kappa " + _num(kap) if kap is not None else "kappa n/a"}</em></div>'
            f"</div></div>"
        )
    return "\n".join(rows)


def _md_to_html(md_text: str) -> str:
    import markdown

    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
    # docs link to each other as foo.md; on the site they are foo.html
    return re.sub(r'href="([a-z_]+)\.md"', r'href="\1.html"', body)


def build(out: Path = paths.SITE_OUT) -> Path:
    if out.exists():
        shutil.rmtree(out)
    (out / "docs").mkdir(parents=True)
    shutil.copytree(paths.SITE_SRC / "static", out / "static")

    results = (
        json.loads(paths.EVAL_RESULTS_JSON.read_text())
        if paths.EVAL_RESULTS_JSON.exists()
        else None
    )
    with open(paths.MANIFEST, newline="") as f:
        manifest = list(csv.DictReader(f))
    topics_cfg = yaml.safe_load(paths.CORPUS_CONFIG.read_text())["topics"]
    topic_counts = Counter(t for r in manifest for t in r["topics"].split(";") if t)
    agency_counts = Counter(r["agency"] for r in manifest)
    n_chunks = sum(int(r["n_chunks"]) for r in manifest)

    if results:
        c = results["coding"]
        notes = []
        if not results["provider"]["is_live_llm"]:
            notes.append(
                "These results come from the <strong>offline keyword/extractive baseline</strong>, "
                "not an LLM. They show the pipeline runs end to end and set a floor a model must beat."
            )
        if results["gold"]["tier"] != "verified":
            notes.append(
                "The gold standard is a <strong>starter draft that no human has verified yet</strong> "
                f"(0 of {results['gold']['n_documents_total']} documents). Treat agreement numbers "
                "as a smoke test, not a finding."
            )
        eval_values = {
            "eval_notice": "".join(f'<div class="notice">{n}</div>' for n in notes),
            "macro_acc": _pct(c["macro_accuracy"]),
            "macro_kappa": _num(c["macro_kappa"]),
            "recall5": _pct(results["retrieval"]["primary"]["recall_at_k"]["5"]),
            "ret_mode": results["retrieval"]["primary"]["mode"],
            "correct_abst": _pct(results["qa"]["correct_abstention_rate"]),
            "bars": _bars(c["per_variable"]),
            "generated": results["generated_at"][:10],
        }
    else:
        eval_values = {
            k: "n/a"
            for k in (
                "macro_acc",
                "macro_kappa",
                "recall5",
                "ret_mode",
                "correct_abst",
                "generated",
            )
        }
        eval_values |= {
            "eval_notice": '<div class="notice">Run <code>make eval</code> to populate.</div>',
            "bars": "",
        }

    index = _fill(
        (paths.SITE_SRC / "index.template.html").read_text(),
        {
            "repo_url": REPO_URL,
            "disclaimer": DISCLAIMER,
            "n_docs": str(len(manifest)),
            "n_chunks": f"{n_chunks:,}",
            "n_vars": str(len(load_codebook().variables)),
            "topic_rows": "".join(
                f"<tr><td>{html.escape(topics_cfg[t]['label'])}</td><td class='num'>{n}</td></tr>"
                for t, n in topic_counts.most_common()
            ),
            "agency_rows": "".join(
                f"<tr><td>{html.escape(a)}</td><td class='num'>{n}</td></tr>"
                for a, n in agency_counts.most_common()
            ),
            **eval_values,
        },
    )
    (out / "index.html").write_text(index)

    doc_t = (paths.SITE_SRC / "doc.template.html").read_text()
    for name in DOC_PAGES:
        src = paths.DOCS / f"{name}.md"
        md_text = src.read_text()
        title = next((ln[2:].strip() for ln in md_text.splitlines() if ln.startswith("# ")), name)
        page = _fill(
            doc_t,
            {"title": html.escape(title), "body": _md_to_html(md_text), "disclaimer": DISCLAIMER},
        )
        (out / "docs" / f"{name}.html").write_text(page)
    (out / ".nojekyll").write_text("")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=paths.SITE_OUT)
    args = ap.parse_args()
    out = build(args.out)
    print(f"site written to {out}")


if __name__ == "__main__":
    main()
