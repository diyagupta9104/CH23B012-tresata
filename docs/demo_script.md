# Five-minute live demo route

In **History & audit → Clear history / start fresh**, check **Also restore the original demo conditions**, type `CLEAR`, and clear saved demo activity. Then follow the **Test guide** checklist.

| Time | Action | Show |
|---|---|---|
| 0:00–0:35 | Explain the problem: invoice decisions can change when conditions or evidence changes. | The five tabs and the sample test plan. |
| 0:35–1:15 | Process `04_freight_first.pdf`. | Live extraction stages, source quotes, original PO-1002 PDF, 200 ordered and received pallets. |
| 1:15–1:50 | Process `05_freight_overspend.pdf`. | 225 cumulative pallets and ₹265,500 gross exceed the initial PO limits; reject. |
| 1:50–2:45 | In **Conditions & replay**, change PO-1002 ordered quantity from 200 to 250 and preview. | Before → after shows reject → review; PO capacity and receipt evidence are distinct. |
| 2:45–3:20 | Enter reviewer and reason; save the condition. | The new version applies to future invoices; run 05 stays rejected. |
| 3:20–3:45 | Preview and choose the optional historical rerun. | Run 05 changes to review; the previous rejection remains in **History & audit**. |
| 3:45–4:25 | In **Later evidence**, correct `GRN-1002` to 250 using `receipt_amendment_250.pdf`. | Document-backed receipt correction moves run 05 to approve. |
| 4:25–5:00 | Process `11_scanned_invoice.pdf`, or show `13_bundled_line.pdf` if time. | Actual OCR or a review decision when a line cannot be verified. |

For other cases, use [testing_guide.md](testing_guide.md). The recording should show actual execution, a happy path, a failure and the replay. A public link and screen recording require the owner's accounts; no repository or app has been pushed or published by this workflow.
