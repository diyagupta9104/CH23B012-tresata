# Five-minute prototype walkthrough

This guide demonstrates the invoice-evidence problem with synthetic documents.

## Happy path

1. Start from a clean database.
2. Process `04_freight_first.pdf`.
3. Show the extracted fields, linked purchase order, receipt coverage, calculations, source quotes, and **approve** result.
4. Open **History & audit** and show the saved decision and calculation trail.

## Meaningful edge case

1. Process `04_freight_first.pdf` followed by `05_freight_overspend.pdf`.
2. Show that cumulative quantity and gross exceed the original order and the second invoice is rejected.
3. Change the synthetic order quantity to 250 and preview the impact.
4. Save the condition with a reviewer and reason.
5. Explicitly replay history and show the result move to review because receiving evidence is still short.
6. Add the synthetic receipt amendment and show the decision move to approval.

## What to explain

The prototype separates uncertain document perception from exact financial checks. It keeps the earlier decision, records the later evidence, and requires explicit replay before history changes.
