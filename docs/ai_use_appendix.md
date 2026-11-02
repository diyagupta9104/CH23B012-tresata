# AI-use appendix — candidate review draft

This page should be checked and personalized by the candidate before submission. It is intentionally honest about what the project record can establish.

**Where AI helped.** AI-assisted discussion compared the three operational problems and the finance assignment, researched reusable invoice/OCR software, and helped implement and inspect the prototype. Local OCR is used at runtime for scanned PDFs. An optional language model proposes missing fields on unfamiliar layouts, with source-text checks; it never calculates a payable decision. Representative prompts from the recorded conversation include: “from where are u planning to take the boiler plate and which ocr tool?” and “our project should be unique ... figure out what else we can develop.” The full conversation should be exported separately.

**What was rejected or corrected.** An initially considered invoice repository was found to base active matching on filename fragments and to leave normalized invoice/PO records empty. It was rejected after source inspection because that would not process unfamiliar PDFs honestly. A one-call model decision was also rejected: source links, arithmetic and changing PO balances require inspectable state and exact calculations.

**What came from the candidate.** The candidate explicitly chose one shared project, insisted that it cover both problem statements end to end, asked for an existing invoice base plus OCR to minimize code, and required a distinct contribution with no hiring identity in the product code. Before submitting, add one personal insight or trade-off you can explain from your own work with the documents or prototype: **[candidate to add]**.

**One part to defend without AI.** Suggested choice: explain why cumulative gross and quantity are recalculated after every credit or receipt correction, and why a received-quantity shortfall requires review. Use this only if you can personally walk through the sample numbers and revision history during the interview.
