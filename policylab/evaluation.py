"""Evaluation harness: AI-vs-human coding agreement, grounded Q&A, retrieval.

``make eval`` runs this with the offline baseline (no API key, deterministic).
``python -m policylab.evaluation --provider anthropic`` evaluates a live model.

Outputs: eval/results.json, eval/results.md, eval/charts/*.png
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import paths
from .codebook import Codebook, load_codebook
from .coding import code_document
from .llm import get_provider
from .qa import ask
from .retrieval import HybridRetriever
from .store import Corpus, load_corpus
from .textutil import normalize, quote_in

# ---------------------------------------------------------------------------
# agreement metrics
# ---------------------------------------------------------------------------


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    """Cohen's kappa for two raters over the same items (nominal labels)."""
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return 1.0 if po == 1.0 else None  # undefined: both raters constant
    return (po - pe) / (1 - pe)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def multilabel_kappa(ai: list[set[str]], gold: list[set[str]], labels: list[str]) -> float | None:
    """Mean of per-label binary kappas over labels that occur in either rater."""
    ks = []
    for lab in labels:
        x = ["1" if lab in s else "0" for s in ai]
        y = ["1" if lab in s else "0" for s in gold]
        if "1" not in x and "1" not in y:
            continue
        k = cohen_kappa(x, y)
        if k is not None:
            ks.append(k)
    return sum(ks) / len(ks) if ks else None


@dataclass
class GoldRow:
    doc_number: str
    variable: str
    values: list[str]
    chunk_id: str
    quote: str
    status: str
    coder_id: str


def load_gold(path: Path = paths.GOLD_CODES) -> list[GoldRow]:
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(
                GoldRow(
                    doc_number=r["doc_number"],
                    variable=r["variable"],
                    values=[v for v in r["gold_values"].split(";") if v],
                    chunk_id=r["evidence_chunk_id"],
                    quote=r["evidence_quote"],
                    status=r["status"],
                    coder_id=r["coder_id"],
                )
            )
    return rows


def gold_tier(rows: list[GoldRow]) -> tuple[str, list[GoldRow]]:
    """Use human-verified rows when any exist; otherwise fall back to drafts."""
    verified = [r for r in rows if r.status == "verified" and r.values]
    if verified:
        return "verified", verified
    return "draft_unverified", [r for r in rows if r.status == "draft_unverified" and r.values]


def coding_agreement(
    ai: dict[tuple[str, str], dict], gold: list[GoldRow], codebook: Codebook
) -> dict:
    """ai: (doc, variable) -> {"status", "values", "quote_check", "confidence"}."""
    per_var = {}
    for var in codebook.variables:
        items = [g for g in gold if g.variable == var.id]
        if not items:
            per_var[var.id] = {"n_gold": 0}
            continue
        pairs = [(ai.get((g.doc_number, var.id)), g) for g in items]
        coded = [(a, g) for a, g in pairs if a and a["status"] == "coded"]
        correct_all = sum(1 for a, g in coded if set(a["values"]) == set(g.values))
        res = {
            "label": var.label,
            "type": var.type,
            "n_gold": len(items),
            "n_ai_coded": len(coded),
            "abstention_rate": 1 - len(coded) / len(items),
            "accuracy": correct_all / len(items),  # abstentions count as misses
            "accuracy_when_coded": correct_all / len(coded) if coded else None,
        }
        if var.type == "multi":
            res["mean_jaccard"] = (
                sum(jaccard(set(a["values"]), set(g.values)) for a, g in coded) / len(coded)
                if coded else None
            )
            res["kappa"] = multilabel_kappa(
                [set(a["values"]) for a, _ in coded], [set(g.values) for _, g in coded], list(var.values)
            )
            res["kappa_kind"] = "mean per-label binary kappa"
        elif var.type == "single":
            res["kappa"] = cohen_kappa([a["values"][0] for a, _ in coded], [g.values[0] for _, g in coded])
            res["kappa_kind"] = "Cohen's kappa"
        else:
            res["kappa"] = None
            res["kappa_kind"] = "n/a (dates: exact-match accuracy only)"
        per_var[var.id] = res

    all_items = [g for g in gold]
    coded_quotes = [
        a for (d, v), a in ai.items() if a["status"] == "coded" and a["quote_check"] in ("exact", "not_found",
                                                                                          "invalid_chunk")
    ]
    kappas = [r["kappa"] for r in per_var.values() if r.get("kappa") is not None]
    accs = [r["accuracy"] for r in per_var.values() if r.get("n_gold")]
    return {
        "per_variable": per_var,
        "n_gold_cells": len(all_items),
        "n_documents": len({g.doc_number for g in all_items}),
        "macro_accuracy": sum(accs) / len(accs) if accs else None,
        "macro_kappa": sum(kappas) / len(kappas) if kappas else None,
        "quote_verification_rate": (
            sum(a["quote_check"] == "exact" for a in coded_quotes) / len(coded_quotes)
            if coded_quotes else None
        ),
    }


