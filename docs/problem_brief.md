# When later evidence changes an invoice decision

## 1. Problem and boundary

An accounts payable analyst can approve an invoice against the purchase order and receiving record available today, then learn tomorrow that the order was amended, the receipt count was corrected, or the supplier issued a credit. The original decision may no longer be valid. The problem here is **keeping payable decisions consistent with changing purchase-to-pay evidence and conditions**.

The intended user is an analyst at a mid-size company processing hundreds of vendor PDFs monthly. The time cost is repeated document reading and rechecking; the error cost is approving more units or money than the company can support with an order and receipt. No measured monetary savings are claimed. **Out of scope:** the prototype is limited to one Indian-rupee PO configuration with synthetic suppliers and invoices; it does not send payments, decide tax law, authenticate suppliers, or reconcile bank transactions.

The surprising design observation is that an invoice decision is not permanent merely because its arithmetic was correct. It is a conclusion over a **version of evidence**. A later receiving correction can turn a prior approval into a review item; a genuine credit can release PO capacity for another invoice. This gives the system a useful job beyond extracting invoice fields.

## 2. Solution and architecture

```text
Invoice PDF → digital text / local OCR → structured fields + source quotes
                                                 ↓
Vendor register + PO + receipts + prior invoices + credits
                                                 ↓
                         deterministic decimal checks
                                                 ↓
                 approve / review / reject + reasons
                                                 ↓
       versioned history ← optional rerun or new evidence
```

The PDF reader handles digital text and falls back to a pretrained OCR model for scanned pages. An optional language model can propose fields from unfamiliar layouts, but each accepted value must be present in the document text. Matching a supplier or line description is probabilistic; uncertain matches go to review. Money, quantities, duplicate identity, tax calculations, PO limits and receipt balances use explicit rules and decimal arithmetic. The model is never asked to make a payable decision.

Every decision stores extracted field quotes, document page numbers, linked PO/receipt identifiers, formula inputs, the condition version, reasons and a revision history. The original synthetic PO PDF is visible beside the decision. The Conditions tab lets a reviewer edit order capacity, supplier approval, receipt requirements and tolerances. Saving a version makes it active for new invoices while earlier decisions keep their original policy. The reviewer can separately preview and rerun historical invoices under the saved conditions; a repeated unchanged rerun creates no new revisions. The reference records begin in a small JSON register; condition versions, evidence and decisions live in SQLite. A graph database, autonomous agents and a vector index would add more moving parts without improving these bounded checks.

**Uncertainty and mistakes:** human review is required when fields are missing, OCR confidence is low, a PO or item link is ambiguous, the configured tax calculation differs, or received units fall short. A reviewer must upload a supporting PDF, identify themselves and explain a receipt correction or credit event before replay. The app checks that the reference and entered values appear in the PDF and retains its hash. That UI action is an attestation in the prototype; production must verify authenticity and enforce approval authority.

## 3. Proof and failure analysis

The prototype processes 13 self-created invoice PDFs, including one rasterized scan. The observed initial status matched the expected status for all 13. Saving a revised freight PO left earlier decisions untouched, while a new invoice used the new version. An explicit rerun then changed one rejection to review; repeating the rerun made no further change. A documented receipt correction then changed that invoice to approval. Separately, a credit changed a PO overspend rejection to approval, and a corrected receipt reopened earlier approvals for review. The observed results and issue codes are in `reports/evaluation.json`; invoice, PO and evidence PDFs and the generating script are included.

These cases prove the **workflow runs**, not that extraction is accurate on the population of vendor invoices. The layouts come from one generator and have clean typography. The bundled-line case has no verifiable quantity or unit price, so the system routes it to review. A real handwritten, multilingual, rotated, or badly scanned invoice may fail earlier. We would measure field-level accuracy and false approval rate on a diverse, manually labeled document set before expanding automation.

**Alternatives considered and rejected:** rules-only text matching can handle the known templates but fails when layouts or wording change. A single language-model call could read more formats, but would blur source evidence, arithmetic and policy. AI is useful here for document perception and candidate extraction across unfamiliar layouts; exact calculations and the final decision remain inspectable. The optional model path is deliberately nonessential: the local OCR and review route work without an API key.

## 4. Risks and next decision

**Wrong answers:** An OCR digit error or a model-proposed field can create an incorrect decision. Source text checks, confidence thresholds and decimal validations reduce this risk, but matching a wrong yet plausible number remains possible. The weakest point is extraction from unfamiliar tables. **Outdated evidence:** A condition edit applies forward unless a reviewer chooses historical replay; reviewed evidence corrections replay earlier decisions under their assigned condition versions. The editable PO is a scenario tool, not proof of an authorized amendment. Production would need effective dates, signed approvals and a controlled amendment process. **Confidential data:** The default path runs locally on synthetic data; optional external model calls send invoice text and must be disabled for confidential data without authorization. **Liability:** The status is a recommendation under configured PO policy. A qualified human owns payment and tax treatment.

The next investment should be a blind evaluation on diverse public or consented PDFs, with field-level labels, false approval tracking and a reviewer workflow for evidence attachments. Only after that should the system add authentication, durable shared storage, effective-date logic, more currencies, line-level receipts and tax rules for other jurisdictions.
