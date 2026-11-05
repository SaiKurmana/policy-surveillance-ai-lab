"""Regenerate the cached example outputs shown in demo mode.

These are produced by the offline baseline (not an LLM) and say so. If you run
this with ANTHROPIC_API_KEY set and ``--provider anthropic``, the file records
the live model instead. Never hand-edit these files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

from . import paths
from .llm import get_provider
from .qa import ask
from .retrieval import HybridRetriever
from .store import load_corpus

EXAMPLES = [
    (
        "What added sugars limits apply to breakfast cereals and yogurt in school meals?",
        ["2024-08098"],
    ),
    ("Which restaurants must post calorie information on menus?", ["2014-27833"]),
    ("What did the State of Ohio request in its SNAP demonstration project?", ["2026-18897"]),
    (
        "What is the maximum grant amount for active transportation projects in Canada?",
        ["2024-08758"],
    ),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic"])
    args = ap.parse_args()
    provider = get_provider(args.provider)
    corpus = load_corpus()
    retriever = HybridRetriever(corpus)  # BM25: deterministic and model-free
    out = []
    for q, docs in EXAMPLES:
        r = ask(q, docs, retriever, provider)
        out.append(
            {
                "question": q,
                "docs": docs,
                "insufficient_evidence": r.answer.insufficient_evidence,
                "missing_information": r.answer.missing_information,
                "sentences": [
                    {
                        "text": s.text,
                        "citations": [c.chunk_id for c in s.citations],
                        "status": s.status,
                    }
                    for s in r.verification.sentences
                ],
                "citation_precision": r.verification.citation_precision,
            }
        )
    label = (
        "offline extractive baseline (NOT an LLM)" if not provider.is_live_llm else provider.model
    )
    paths.DEMO_OUTPUTS.mkdir(parents=True, exist_ok=True)
    (paths.DEMO_OUTPUTS / "qa_examples.json").write_text(
        json.dumps(
            {
                "note": f"Generated {dt.date.today()} by `python -m policylab.demo` using the {label}. "
                "Answers are copied sentences from the cited chunks; they are examples of the output "
                "format and verification, not model-quality results.",
                "provider": provider.name,
                "model": provider.model,
                "is_live_llm": provider.is_live_llm,
                "examples": out,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"wrote {len(out)} examples")


if __name__ == "__main__":
    main()