# ---------------------------------------------------------------------------
# retrieval
# ---------------------------------------------------------------------------


def relevant_chunks(pair: dict, corpus: Corpus) -> set[str]:
    rel = set()
    for d in pair["docs"]:
        for c in corpus.chunks_for(d):
            if all(quote_in(s, c["text"]) for s in pair["must_contain"]):
                rel.add(c["chunk_id"])
    return rel


def retrieval_eval(retriever: HybridRetriever, pairs: list[dict], ks=(1, 3, 5, 10)) -> dict:
    hits = {k: 0 for k in ks}
    rr = []
    rows = []
    for p in pairs:
        rel = relevant_chunks(p, retriever.corpus)
        res = [r.chunk["chunk_id"] for r in retriever.search(p["question"], k=max(ks))]
        rank = next((i + 1 for i, cid in enumerate(res) if cid in rel), None)
        for k in ks:
            hits[k] += bool(rank and rank <= k)
        rr.append(1 / rank if rank else 0.0)
        rows.append({"id": p["id"], "n_relevant": len(rel), "first_relevant_rank": rank})
    n = len(pairs)
    return {
        "mode": retriever.mode,
        "n_pairs": n,
        "recall_at_k": {str(k): hits[k] / n for k in ks},
        "mrr_at_10": sum(rr) / n,
        "per_pair": rows,
    }


# ---------------------------------------------------------------------------
# grounded Q&A
# ---------------------------------------------------------------------------


def qa_eval(retriever: HybridRetriever, provider, questions: list[dict]) -> dict:
    rows = []
    for q in questions:
        r = ask(q["question"], q["docs"], retriever, provider)
        text = " ".join(s.text for s in r.answer.sentences)
        abstained = r.answer.insufficient_evidence or not r.answer.sentences
        row = {
            "id": q["id"],
            "answerable": q["answerable"],
            "abstained": abstained,
            "citation_precision": r.verification.citation_precision,
            "n_citations": r.verification.n_citations,
            "flagged_sentences": len(r.verification.flagged),
        }
        if q["answerable"]:
            terms = q.get("expect_terms", [])
            row["key_facts_present"] = (not abstained) and all(normalize(t) in normalize(text) for t in terms)
        rows.append(row)
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    cp = [r["citation_precision"] for r in rows if r["citation_precision"] is not None]
    total_cit = sum(r["n_citations"] for r in rows)
    supported = sum((r["citation_precision"] or 0) * r["n_citations"] for r in rows)
    return {
        "n_questions": len(rows),
        "abstention_rate": sum(r["abstained"] for r in rows) / len(rows),
        "correct_abstention_rate": sum(r["abstained"] for r in unans) / len(unans) if unans else None,
        "false_abstention_rate": sum(r["abstained"] for r in ans) / len(ans) if ans else None,
        "key_fact_accuracy": sum(bool(r.get("key_facts_present")) for r in ans) / len(ans) if ans else None,
        "citation_precision": supported / total_cit if total_cit else None,
        "mean_answer_citation_precision": sum(cp) / len(cp) if cp else None,
        "per_question": rows,
    }


# ---------------------------------------------------------------------------
# time-saved placeholder
# ---------------------------------------------------------------------------


