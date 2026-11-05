# Data governance

> **Template status.** Describes the data handled by this repository. Agencies adapting it should add their records schedule, system of records determination (if any), and hosting authorization. Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or any government agency. Uses only public-domain documents. AI outputs require human review.

## 1. Data inventory

| Data | Source | Sensitivity | Location | Retention |
|---|---|---|---|---|
| Document metadata (number, title, agency, dates, URLs, topics) | Federal Register API v1 | Public | `data/corpus_manifest.csv`, `data/snapshot/documents.jsonl` (committed) | Indefinite, versioned in git |
| Discovery query log (query, hit count, run date) | Federal Register API v1 | Public | `data/corpus_queries.json` (committed) | Indefinite |
| Full text, chunked | GPO GovInfo HTML edition of each Federal Register document | Public | `data/snapshot/chunks.jsonl.gz` (committed, about 2.2 MB) | Indefinite |
| Raw downloads (API JSON, GovInfo HTML) | Same as above | Public | `data/raw/` (git-ignored cache) | Delete any time; rebuilt by `make corpus` |
| Embedding index | Computed locally | Public-derived | `data/index/` (git-ignored) | Rebuilt by `make index` |
| AI codes and review decisions | Generated in the app | Internal work product; contains reviewer IDs | `data/lab.duckdb` (git-ignored) | Set by the program; see section 5 |
| Gold-standard codes | Human coders | Internal work product | `eval/gold/gold_codes.csv` (committed) | Indefinite, versioned |
| Questions typed into Ask | Users | May reveal work topics | Sent to the model provider when live AI is on; not stored by the app | Not retained by the app |

**Never collected:** protected health information, personally identifiable information about the public, confidential or pre-decisional agency documents, non-public comments, or data from sites whose terms prohibit automated access.

## 2. Sources and licensing

- **Federal Register documents** are works of the U.S. Government and are in the public domain in the United States (17 U.S.C. 105). Some documents quote or reproduce third-party material (for example, copyrighted figures or standards incorporated by reference); those items keep their original status. This project stores text only, not images.
- **Federal Register API** (`https://www.federalregister.gov/api/v1/`): no key required. Used for discovery queries and document metadata.
- **GovInfo** (`https://www.govinfo.gov/content/pkg/FR-<date>/html/<document_number>.htm`): the Government Publishing Office's official edition. Used for full text.
- **Why not FederalRegister.gov full-text pages?** As of the corpus build date, FederalRegister.gov limits programmatic access to its developer APIs and shows automated clients a CAPTCHA page on its full-text URLs. This project respects that: it never requests those pages and never attempts to bypass the check.
- **Crawling etiquette:** a descriptive User-Agent, at most about 1.6 requests per second, retries with backoff, and a local cache so documents are fetched once.

## 3. Provenance and integrity

Every document row in the manifest records:

- `document_number`, `title`, `agency`, `document_type`, `publication_date`, `effective_on`, `citation`
- `url` (FederalRegister.gov page), `pdf_url` and `full_text_url` (GovInfo)
- `access_date` (when the text was downloaded)
- `topics` (which curated topic lists include it) and `found_by_query` (which discovery queries returned it)
- `text_sha256` (hash of the cleaned text) and `chunker_version`

The builder fails if a discovery query returns zero documents, if the API returns a different document number than requested, or if the GovInfo text does not mention the document number.

### Curation

Federal Register keyword search is noisy, so the corpus is a **curated subset** of the query results. The topic file `corpus/topics.yaml` lists each topic's query, its inclusion and exclusion criteria, and the selected document numbers. Curation choices are visible in git history.

## 4. Chunk identifiers

Chunk IDs have the form `<document_number>:p<first>-<last>`, where the numbers are zero-based paragraph indices in the cleaned text. They are stable as long as the source text and `chunker_version` do not change. If either changes, `text_sha256` or `chunker_version` in the manifest changes too, and previously stored citations should be re-validated (the evaluation does this for the gold file).

## 5. Review data (DuckDB)

- Tables: `coding_runs`, `ai_codes`, `review_decisions`. Decisions are **append-only**; corrections are new rows.
- Reviewer IDs are the only personal data. Use role-based or pseudonymous IDs where possible.
- **Retention template:** keep review decisions for [N years / per records schedule]; keep coding runs as long as their decisions are retained; delete local copies when a reviewer leaves the project.
- **Hosting note:** on ephemeral hosts (for example Streamlit Community Cloud) the DuckDB file is lost on restart. For real use, point `POLICYLAB_DB` at durable, access-controlled storage and back it up.

## 6. Third-party processing

When live AI is enabled, retrieved public passages, the user's question, and the codebook are sent to the Anthropic API. No PHI or confidential material should ever be in those inputs (section 1). Agencies must confirm that their use of any external model API is authorized under their own policies before enabling live AI.

## 7. Secrets

No API keys or passwords are stored in the repository. The app reads `ANTHROPIC_API_KEY` and `LIVE_MODE_PASSWORD` from the environment or from Streamlit secrets (`.streamlit/secrets.toml`, which is git-ignored). CI uses the offline baseline and has no key.

A public deployment stays in demo mode by default. Live LLM mode turns on only when **both** secrets are set **and** the viewer enters the `LIVE_MODE_PASSWORD` value in the sidebar. A key without a password secret never enables live mode, so anonymous visitors cannot spend the operator's API budget. The password is compared in constant time and is not logged or written to the audit trail.
