# Test the PDF workflow

Open [http://localhost:8501](http://localhost:8501). Use **Test guide** for the in-app checklist. The outcomes below assume empty history and the initial conditions.

## Start fresh in the app

1. Open **History & audit** → **Clear history / start fresh**.
2. For the baseline results in this guide, check **Also restore the original demo conditions**. Type `CLEAR` and select **Clear saved demo activity**. Leave that checkbox off when you want to keep your active conditions for the next invoices.
3. Check that the sidebar shows `0 invoices` and `Conditions v1`. The invoice, PO and evidence sample PDFs remain available.

This removes saved invoice runs, audit revisions and evidence events. Condition edits are removed only when you select the reset checkbox. Sample PDFs stay available. Do this between independent scenarios; repeating a PDF without clearing can trigger a duplicate decision.

## Check each app option

| Where | What to do | What to check |
|---|---|---|
| **Test guide** | Open the 13-PDF table and **How to check every tab**. | The test order and expected statuses are visible in the app. |
| **Process invoice: sample** | Select `01_standard.pdf`, then **Run invoice checks**. | Processing stages appear; result is approve. |
| **Process invoice: upload** | Clear history, upload `samples/01_standard.pdf` from your computer, then run. | Same approve result as the sample selector. Uploaded files take priority if both are set. |
| **Decision panel** | Open the result for 01. | Supplier, PO, invoice total, PO and receipt checks appear. Expand the breakdown and sources for details. |
| **Decision export** | Select **Download decision JSON**. | The file contains the status, reasons, calculations and conditions version. |
| **Conditions: PO** | After 04 and 05, change PO-1002 quantity to 250. | Draft subtotal and gross cap update; preview shows 05 reject → review. |
| **Conditions: draft preview** | Select **Preview possible impact on past invoices**. | Before/after table appears; it writes no decisions. |
| **Conditions: save** | Enter reviewer and reason under **Save changes**, then **Save and activate changes**. | Conditions version increments. Processing is blocked while draft edits are unsaved; old decisions keep their original status and version. |
| **Conditions: optional rerun** | Select **Preview rerun with saved conditions**, enter a reviewer and reason, then **Rerun history using saved conditions**. | Earlier decisions update only now; a second identical rerun revises zero records. |
| **Conditions: vendor** | On a fresh run, process 01; turn off Northstar's approved switch and preview. | Invoice 01 changes from approve to reject. Apply only if you want that scenario saved. |
| **Conditions: receiving** | After 04 and 05, set PO-1002 quantity to 250 and turn off **Require receiving evidence**; preview. | Invoice 05 can approve without a 250-unit receipt. Turn the switch back on for the documented three-way match route. |
| **Conditions: tolerances** | Expand **Matching and tolerance settings**; change one number and preview. | The draft change is shown; the table tells you whether any recorded decision changes. Restore it or apply with a reason. |
| **Conditions: rules and versions** | Open **Complete rule catalog** and **Saved version details**. | Fixed safeguards and editable settings are listed; saved versions show reviewer, reason and values. |
| **Later evidence: receipt** | Use the 250-unit receipt route below. | Run 05 changes review → approve; the evidence log retains the PDF text, hash and download. |
| **Later evidence: credit** | Use the credit route below on a fresh run. | Run 05 changes reject → approve after the credit on run 04. |
| **History & audit** | Filter approve/review/reject; inspect a run; expand **Every decision version** and **Original PDF text**; download audit JSON. | Filtered runs, earlier decisions and source data remain inspectable. |
| **Clear history** | Type `CLEAR` and clear after testing. | Runs and events disappear; active conditions stay saved. Check the reset option to return to version 1. |

For an OCR-specific rule check, process `11_scanned_invoice.pdf`, inspect its OCR confidence in **Calculation trail and PDF quotes**, then raise the OCR confidence threshold above that value in **Conditions & replay** and preview. The result should move to review. Restore the threshold afterward.

### Check the condition settings one at a time

Use **Clear history** between these independent scenarios. A draft preview is enough to check possible impact; save only when you want the new version active for future invoices. Rerun history separately when you want to change past decisions.

| Setting | Example check |
|---|---|
| Ordered quantity | Process 04 and 05; raise PO-1002 from 200 to 250. Run 05 previews reject → review. |
| Unit price | Process 04; lower PO-1002's unit price from 1000 to 900. The invoice price differs from the order, so it previews review. |
| PO tax rate | Process 06; change PO-1003 from 18% to 19%. Its tax check previews review. |
| Require receiving evidence | Process 04 and 05; raise PO-1002 to 250 and turn off the receipt requirement. Run 05 previews approve. |
| Vendor approved | Process 01; turn off Northstar's approved switch. It previews reject. |
| OCR average and line minimums | Process 11; set both OCR minimums to 1.0. It previews review for low OCR confidence. |
| Arithmetic tolerance | Process 12; raise **Line and invoice arithmetic tolerance** from 0.01 to 1000 and preview. This intentionally weakens a safeguard; do not use it as a real payment policy. |
| PO gross tolerance | Process 04 and 05; change the PO gross overage tolerance and preview. This does not override a quantity excess, which remains a separate rejection. |
| Supplier and item match thresholds | Open the two matching threshold pairs and inspect the rule catalog. The supplied invoices use exact supplier and item names, so these thresholds need a custom PDF with a near-matching name to demonstrate a status change. |
| Tax and unit-price tolerances | Use the tax-rate and unit-price scenarios above, then raise their corresponding tolerance and preview again. The mismatch may stop routing to review once inside the tolerance. |

The preview table is the ground truth for each experiment: a rule edit may leave every status unchanged if another independent check still fails. The **New reasons** column shows the remaining blockers.

## Exact 225-unit test

1. Clear history and check **Also restore the original demo conditions**.
2. In **Conditions & replay**, select `PO-1002` and set **Ordered quantity** to **225**. The draft gross cap should be **₹265,500**.
3. Enter a reviewer and change reason, then click **Save and activate changes**. Check that the active conditions version becomes **2** and PO-1002 displays **225**. Until you save, **Run invoice checks** is disabled.
4. Process `04_freight_first.pdf`: **approve**.
5. Process `05_freight_overspend.pdf`: **review**, with **Receipt shortfall** as the only issue. Cumulative quantity is **225 / 225**, and cumulative gross is **₹265,500 / ₹265,500**. There should be no **PO exceeded** issue.
6. To complete the three-way match, in **Later evidence** add a receipt correction for `PO-1002`, `GRN-1002`, quantity **225**, using [receipt_amendment_225.pdf](../sample_evidence/receipt_amendment_225.pdf), a reviewer and note. Run 05 should become **approve**.

If run 05 still says **PO exceeded**, inspect **Active conditions** and the **ordered quantity** beside its decision. A version 1 decision with 200 ordered means the draft was not saved or the invoice was processed before the condition changed. An already processed invoice changes only after the optional historical rerun.

## Invoice PDFs

In **Process invoice**, choose each sample from the dropdown and select **Run invoice checks**. Inspect the decision reasons, extracted field quotes, original PO PDF, ordered and received quantities, cumulative totals, and audit version.

| Order | PDF | Expected | Check |
|---|---|---|---|
| 1 | `01_standard.pdf` | Approve | Supplier, PO and receipt link; tax and total reconcile. |
| 2 | `02_split_order.pdf` | Approve | A second invoice uses the remaining quantity on PO-1001. |
| 3 | `03_duplicate.pdf` | Reject | Same source PDF and invoice number as 01. |
| 4 | `04_freight_first.pdf` | Approve | 150 of PO-1002's initial 200 pallets billed. |
| 5 | `05_freight_overspend.pdf` | Reject | Cumulative 225 pallets and ₹265,500 gross exceed 200 and ₹236,000. |
| 6 | `06_tax_inclusive.pdf` | Approve | Tax and gross reconcile when tax is shown as included. |
| 7 | `07_missing_po.pdf` | Review | PO reference is absent. |
| 8 | `08_missing_number.pdf` | Review | Critical invoice number is absent. |
| 9 | `09_receipt_recheck.pdf` | Approve | Later receipt evidence can reopen this decision. |
| 10 | `10_unapproved_vendor.pdf` | Reject | Supplier is not approved. |
| 11 | `11_scanned_invoice.pdf` | Approve | The image-only PDF goes through local OCR. |
| 12 | `12_arithmetic_error.pdf` | Reject | Stated gross contradicts subtotal plus tax. |
| 13 | `13_bundled_line.pdf` | Review | Missing item quantity and unit price cannot be verified. |

These are functional checks on generated PDFs. They do not measure real-world extraction accuracy.

## Demonstrate why the PO and receipt are separate

For this route, use a fresh database and process only 04 then 05.

1. Open run 05 and download the original [PO-1002.pdf](../sample_orders/PO-1002.pdf). It says **200 pallets at ₹1,000**, and the app shows a **₹236,000 gross cap**. The original receipt confirms 200.
2. Open **Conditions & replay**, choose `PO-1002`, and change **Ordered quantity** from 200 to **250**. The subtotal updates to ₹250,000 and the gross cap to ₹295,000.
3. Select **Preview possible impact on past invoices**. Run 05 should show **reject → review** as a possible result. The order now covers 225 billed pallets, but the 200-pallet receipt does not. The preview writes nothing.
4. Enter a reviewer identifier and reason, then select **Save and activate changes**. Run 05 remains **reject**. Any newly processed invoice now uses the saved 250-unit order.
5. Select **Preview rerun with saved conditions**. Enter a reviewer and reason, then select **Rerun history using saved conditions**. Run 05 becomes **review** and gains a new revision in **History & audit**. Repeat the same rerun: it should revise zero records.
6. In **Later evidence**, choose **Receipt correction**, `PO-1002`, receipt `GRN-1002`, corrected quantity **250**, a note and reviewer, and [receipt_amendment_250.pdf](../sample_evidence/receipt_amendment_250.pdf). Save and replay. Run 05 should become **approve** with another audit version.

The PO edit is a synthetic scenario. For a real order, an authorized amendment would have to be verified and attached before using its new limit for payment.

## Alternative evidence routes

Use a fresh database for each route so one scenario does not change another's expected result.

- **Credit:** process 04 then 05. In **Later evidence**, choose **Credit note**, `PO-1002`, invoice 04, reference `CN-4101`, amount **59000**, quantity **50**, a note and reviewer, and [credit_note.pdf](../sample_evidence/credit_note.pdf). Run 05 should change from reject to approve because the credit reduces prior billed quantity and gross.
- **Receiving recheck:** process 06 then 09. Choose **Receipt correction**, `PO-1003`, `GRN-1003`, quantity **10**, a note and reviewer, and [receipt_correction.pdf](../sample_evidence/receipt_correction.pdf). The earlier approvals should change to review because billed chairs now exceed confirmed receipt.

For repeatable checks, run `scripts/evaluate.py` for all 13 PDFs and `scripts/verify_combinations.py` for the tested PO, receipt, credit, duplicate, replay and invalid-input combinations. Their results are saved in `reports/evaluation.json` and `reports/combinations.json`.