def time_saved() -> dict:
    """Placeholder until reviewers log real timings (review_decisions.seconds_spent)
    and a manual-coding baseline is timed. Returns null estimates, never invented ones."""
    cfg_path = paths.EVAL / "time_assumptions.yaml"
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    manual = cfg.get("manual_minutes_per_document")
    review = cfg.get("review_minutes_per_document")
    est = None
    if manual and review:
        est = {"minutes_saved_per_document": manual - review, "percent_saved": (manual - review) / manual}
    return {
        "status": "measured" if est else "placeholder - not measured",
        "manual_minutes_per_document": manual,
        "review_minutes_per_document": review,
        "estimate": est,
        "how_to_measure": "Time manual coding of the gold documents; log review time in the app "
        "(seconds_spent is stored per review decision); fill eval/time_assumptions.yaml.",
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------


def _fmt(x, pct=False):
    if x is None:
        return "n/a"
    return f"{x:.0%}" if pct else f"{x:.2f}"


def write_charts(results: dict, out: Path) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    out.mkdir(parents=True, exist_ok=True)
    surface, ink, muted, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    s1, s2 = "#2a78d6", "#eb6834"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": grid, "axes.labelcolor": muted,
                         "xtick.color": muted, "ytick.color": muted, "text.color": ink})
    files = []

    pv = results["coding"]["per_variable"]
    vars_ = [v for v in pv if pv[v].get("n_gold")]
    if vars_:
        fig, ax = plt.subplots(figsize=(7.5, 0.42 * len(vars_) + 1.4), facecolor=surface)
        ax.set_facecolor(surface)
        y = list(range(len(vars_)))[::-1]
        acc = [pv[v]["accuracy"] for v in vars_]
        kap = [pv[v]["kappa"] if pv[v].get("kappa") is not None else 0 for v in vars_]
        ax.barh([i + 0.2 for i in y], acc, height=0.36, color=s1, label="Accuracy (abstain = miss)")
        ax.barh([i - 0.2 for i in y], kap, height=0.36, color=s2, label="Kappa (n/a shown as 0)")
        ax.set_yticks(y, vars_)
        ax.set_xlim(min(0, min(kap) - 0.05), 1)
        ax.axvline(0, color=muted, lw=0.8)
        ax.grid(axis="x", color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=9)
        fig.suptitle(f"Coding agreement by variable - {results['provider']['label']}", x=0.02, ha="left",
                     fontsize=11)
        fig.tight_layout()
        p = out / "coding_agreement.png"
        fig.savefig(p, dpi=150, facecolor=surface)
        plt.close(fig)
        files.append(p.name)

    ret = results["retrieval"]
    fig, ax = plt.subplots(figsize=(6, 3.2), facecolor=surface)
    ax.set_facecolor(surface)
    for name, color in (("primary", s1), ("bm25_only", s2)):
        r = ret.get(name)
        if not r:
            continue
        ks = list(r["recall_at_k"])
        ax.plot([int(k) for k in ks], [r["recall_at_k"][k] for k in ks], color=color, lw=2,
                marker="o", ms=6, label=f"{r['mode']} (MRR {r['mrr_at_10']:.2f})")
    ax.set_ylim(0, 1.02)
    ax.set_xticks([1, 3, 5, 10])
    ax.set_xlabel("k (passages returned)")
    ax.set_ylabel("Recall@k")
    ax.grid(color=grid, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.set_title("Retrieval: share of questions with a relevant passage in top k", loc="left", fontsize=11)
    fig.tight_layout()
    p = out / "retrieval_recall.png"
    fig.savefig(p, dpi=150, facecolor=surface)
    plt.close(fig)
    files.append(p.name)
    return files


def write_markdown(results: dict, path: Path) -> None:
    c, q, t = results["coding"], results["qa"], results["time_saved"]
    prov = results["provider"]
    gold = results["gold"]
    lines = [
        "# Evaluation results",
        "",
        f"_Generated {results['generated_at']} by `make eval`. Do not edit by hand._",
        "",
    ]
    banner = []
    if not prov["is_live_llm"]:
        banner.append(
            "**These numbers come from the offline keyword/extractive baseline, not from an LLM.** "
            "They show that the evaluation pipeline runs end to end and set a floor a real model "
            "must beat. To evaluate Claude, run `python -m policylab.evaluation --provider anthropic` "
            "with `ANTHROPIC_API_KEY` set."
        )
    if gold["tier"] != "verified":
        banner.append(
            f"**The gold standard is not validated.** 0 of {gold['n_documents_total']} gold documents "
            "have been verified by a human coder; metrics below use the assistant-drafted starter "
            "labels (`status = draft_unverified`). Treat every agreement number as a pipeline smoke "
            "test, not a finding. See `docs/evaluation_protocol.md`."
        )
    for b in banner:
        lines += [f"> {b}", ">"]
    if banner:
        lines[-1] = ""
    lines += [
        "## Run configuration",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Coding/Q&A provider | {prov['label']} (`{prov['model']}`) |",
        f"| Live LLM | {'yes' if prov['is_live_llm'] else 'no'} |",
        f"| Prompt versions | coding `{results['prompt_versions']['coding']}`, Q&A `{results['prompt_versions']['qa']}` |",
        f"| Codebook version | {results['codebook_version']} |",
        f"| Gold tier used | `{gold['tier']}` ({gold['n_cells_used']} cells, {c['n_documents']} documents) |",
        f"| Gold status counts | {', '.join(f'{k}: {v}' for k, v in gold['status_counts'].items())} |",
        f"| Corpus | {results['corpus']['documents']} documents, {results['corpus']['chunks']} chunks |",
        "",
        "## 1. Policy coding: AI vs. human agreement",
        "",
        f"Macro accuracy **{_fmt(c['macro_accuracy'], True)}**, macro kappa **{_fmt(c['macro_kappa'])}**, "
        f"supporting quotes found verbatim in the cited chunk: **{_fmt(c['quote_verification_rate'], True)}**.",
        "",
        "| Variable | n | Abstained | Accuracy | Accuracy when coded | Kappa | Kappa type |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for vid, r in c["per_variable"].items():
        if not r.get("n_gold"):
            lines.append(f"| {vid} | 0 | | | | | no gold labels yet |")
            continue
        lines.append(
            f"| {vid} | {r['n_gold']} | {_fmt(r['abstention_rate'], True)} | {_fmt(r['accuracy'], True)} | "
            f"{_fmt(r['accuracy_when_coded'], True)} | {_fmt(r.get('kappa'))} | {r['kappa_kind']} |"
        )
    lines += [
        "",
        "Accuracy counts an abstention as a miss. Multi-select variables count as correct only on an "
        "exact set match; kappa for them is the mean of per-label binary kappas. With ~20 documents, "
        "kappa confidence intervals are wide (roughly +/-0.2 or more); do not over-read small differences.",
        "",
    ]
    if "coding_agreement.png" in results["charts"]:
        lines += ["![Coding agreement](charts/coding_agreement.png)", ""]
    lines += [
        "## 2. Grounded Q&A",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Questions | {q['n_questions']} |",
        f"| Abstention rate (all questions) | {_fmt(q['abstention_rate'], True)} |",
        f"| Correct abstention (unanswerable questions) | {_fmt(q['correct_abstention_rate'], True)} |",
        f"| False abstention (answerable questions) | {_fmt(q['false_abstention_rate'], True)} |",
        f"| Key facts present in answer (answerable) | {_fmt(q['key_fact_accuracy'], True)} |",
        f"| Citation precision (cited chunk supports the sentence) | {_fmt(q['citation_precision'], True)} |",
        "",
        "Citation precision is measured by the lexical verifier in `policylab/verify.py` (content-word "
        "overlap >= 0.6 and every number in the sentence present in the chunk). An extractive baseline "
        "scores near 100% by construction because it copies sentences; the metric is meaningful for a "
        "generative model.",
        "",
        "## 3. Retrieval",
        "",
        "| Retriever | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("primary", "bm25_only"):
        r = results["retrieval"].get(name)
        if r:
            rk = r["recall_at_k"]
            lines.append(
                f"| {r['mode']} | {_fmt(rk['1'], True)} | {_fmt(rk['3'], True)} | {_fmt(rk['5'], True)} | "
                f"{_fmt(rk['10'], True)} | {_fmt(r['mrr_at_10'])} |"
            )
    lines += [
        "",
        f"{results['retrieval']['primary']['n_pairs']} question-passage pairs (status: "
        f"`{results['retrieval']['pairs_status']}`), searched over the full corpus without filters.",
        "",
    ]
    if "retrieval_recall.png" in results["charts"]:
        lines += ["![Retrieval recall](charts/retrieval_recall.png)", ""]
    lines += [
        "## 4. Time saved",
        "",
        f"Status: **{t['status']}**. {t['how_to_measure']}",
        "",
        "## What is real and what is placeholder",
        "",
        "| Component | Status |",
        "|---|---|",
        "| Corpus, chunk IDs, retrieval index | Real (Federal Register API + GovInfo text) |",
        "| Retrieval metrics | Real computation; question set is an unverified draft |",
        f"| Coding metrics | Real computation; gold labels are `{gold['tier']}` |",
        f"| Model under test | {'Live LLM' if prov['is_live_llm'] else 'Offline baseline (not an LLM)'} |",
        "| Time saved | Placeholder until timed |",
        "",
    ]
    path.write_text("\n".join(lines))


def run(provider_name: str = "mock", limit_docs: int | None = None, use_embeddings: bool = True) -> dict:
    corpus = load_corpus()
    codebook = load_codebook()
    provider = get_provider(provider_name)
    retriever = HybridRetriever.from_disk(corpus, load_model=use_embeddings)
    bm25 = retriever if retriever.mode == "bm25" else HybridRetriever(corpus)

    gold_all = load_gold()
    tier, gold = gold_tier(gold_all)
    docs = sorted({g.doc_number for g in gold})
    if limit_docs:
        docs = docs[:limit_docs]
        gold = [g for g in gold if g.doc_number in docs]
    ai = {}
    runs = []
    for d in docs:
        run_ = code_document(d, codebook, bm25 if provider_name == "mock" else retriever, provider)
        runs.append({"doc": d, "problems": run_.problems, "served_model": run_.served_model})
        for c in run_.coding.codes:
            ai[(d, c.variable)] = {"status": c.status, "values": c.values, "confidence": c.confidence,
                                   "quote_check": run_.quote_checks.get(c.variable)}

    pairs_doc = yaml.safe_load(paths.RETRIEVAL_PAIRS.read_text())
    qa_doc = yaml.safe_load(paths.QA_QUESTIONS.read_text())
    retrieval = {"primary": retrieval_eval(retriever, pairs_doc["pairs"]), "pairs_status": pairs_doc["status"]}
    if retriever.mode != "bm25":
        retrieval["bm25_only"] = retrieval_eval(bm25, pairs_doc["pairs"])

    label = "Offline baseline (keyword/extractive, not an LLM)" if not provider.is_live_llm else f"Anthropic {provider.model}"
    results = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "provider": {"name": provider.name, "model": provider.model, "is_live_llm": provider.is_live_llm,
                     "label": label},
        "prompt_versions": {"coding": "coding_v1", "qa": "qa_v1"},
        "codebook_version": codebook.version,
        "corpus": {"documents": len(corpus.documents), "chunks": len(corpus.chunks)},
        "gold": {
            "tier": tier,
            "n_cells_used": len(gold),
            "n_documents_total": len({g.doc_number for g in gold_all}),
            "status_counts": dict(Counter(g.status for g in gold_all)),
        },
        "coding": coding_agreement(ai, gold, codebook),
        "coding_runs": runs,
        "qa": qa_eval(bm25 if provider_name == "mock" else retriever, provider, qa_doc["questions"]) | {
            "questions_status": qa_doc["status"]},
        "retrieval": retrieval,
        "time_saved": time_saved(),
    }
    results["charts"] = write_charts(results, paths.EVAL_CHARTS)
    paths.EVAL_RESULTS_JSON.write_text(json.dumps(results, indent=2, default=str) + "\n")
    write_markdown(results, paths.EVAL_RESULTS_MD)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic"])
    ap.add_argument("--limit-docs", type=int, default=None, help="evaluate only the first N gold docs")
    ap.add_argument("--no-embeddings", action="store_true", help="BM25 only (CI)")
    args = ap.parse_args()
    r = run(args.provider, args.limit_docs, use_embeddings=not args.no_embeddings)
    c = r["coding"]
    print(f"coding: macro_accuracy={_fmt(c['macro_accuracy'])} macro_kappa={_fmt(c['macro_kappa'])} "
          f"(gold tier: {r['gold']['tier']}, provider: {r['provider']['label']})")
    print(f"qa: citation_precision={_fmt(r['qa']['citation_precision'])} "
          f"correct_abstention={_fmt(r['qa']['correct_abstention_rate'])}")
    p = r["retrieval"]["primary"]
    print(f"retrieval ({p['mode']}): recall@5={_fmt(p['recall_at_k']['5'])} mrr={_fmt(p['mrr_at_10'])}")
    print(f"wrote {paths.EVAL_RESULTS_MD.relative_to(paths.ROOT)}")


if __name__ == "__main__":
    main()
