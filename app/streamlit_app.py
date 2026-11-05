"""Policy Surveillance AI Lab - Streamlit app.

Run: make app   (or: streamlit run app/streamlit_app.py)

Independent portfolio project. Not affiliated with, endorsed by, or produced for
the CDC or any government agency. Uses only public-domain documents. AI outputs
require human review.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from policylab import db, paths  # noqa: E402
from policylab.codebook import NOT_STATED, default_codebook  # noqa: E402
from policylab.coding import code_document  # noqa: E402
from policylab.llm import LLMError, api_key, get_provider  # noqa: E402
from policylab.qa import ask  # noqa: E402
from policylab.retrieval import Filters, HybridRetriever  # noqa: E402
from policylab.store import load_corpus  # noqa: E402

DISCLAIMER = (
    "Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or "
    "any government agency. Uses only public-domain documents. AI outputs require human review."
)

st.set_page_config(
    page_title="Policy Surveillance AI Lab", page_icon=":material/policy:", layout="wide"
)


@st.cache_resource(show_spinner="Loading corpus and search index...")
def resources():
    corpus = load_corpus()
    retriever = HybridRetriever.from_disk(corpus)
    return corpus, retriever


@st.cache_resource
def database():
    return db.connect()


corpus, retriever = resources()
codebook = default_codebook()
con = database()
LIVE = bool(api_key())
provider = get_provider()


def doc_label(n: str) -> str:
    d = corpus.documents[n]
    return f"{n} | {d['publication_date']} | {d['title'][:90]}"


def chunk_link(chunk_id: str) -> str:
    d = corpus.doc_for_chunk(chunk_id)
    return f"[{chunk_id}]({d['url']})" if d else chunk_id


# ---- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.title("Policy Surveillance AI Lab")
    page = st.radio(
        "Go to",
        [
            "Overview",
            "Search",
            "Ask (grounded Q&A)",
            "Code a document",
            "Review queue",
            "Audit trail",
            "Evaluation",
            "Corpus",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    if LIVE:
        st.success(f"Live AI: {provider.model}", icon=":material/bolt:")
    else:
        st.warning(
            "**Demo mode** - no API key found. Search is real; Ask and Code use the offline "
            "keyword/extractive baseline (not an LLM).",
            icon=":material/science:",
        )
    st.caption(
        f"Retrieval: **{retriever.mode}**"
        + ("" if retriever.mode == "hybrid" else " (run `make index` for hybrid)")
    )
    reviewer = st.text_input(
        "Reviewer ID",
        key="reviewer",
        placeholder="e.g. initials-org",
        help="Required to record review decisions. Stored in the audit trail.",
    )
    st.divider()
    st.caption(DISCLAIMER)

# ---- pages -----------------------------------------------------------------
if page == "Overview":
    st.header("Responsible, evaluable AI for policy surveillance")
    st.markdown(
        """
Public health teams track nutrition, physical activity, and obesity-prevention policy by reading
long regulatory documents and coding them by hand. That is slow, and two coders often disagree.
This lab shows a workflow where AI **assists** and humans **decide**:

1. **Search** public-domain Federal Register documents (hybrid keyword + semantic retrieval).
2. **Ask** questions answered *only* from documents you select, with a citation on every sentence
   and an automatic check that each citation supports its sentence.
3. **Code** a document against a structured policy codebook. Every code comes with an exact quote,
   a chunk ID, and a confidence score.
4. **Review** each AI code: accept, edit, or reject it with a reason. Every decision is logged with
   reviewer, timestamp, model, and prompt version.
