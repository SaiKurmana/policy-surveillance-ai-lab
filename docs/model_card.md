# Model card: Policy Surveillance AI Lab

> **Template status.** This card describes the system as built in this repository. Agencies adapting it should update every version field when anything changes and keep old versions of this card. Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or any government agency. Uses only public-domain documents. AI outputs require human review.

## 1. System overview

The system is a pipeline, not a single model. Each component is versioned separately and recorded with every output.

| Component | Default | Version recorded as |
|---|---|---|
| Generative model (Q&A, coding) | Anthropic Claude `claude-opus-5-5`, effort `medium` (configurable via `POLICYLAB_MODEL`, `POLICYLAB_EFFORT`) | `model`, `served_model` |
| Offline baseline (demo mode, CI) | `extractive-keyword-baseline-v1` (no ML; sentence extraction and codebook cue counting) | `model` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) | `data/index/meta.json` |
| Keyword retrieval | BM25 (k1 = 1.5, b = 0.75), fused with embeddings by reciprocal rank fusion (k = 60) | code version |
| Q&A prompt | `policylab/prompts/qa_v1.md` | `prompt_version` + SHA-256 prefix |
| Coding prompt | `policylab/prompts/coding_v1.md` | `prompt_version` + SHA-256 prefix |
| Codebook | `codebook/policy_codebook.yaml` v1.0.0 | `codebook_version` |
| Chunker | `policylab/chunking.py` v1 (target 220 words, max 360) | `chunker_version` in manifest |

### Provider interface

`policylab/llm/` defines one method, `structured(system, user, output_model, task)`, that returns a pydantic-validated object. The Anthropic provider uses structured outputs (JSON schema generated from the pydantic models) and then validates the response again with pydantic. To swap models, implement the same method for another provider and register it in `get_provider()`.

### Refusals and fallbacks

Requests opt into the API's server-side fallback (`fallbacks: "default"`), so if a safety classifier declines a request, the API may retry it on a recommended fallback model. The model that actually answered is stored as `served_model` and shown to reviewers. If the whole chain declines (`stop_reason = refusal`) or the output is truncated, the system raises an error instead of using a partial answer.

## 2. Intended use

See [responsible use](responsible_use.md). In short: drafting evidence-linked answers and codes for **human review** over **public** policy documents.

## 3. Inputs and outputs

**Inputs:** retrieved passages from public Federal Register documents (no user data beyond the question text and reviewer ID).

**Q&A output (`GroundedAnswer`):** `insufficient_evidence` flag, a list of sentences each with cited chunk IDs, and a description of missing information.

**Coding output (`DocumentCoding`):** for each codebook variable: `status` (`coded` or `insufficient_evidence`), `values`, an exact `supporting_quote`, the `chunk_id` containing it, a self-reported `confidence` (0-1), and a short `rationale`.

### What the model sees during coding

Long rules do not fit a useful prompt, so coding uses the document's first 6 chunks (header, SUMMARY, DATES, ACTION) plus the top 4 chunks for each variable's retrieval query, up to 45 chunks. The selected chunk IDs are stored with the run so reviewers can see exactly what the model saw.

## 4. Automatic checks applied to every output

| Check | Where | Catches |
|---|---|---|
| Schema validation (pydantic) | all outputs | malformed JSON, missing fields, out-of-range confidence |
| Codebook validation | coding | values not in the codebook, multiple values for single-select, bad dates, missing variables |
| Quote check | coding | quote not found verbatim in the cited chunk (`not_found`), chunk the model was not shown (`invalid_chunk`) |
| Citation verifier | Q&A | uncited sentences, invented chunk IDs, low word overlap with the cited chunk, numbers not present in the cited chunk |

## 5. Evaluation

See [evaluation protocol](evaluation_protocol.md) and `eval/results.md`. **Current status:** the committed results were produced by the offline baseline against an unverified starter gold standard. No live-model results are reported yet; none should be cited until a human-verified gold standard exists and `make eval` is run with `--provider anthropic`.

## 6. Known and expected failure modes

These are documented from the design and from the baseline runs. Update this list from reviewer rejection reasons.

| Failure mode | Example | Mitigation |
|---|---|---|
| Commenter vs. agency confusion | Reporting "a State agency recommended 8 or 9 grams" as the rule's limit | Prompt rule 5; reviewer checks source; a known weakness of the extractive baseline, visible in `data/demo_outputs/` |
| Retrieval miss on long rules | The effective date for a phased rule is in a later section | Head chunks always included; abstention allowed; recall@k tracked |
| Over-broad multi-select codes | Every population mentioned in a 159-page preamble gets coded | Decision rule: main provisions only; exact-set accuracy and per-label kappa reported separately |
| Legal-force ambiguity | Deregulatory rules that permit rather than require; voluntary claims with binding criteria; executive orders | Flagged in gold notes; reviewer judgment required |
| Effective vs. compliance dates | Taking a compliance date as the effective date | Codebook decision rule; date accuracy reported separately |
| Out-of-scope questions answered anyway | The baseline answers a question about Canada using U.S. passages | Abstention metrics on unanswerable questions; verifier does not catch this, so human review is required |
| Lexical verifier false positives | A sentence that copies words but reverses the meaning passes | Documented limitation; human review |
| Paraphrased quotes | Model "cleans up" a quote so it no longer matches | `quote_check = not_found` shown to reviewers |
| Calibration | Self-reported confidence is not a probability until calibrated against verified gold | Report accuracy by confidence band once gold is verified |

## 7. Ethical and equity considerations

- Equity provisions are coded explicitly so the system can surface them, but a lexical cue such as "equity" does not by itself justify a "yes" code; boilerplate civil rights analyses are excluded by decision rule.
- Federal Register coverage is federal only. State and local policies, which often matter most for obesity prevention, are out of scope for this corpus.
- The corpus over-represents USDA and FDA rulemaking because those agencies publish long nutrition rules; physical activity policy appears mostly as notices.

## 8. Versions

| Date | Change |
|---|---|
| 2026-11-05 | Initial version: codebook 1.0.0, prompts qa_v1 / coding_v1, chunker v1, 61-document corpus. |
