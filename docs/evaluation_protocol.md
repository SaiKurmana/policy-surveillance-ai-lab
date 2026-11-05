# Evaluation protocol

> **Template status.** A practical protocol for measuring whether AI-assisted policy coding is good enough to use, and for monitoring it afterward. Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or any government agency. Uses only public-domain documents. AI outputs require human review.

## 1. Questions the evaluation answers

1. **Coding agreement.** How often does the AI assign the same code as a trained human, beyond chance? (accuracy, Cohen's kappa, per variable)
2. **Evidence quality.** When the AI cites evidence, does the cited passage actually support the claim? (quote verification rate, citation precision)
3. **Honest abstention.** Does the system say "insufficient evidence" when the documents do not contain the answer, and answer when they do? (correct and false abstention rates)
4. **Retrieval.** Does search put a relevant passage near the top? (recall@k, MRR)
5. **Efficiency.** Does review of AI codes take less time than coding from scratch? (time saved; placeholder until measured)

## 2. Current status (be explicit about this)

| Asset | Status | Who must act |
|---|---|---|
| `eval/gold/gold_codes.csv` (20 documents x 11 variables) | **Starter draft, not validated.** 213 cells drafted by the AI coding assistant that scaffolded the repo, from abstracts and keyword-located passages; 7 cells left `todo`. Every row is `status = draft_unverified`, `coder_id = assistant-draft`. | Human coder(s) |
| `eval/gold/retrieval_pairs.yaml` (25 pairs) | Draft; relevance defined mechanically by required phrases | Human reviewer |
| `eval/gold/qa_questions.yaml` (12 answerable, 6 unanswerable) | Draft | Human reviewer |
| `eval/results.md` | Produced with the offline baseline, not an LLM | Re-run with a live model after gold is verified |
| Time saved | Not measured | Program |

**Do not cite any agreement number from this repository as evidence that AI coding works** until sections 3 and 4 are complete.

## 3. Building the human gold standard (TODO for the project owner)

1. **Select documents.** Keep the 20 starter documents (they span all four Federal Register document types, 7 agencies as named by the Federal Register, and both domains) or replace some, then fill `gold_codes_template.csv` for the new set.
2. **Train coders on the codebook.** Read `codebook/policy_codebook.yaml` together; code 3 practice documents not in the gold set; discuss every disagreement and update decision rules (bump the codebook version).
3. **Code independently, blind to the AI.** Each coder codes from the full text, without looking at the starter draft values or AI output. Record `gold_values`, `evidence_chunk_id`, `evidence_quote`, and `notes` (use the app's Search page to find chunk IDs). Time each document (start to finish) for the time-saved estimate.
4. **Double-code at least 30% of documents** (6 of 20) with a second coder to measure **human-human kappa**. This is the ceiling: the AI cannot be expected to agree with one human more than two humans agree with each other.
5. **Adjudicate.** Disagreements are resolved by discussion or a third coder; record the adjudicated value.
6. **Mark rows verified.** Set `status = verified` and `coder_id` to the coder's ID. The evaluation automatically switches to verified rows as soon as any exist and stops using drafts.
7. **Freeze.** Tag the commit (e.g. `gold-v1`). Do not edit verified rows after seeing AI results; if a gold label is wrong, fix it in a new version and report both.

Checks that run automatically (`make test`): every gold quote must appear verbatim in its cited chunk, values must be valid codebook values, and every retrieval pair must have at least one relevant chunk.

## 4. Running the evaluation

```bash
make eval                                                 # offline baseline (no key); what CI runs
python -m policylab.evaluation --provider anthropic       # live model; needs ANTHROPIC_API_KEY
python -m policylab.evaluation --no-embeddings            # BM25 only (matches CI)
```

Outputs: `eval/results.md` (human-readable), `eval/results.json` (machine-readable, used by the site), `eval/charts/`.

Record for every reported run: commit SHA, model and `served_model`, effort, prompt versions and hashes, codebook version, gold version (tag), and date. The results file includes most of these automatically.

## 5. Metrics and how to read them

| Metric | Definition | How to read it |
|---|---|---|
| Accuracy | Share of gold items where AI values exactly equal gold values; an AI abstention counts as a miss | Simple, but inflated for variables where one value dominates |
| Accuracy when coded | Accuracy among items the AI did not abstain on | Pair with abstention rate: high accuracy with high abstention means the AI is cautious |
| Cohen's kappa (single-select) | (p_o - p_e) / (1 - p_e) on items both raters coded | Below 0.40 poor; 0.41-0.60 moderate; 0.61-0.80 substantial; above 0.80 near-perfect (Landis & Koch). Compare with human-human kappa. |
| Mean per-label kappa (multi-select) | Binary kappa per allowed value, averaged over values that either rater used | Exact-set accuracy is harsh for multi-select; this credits partial agreement |
| Mean Jaccard (multi-select) | Overlap of AI and gold value sets | Partial-credit view |
| Quote verification rate | Share of AI quotes found verbatim in the cited chunk | Should be close to 100%; anything else means the model paraphrased or cited the wrong chunk |
| Citation precision (Q&A) | Share of citations whose chunk supports the citing sentence (lexical verifier) | Detects fabricated or misplaced citations; does not detect meaning reversals |
| Correct abstention rate | Share of unanswerable questions where the system abstained | Low values mean the system answers when it should not |
| False abstention rate | Share of answerable questions where the system abstained | High values mean the system is unhelpfully cautious or retrieval failed |
| Key-fact accuracy | Share of answerable questions whose answer contains all expected key terms | A rough correctness check; review failures by hand |
| Recall@k / MRR@10 | Share of questions with a relevant chunk in the top k / mean reciprocal rank of the first relevant chunk | Retrieval ceiling for Q&A and coding |

### Sample size and uncertainty

With 20 documents, a kappa of 0.60 has a 95% confidence interval roughly +/-0.2 or wider, and variables with rare values (for example `equity_provisions = yes`) are unstable. Report confidence intervals (bootstrap over documents) when presenting results, and do not compare models on differences smaller than the interval width. Expand the gold set before drawing conclusions about individual variables.

### Known biases in the current draft sets

- Retrieval questions were written by someone who had seen the target passages, so they share vocabulary with them; this favors BM25 over embeddings. Add questions written by analysts who have not seen the passages.
- The starter gold draft and the coding prompt share an author (an AI assistant). Agreement between the drafts and a Claude model would partly measure AI-AI agreement. This is why verified human coding is required.

## 6. Acceptance criteria template

Fill these in before looking at live-model results.

| Criterion | Threshold (example) | Program's threshold |
|---|---|---|
| Kappa per variable vs. adjudicated gold | >= 0.60, and >= human-human kappa minus 0.10 | [ ] |
| Quote verification rate | >= 98% | [ ] |
| Q&A citation precision | >= 95% | [ ] |
| Correct abstention | >= 90% | [ ] |
| Retrieval recall@10 | >= 90% | [ ] |
| Review time per document vs. manual coding | at least 30% less | [ ] |

Variables that fail stay **manual-only** (shown to reviewers as suggestions with no pre-filled value) until they pass.

## 7. Ongoing monitoring

- Re-run `make eval` on every change to model, prompt, codebook, chunker, or retrieval settings (CI runs the offline version on every pull request).
- Track review outcomes monthly from the audit trail: rejection and edit rates by variable, and the most common reasons.
- Second-review 10% of accepted codes to measure reviewer drift.
- Refresh the corpus on a schedule; new documents need new gold examples if they introduce new document types.