5. **Evaluate** AI-vs-human agreement (accuracy, Cohen's kappa), citation precision, abstention,
   and retrieval recall.
"""
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents", len(corpus.documents))
    c2.metric("Citable chunks", f"{len(corpus.chunks):,}")
    c3.metric("Agencies", len(corpus.agencies))
    c4.metric("Codebook variables", len(codebook.variables))
    st.info(DISCLAIMER, icon=":material/info:")

elif page == "Search":
    st.header("Search")
    q = st.text_input("Query", placeholder="e.g. added sugars limits for breakfast cereals")
    with st.expander("Filters", expanded=False):
        f1, f2 = st.columns(2)
        agencies = f1.multiselect("Agency", corpus.agencies)
        topics = f2.multiselect("Topic", corpus.topics)
        dates = sorted(d["publication_date"] for d in corpus.documents.values())
        d1, d2, d3 = st.columns(3)
        date_from = d1.text_input("Published from (YYYY-MM-DD)", value=dates[0])
        date_to = d2.text_input("Published to (YYYY-MM-DD)", value=dates[-1])
        k = d3.slider("Results", 5, 30, 10)
    if q:
        res = retriever.search(
            q,
            k=k,
            filters=Filters(
                agencies=agencies or None,
                topics=topics or None,
                date_from=date_from,
                date_to=date_to,
            ),
        )
        if not res:
            st.write("No matching passages.")
        for r in res:
            d = r.document
            with st.container(border=True):
                st.markdown(
                    f"**{d['title']}**  \n{d['agency']} | {d['document_type']} | "
                    f"{d['publication_date']} | {d.get('citation', '')} | "
                    f"[Federal Register]({d['url']}) | [GovInfo text]({d['full_text_url']})"
                )
                st.caption(
                    f"Chunk `{r.chunk['chunk_id']}` | section: {r.chunk.get('section') or '-'} | "
                    f"FR page {r.chunk.get('fr_page') or '?'} | ranks: BM25 {r.bm25_rank}, "
                    f"embedding {r.dense_rank}"
                )
                st.write(r.chunk["text"][:1500] + ("..." if len(r.chunk["text"]) > 1500 else ""))

elif page == "Ask (grounded Q&A)":
    st.header("Ask a question, grounded in documents you choose")
    st.caption(
        "Answers use only passages retrieved from the selected documents. Every sentence must "
        "cite a chunk; the verifier flags any sentence its citations do not support."
    )
    sel = st.multiselect(
        "Documents to ground the answer",
        sorted(corpus.documents),
        format_func=doc_label,
        default=["2024-08098"],
    )
    q = st.text_input(
        "Question", placeholder="What added sugars limits apply to breakfast cereals?"
    )
    if st.button("Answer", type="primary", disabled=not (q and sel)):
        try:
            with st.spinner("Retrieving and answering..."):
                r = ask(q, sel, retriever, provider)
        except LLMError as e:
            st.error(str(e))
            st.stop()
        if not r.is_live_llm:
            st.warning(
                "Demo mode: this answer was extracted by the offline baseline, not written by an LLM."
            )
        if r.answer.insufficient_evidence:
            st.error(
                f"Insufficient evidence in the selected documents. {r.answer.missing_information}"
            )
        icon = {
            "supported": ":green[supported]",
            "unsupported": ":red[NOT SUPPORTED]",
            "uncited": ":red[NO CITATION]",
            "invalid_citation": ":red[INVALID CITATION]",
        }
        for s in r.verification.sentences:
            cites = ", ".join(chunk_link(c.chunk_id) for c in s.citations) or "none"
            st.markdown(f"- {s.text}  \n  {icon[s.status]} | cites {cites}")
        if r.answer.missing_information and not r.answer.insufficient_evidence:
            st.info(f"Partial answer. Missing: {r.answer.missing_information}")
        cp = r.verification.citation_precision
        st.caption(f"Citation precision: {cp:.0%}" if cp is not None else "No citations.")
        st.caption(f"{r.provider} / {r.served_model} | prompt {r.prompt_version} ({r.prompt_sha})")
        with st.expander(f"Passages shown to the model ({len(r.chunks)})"):
            for c in r.chunks:
                st.markdown(f"**{chunk_link(c['chunk_id'])}**")
                st.text(c["text"][:2000])
    ex_path = paths.DEMO_OUTPUTS / "qa_examples.json"
    if ex_path.exists():
        with st.expander("Cached example outputs"):
            ex = json.loads(ex_path.read_text())
            st.caption(ex["note"])
            for e in ex["examples"]:
                st.markdown(f"**Q: {e['question']}** (docs: {', '.join(e['docs'])})")
                for s in e["sentences"]:
                    st.markdown(f"- {s['text']} `[{', '.join(s['citations'])}]` - {s['status']}")
                if e["insufficient_evidence"]:
                    st.markdown("- _Insufficient evidence - abstained._")

elif page == "Code a document":
    st.header("AI-assisted policy coding")
    st.caption(f"Codebook v{codebook.version}: {', '.join(codebook.ids)}")
    doc = st.selectbox("Document", sorted(corpus.documents), format_func=doc_label)
    d = corpus.documents[doc]
    st.markdown(f"[{d['title']}]({d['url']}) - {d['agency']}, {d['publication_date']}")
    if d.get("abstract"):
        st.caption(d["abstract"])
    if st.button("Run AI coding", type="primary"):
        try:
            with st.spinner("Selecting evidence passages and coding..."):
                run = code_document(doc, codebook, retriever, provider)
        except LLMError as e:
            st.error(str(e))
            st.stop()
        db.save_run(con, run)
        if not run.is_live_llm:
            st.warning(
                "Demo mode: codes were produced by the offline keyword baseline, not an LLM."
            )
        if run.problems:
            st.error("Validation problems (shown to reviewers): " + "; ".join(run.problems))
        rows = [
            {
                "variable": c.variable,
                "status": c.status,
                "values": ", ".join(c.values),
                "confidence": c.confidence,
                "quote check": run.quote_checks.get(c.variable),
                "chunk": c.chunk_id,
                "quote": c.supporting_quote,
            }
            for c in run.coding.codes
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.success(f"Saved run `{run.run_id}` ({len(rows)} codes) to the review queue.")

elif page == "Review queue":
    st.header("Human review queue")
    if not reviewer.strip():
        st.warning("Enter your Reviewer ID in the sidebar to record decisions.")
    queue = db.review_queue(con)
    if queue.empty:
        st.info("Nothing to review. Run AI coding on a document first.")
        st.stop()
    docs_in_q = sorted(queue.doc_number.unique())
    doc = st.selectbox("Document", docs_in_q, format_func=doc_label)
    order = {v: i for i, v in enumerate(codebook.ids)}
    items = queue[queue.doc_number == doc].sort_values(
        ["created_at", "variable"],
        key=lambda col: col.map(order) if col.name == "variable" else col,
    )
    st.caption(f"{len(items)} codes awaiting review for this document; {len(queue)} total.")
    for _, row in items.iterrows():
        var = codebook.get(row.variable)
        values = json.loads(row.ai_values)
        key = row.code_id
        st.session_state.setdefault(f"t0-{key}", time.time())
        with st.container(border=True):
            st.markdown(f"#### {var.label} (`{var.id}`)")
            st.caption(var.definition)
            badge = ":red[not live LLM]" if not row.is_live_llm else ""
            st.markdown(
                f"**AI:** `{', '.join(values) or '(no value)'}` | status {row.status} | "
                f"confidence {row.confidence:.2f} | quote check **{row.quote_check}** | "
                f"{row.model} / {row.prompt_version} {badge}"
            )
            if row.supporting_quote:
                st.markdown(f"> {row.supporting_quote}")
            if row.chunk_id and row.chunk_id in corpus.by_id:
                with st.expander(f"Source passage {row.chunk_id}"):
                    st.text(corpus.by_id[row.chunk_id]["text"])
            st.caption(f"Rationale: {row.rationale}")
            with st.form(f"f-{key}"):
                decision = st.radio(
                    "Decision", ["accept", "edit", "reject"], horizontal=True, key=f"d-{key}"
                )
                if var.type == "date":
                    new = st.text_input(
                        f"Edited value (YYYY-MM-DD or {NOT_STATED})", key=f"v-{key}"
                    )
                    new_vals = [new.strip()] if new.strip() else []
                elif var.type == "single":
                    opts = list(var.values)
                    pick = st.selectbox(
                        "Edited value",
                        opts,
                        key=f"v-{key}",
                        index=opts.index(values[0]) if values and values[0] in opts else 0,
                    )
                    new_vals = [pick]
                else:
                    new_vals = st.multiselect(
                        "Edited values",
                        list(var.values),
                        key=f"v-{key}",
                        default=[v for v in values if v in var.values],
                    )
                reason = st.text_input("Reason (required for edit or reject)", key=f"r-{key}")
                if st.form_submit_button("Record decision", disabled=not reviewer.strip()):
                    try:
                        db.record_decision(
                            con,
                            key,
                            decision,
                            reviewer,
                            reason,
                            new_vals if decision == "edit" else None,
                            seconds_spent=time.time() - st.session_state[f"t0-{key}"],
                        )
                        st.success("Recorded.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

elif page == "Audit trail":
    st.header("Audit trail")
    st.caption(
        "Append-only log of every review decision, with the model and prompt version that produced "
        "the code being reviewed."
    )
    trail = db.audit_trail(con)
    if trail.empty:
        st.info("No decisions recorded yet.")
    else:
        st.dataframe(trail, hide_index=True, use_container_width=True)
        st.download_button(
            "Download CSV", trail.to_csv(index=False), "review_audit_trail.csv", "text/csv"
        )
        st.subheader("Decisions by variable")
        st.dataframe(db.review_summary(con), hide_index=True)

elif page == "Evaluation":
    st.header("Evaluation")
    if paths.EVAL_RESULTS_MD.exists():
        md = paths.EVAL_RESULTS_MD.read_text()
        # st.markdown cannot load local images; render them separately.
        st.markdown("\n".join(ln for ln in md.splitlines() if not ln.startswith("![")))
        for img in ("coding_agreement.png", "retrieval_recall.png"):
            p = paths.EVAL_CHARTS / img
            if p.exists():
                st.image(str(p))
    else:
        st.info("Run `make eval` to generate results.")

elif page == "Corpus":
    st.header("Corpus")
    st.caption(
        "Federal Register documents (public domain). Metadata from the Federal Register API; "
        "full text from GPO GovInfo. Access dates are in the manifest."
    )
    man = pd.read_csv(paths.MANIFEST)
    st.dataframe(
        man[
            [
                "document_number",
                "title",
                "agency",
                "document_type",
                "publication_date",
                "topics",
                "n_chunks",
                "access_date",
                "url",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={"url": st.column_config.LinkColumn("Source")},
    )
    st.download_button(
        "Download manifest CSV", paths.MANIFEST.read_bytes(), "corpus_manifest.csv", "text/csv"
    )
