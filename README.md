# CH23B012-tresata

**Evidence Ledger — an evidence-aware invoice verification workflow**

Maintainer: **Diya Gupta** (`diya_gupta`)

Evidence Ledger is a runnable Streamlit application for checking invoice PDFs against purchase orders, receiving evidence, supplier status, prior invoices, and later corrections. It returns **approve**, **review**, or **reject** with reasons, calculations, source quotes, and an audit history.

## The problem

Accounts-payable analysts often decide from a changing set of PDFs. An invoice may look supportable today, then become questionable after a receipt correction, purchase-order amendment, duplicate invoice, or supplier credit. The prototype treats the decision as a conclusion over a version of evidence and keeps the earlier decision visible when later evidence changes the result.

This repository is an independent implementation of the finance problem defined in the assignment. The issue, architecture, test cases, and synthetic documents were developed from the problem analysis and are not copied from an external company or product.

## What it does

- Extracts fields from digital PDFs and uses local OCR for image-only scans.
- Matches suppliers, purchase orders, and line items with bounded similarity checks.
- Uses decimal arithmetic and explicit rules for quantities, prices, tax, totals, duplicates, PO limits, and receipts.
- Routes missing, ambiguous, low-confidence, or contradictory evidence to human review.
- Stores source quotes, page references, hashes, linked records, formulas, condition versions, reasons, and revisions.
- Supports source-backed receipt corrections and credit notes followed by explicit replay.
- Includes 13 synthetic invoice cases and a broader policy/event combination suite.

The optional language-model path can propose candidate fields for unfamiliar layouts. It cannot calculate money, approve an invoice, or replace deterministic checks.

## Repository layout

```text
CH23B012-tresata/
├── app.py
├── engine/                    PDF extraction, OCR, rules, state, and replay
├── data/reference.json         Synthetic suppliers, orders, receipts, and policy
├── samples/                   13 synthetic invoice PDFs
├── sample_orders/             Synthetic purchase-order PDFs
├── sample_evidence/           Synthetic receipt and credit evidence
├── scripts/                   Sample generation and evaluation scripts
├── reports/                   Observed evaluation results
├── docs/                      Brief, appendix, testing, and demo notes
└── submission/                Assignment AI-use log package
```

## Run locally

Python 3.12 is recommended.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501`. No API key is required for the standard workflow or OCR sample.

## Test evidence

The 13-case evaluation covers standard invoices, split orders, duplicates, overspend, tax-inclusive totals, missing identifiers, OCR, arithmetic errors, unapproved suppliers, and bundled lines. The later-evidence routes cover receipt corrections, credits, condition versions, historical replay, and repeat replay behavior.

- `reports/evaluation.json` — observed 13-case results.
- `reports/combinations.json` — policy, replay, evidence, and invalid-input checks.
- `docs/testing_guide.md` — repeatable UI test instructions.
- `docs/problem_brief.md` — problem, architecture, proof, failure analysis, and risks.
- `docs/ai_use_appendix.md` — AI-use disclosure source.
- `docs/assignment_requirements.md` — requirement-by-requirement submission checklist.

## Submission package

The assignment package is organized as follows:

1. **Written brief:** `docs/problem_brief.pdf` — maximum four pages.
2. **AI-use appendix:** `docs/ai_use_appendix.pdf` — one page covering AI help, rejected suggestions, candidate decisions, and one defensible design choice.
3. **Prototype link:** this repository is optional; if shared, the README and `docs/testing_guide.md` explain how to run and test it.
4. **AI conversation logs:** the assignment requires the actual AI conversation export or archive. `submission/tresata_ai_use_log.zip` contains supporting project AI-use material; attach the platform export as the authoritative transcript.

The full requirement mapping is in `docs/assignment_requirements.md`.

## Scope and limitations

This is a synthetic-data prototype, not a payment system or legal/tax advice. It does not claim real-world extraction accuracy, authentication, role-based approval authority, document retention, bank reconciliation, or production-grade multi-user storage.

## Ownership

This project is maintained by **Diya Gupta**.
