# Responsible use policy

> **Template status.** Written for the Policy Surveillance AI Lab, a portfolio project. Agencies adapting it should replace bracketed items, route it through their own legal, privacy, and IT governance review, and assign named owners. Independent portfolio project. Not affiliated with, endorsed by, or produced for the CDC or any government agency. Uses only public-domain documents. AI outputs require human review.

## 1. Purpose

This tool helps public health analysts **find, read, and code** public policy documents (nutrition, physical activity, obesity prevention) faster and more consistently. AI **proposes** answers and codes with evidence attached; a **trained human decides** what is recorded.

## 2. Intended uses

| Use | Conditions |
|---|---|
| Locating passages in public regulatory documents | Always open the cited source before relying on a passage. |
| Drafting answers to factual questions about selected documents | Answers must be grounded in user-selected documents and carry a citation on every sentence. |
| Pre-coding documents against the policy codebook | Every AI code goes through the review queue (accept, edit, or reject, with a reason for edits and rejections). |
| Measuring AI-vs-human agreement | Use the evaluation protocol; report verified gold-standard results only. |
| Training new coders on the codebook | Compare a trainee's codes with reviewed codes. |

## 3. Out-of-scope uses (do not use the tool for these)

- **Legal advice or legal interpretation.** Coded fields such as "mandatory vs. voluntary" describe documents for surveillance; they are not legal determinations.
- **Compliance or enforcement decisions** about any school, retailer, restaurant, program operator, or person.
- **Any data about individuals.** The tool must not ingest protected health information (PHI), personally identifiable information, or confidential, pre-decisional, or internal agency material.
- **Publishing AI output without human review**, including in reports, dashboards, briefings, or public statements.
- **Answering from outside the corpus.** If the system says evidence is insufficient, do not re-prompt until it guesses.
- **Ranking or scoring jurisdictions or programs** for funding or penalties.
- **Clinical or individual health guidance.**

## 4. Human review requirement

1. Every AI code is **pending** until a named reviewer records `accept`, `edit`, or `reject`. Pending codes are not data.
2. Edits and rejections **require a reason**. Reasons are how codebook gaps and model failure modes are found.
3. Reviewers **open the source passage** for any code with confidence below 0.7, any quote check other than `exact`, and any variable marked high-stakes by the program (by default `legal_force`, `effective_date`, `equity_provisions`).
4. Q&A answers with any sentence flagged `unsupported`, `uncited`, or `invalid_citation` must not be reused until a human has fixed or removed that sentence.
5. Reviewers record their own ID; shared accounts are not allowed. The audit trail is append-only.
6. At least **10% of accepted codes** per review cycle get a second independent review to monitor reviewer drift (see the evaluation protocol).

## 5. Known limitations users must understand

- **Retrieval can miss the key passage.** Long rules (150+ pages) are split into thousands of chunks; the model only sees the top passages. "Insufficient evidence" may mean the passage was not retrieved, not that it does not exist.
- **The citation verifier is lexical.** It catches invented chunk IDs, wrong-passage citations, and changed numbers. It does **not** catch a sentence that reuses the source's words but reverses its meaning, or a correct quote taken out of context (for example, a commenter's request presented as the agency's decision).
- **Preambles are not rules.** Federal Register preambles summarize public comments, alternatives considered, and economic analyses. Models can confuse these with what the agency adopted.
- **Documents change.** Rules are amended, delayed, or vacated after publication. The corpus is a dated snapshot; the tool does not know about later actions unless they are in the corpus.
- **The demo mode is not AI.** Unless live mode is unlocked (API key plus the live mode password), the app uses an offline keyword/extractive baseline. Its output is labeled and exists to demonstrate the workflow.
- **Agreement metrics depend on the gold standard.** Until a human-verified gold standard exists, reported agreement numbers are pipeline checks, not evidence of accuracy.

## 6. Accountability

| Role | Responsibility | Owner |
|---|---|---|
| Program lead | Approves intended uses and the codebook; signs off on evaluation before wider use | [name] |
| Reviewers | Review AI codes; record reasons; flag codebook gaps | [names] |
| Technical owner | Maintains corpus, prompts, model versions, and evaluation runs | [name] |
| Privacy/IT security | Confirms no PHI or confidential inputs; approves hosting and API use | [office] |

## 7. Change control

A change to the **model**, **prompt**, **codebook**, **chunker**, or **retrieval settings** requires re-running the evaluation (`make eval`) on the verified gold standard and recording the results before the change is used for production coding. Version identifiers for all five are stored with every AI code.

## 8. Reporting problems

Record incorrect outputs as a review rejection with a reason. Systematic failures (for example, a variable that is wrong more than 20% of the time) go to the technical owner, who documents them in the [model card](model_card.md) under known failure modes.
