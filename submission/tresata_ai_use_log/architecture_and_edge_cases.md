# Critical questions and edge-case record

## Critical design questions

| Question | Decision | Reason |
|---|---|---|
| Is one model call enough? | No. Use extraction/OCR, bounded matching, deterministic rules, and human review. | A single call would mix uncertain perception with exact financial checks. |
| Which outputs must be exact? | Money, tax arithmetic, quantities, duplicate identity, purchase-order limits, and receipt balances. | These values must be reproducible and auditable. |
| Which outputs may be probabilistic? | Candidate field extraction and similarity-based links. | Uncertainty is acceptable only when it routes to review and the value is source-checked. |
| Where does knowledge live? | Synthetic reference records, versioned conditions, code rules, and source documents. | The model should not be the system of record for changing policy or evidence. |
| Can an auditor trace the answer? | Yes, through source quotes, page references, hashes, linked records, formulas, reasons, and revisions. | Each decision needs an inspectable evidence trail. |
| What is the weakest point? | Extraction from unfamiliar tables, poor scans, handwriting, multilingual documents, or plausible OCR errors. | The prototype therefore uses confidence gates and human review. |
| What was rejected? | A rules-only filename workflow, an unconstrained one-call approval model, a graph database, autonomous agents, and a vector index. | They either failed on unfamiliar inputs or added complexity without improving bounded checks. |

## Edge cases deliberately tested

| Case | Expected handling | Observed evidence |
|---|---|---|
| Split order | Track cumulative quantity and gross across invoices. | The second invoice consumes the remaining balance. |
| Duplicate invoice | Reject as duplicate and retain the earlier decision. | Duplicate scenario returned a rejection. |
| PO overspend | Reject when cumulative quantity or gross exceeds the active limit. | Freight overspend scenario returned a rejection. |
| Tax-inclusive invoice | Reconcile included tax without double-counting it. | Tax-inclusive scenario returned approval. |
| Missing PO reference | Do not guess an order. | Routed to review. |
| Missing invoice number | Treat a critical missing identifier as reviewable. | Routed to review. |
| Scanned invoice | Use local OCR and retain confidence information. | The OCR scenario returned approval. |
| Arithmetic mismatch | Reject when stated gross does not reconcile. | Arithmetic-error scenario returned a rejection. |
| Unapproved supplier | Do not allow approval merely because the arithmetic works. | Unapproved-supplier scenario returned a rejection. |
| Bundled line | Do not infer missing quantity or unit price. | Routed to review. |
| Receipt correction | Require evidence, reviewer identity, and an explicit replay. | A prior decision changed after corrected receiving evidence. |
| Credit note | Reduce cumulative consumption only after source-backed evidence is recorded. | The credit route changed the affected decision. |
| Repeated replay | Avoid creating a new revision when nothing changed. | Repeated unchanged replay revised zero records. |

## Human contribution

The distinctive insight was treating a payable decision as a conclusion over a version of evidence, not as a permanent truth. That led to versioned conditions, explicit replay, later-evidence events, and a separation between purchase-order capacity and receiving coverage.
