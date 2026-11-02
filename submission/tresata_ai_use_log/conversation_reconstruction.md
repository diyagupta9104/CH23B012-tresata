## How to read this file

This is not a verbatim transcript. It separates exact wording from summaries so the record does not overclaim what can be recovered.

## Exact user wording available in the working conversation


The request was to inspect the assignment PDF and identify what was still missing for submission.

## Prompts preserved in the project’s AI-use draft

The project’s existing AI-use draft records these as representative prompts. They should be checked against the original chat export before being described as verbatim:

> from where are u planning to take the boiler plate and which ocr tool?

> our project should be unique ... figure out what else we can develop.

## Curated development sequence

### 1. Scope and problem selection

AI-assisted discussion explored finance workflow problems and helped compare possible directions. The chosen problem became invoice verification when supporting evidence changes after an earlier decision.

The important human contribution was narrowing the work to a bounded, auditable workflow rather than asking a model to make a payment decision.

### 2. Architecture questions

The design was challenged with questions about whether one model call was enough, which values had to be exact, where knowledge should live, how an auditor could trace an answer, and what would break first.

The resulting split was:

- PDF text extraction and local OCR for document perception.
- Bounded matching for supplier, purchase order, and item links.
- Decimal arithmetic and explicit rules for money, tax, quantities, duplicates, and receipts.
- Human review for missing, ambiguous, low-confidence, or contradictory evidence.
- Optional model assistance only for candidate extraction from unfamiliar layouts; never for the final financial decision.

### 3. Edge-case focus

The work deliberately expanded beyond a happy-path invoice. The test set covers split orders, duplicate invoices, freight overspend, tax-inclusive totals, missing purchase-order references, missing invoice numbers, scanned invoices, arithmetic errors, unapproved suppliers, and bundled lines without verifiable quantity or price.

The later-evidence workflow was added to test receipt corrections and credit notes. A saved condition change can be previewed, activated for future invoices, and explicitly replayed against historical decisions. Repeating an unchanged replay creates no additional revision.

### 4. Implementation and review

The application was implemented as a local Streamlit workflow with a SQLite audit store. It keeps source quotes, page references, hashes, calculation inputs, conditions versions, decision reasons, and revisions.

AI helped with brainstorming, implementation discussion, and inspection. The final design decisions came from checking the generated documents, the failure modes, and the need for reproducible financial calculations.

### 5. Submission review

The assignment requirements were compared against the repository. The written brief and one-page appendix exist. The remaining submission work is to personalize the appendix and attach the actual conversation export if available. 
