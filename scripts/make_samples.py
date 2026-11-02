"""Create synthetic PDFs for the demo and repeatable evaluation."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pymupdf as fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
EVIDENCE = ROOT / "sample_evidence"
ORDERS = ROOT / "sample_orders"

CASES = [
    {"file": "01_standard.pdf", "vendor": "Northstar Components", "number": "NC-2601", "po": "PO-1001", "item": "Industrial sensors", "qty": 50, "subtotal": 50000, "tax": 9000, "total": 59000, "style": "standard"},
    {"file": "02_split_order.pdf", "vendor": "Northstar Components", "number": "NC-2602", "po": "PO-1001", "item": "Industrial sensors", "qty": 50, "subtotal": 50000, "tax": 9000, "total": 59000, "style": "alternate"},
    {"file": "03_duplicate.pdf", "vendor": "Northstar Components", "number": "NC-2601", "po": "PO-1001", "item": "Industrial sensors", "qty": 50, "subtotal": 50000, "tax": 9000, "total": 59000, "style": "standard"},
    {"file": "04_freight_first.pdf", "vendor": "Harbor Logistics", "number": "HL-4101", "po": "PO-1002", "item": "Freight pallets", "qty": 150, "subtotal": 150000, "tax": 27000, "total": 177000, "style": "standard"},
    {"file": "05_freight_overspend.pdf", "vendor": "Harbor Logistics", "number": "HL-4102", "po": "PO-1002", "item": "Freight pallets", "qty": 75, "subtotal": 75000, "tax": 13500, "total": 88500, "style": "alternate"},
    {"file": "06_tax_inclusive.pdf", "vendor": "Cedar Office Supply", "number": "CO-3001", "po": "PO-1003", "item": "Desk chairs", "qty": 20, "subtotal": 20000, "tax": 3600, "total": 23600, "style": "inclusive"},
    {"file": "07_missing_po.pdf", "vendor": "Harbor Logistics", "number": "HL-4103", "po": None, "item": "Packaging cartons", "qty": 10, "subtotal": 10000, "tax": 1800, "total": 11800, "style": "standard"},
    {"file": "08_missing_number.pdf", "vendor": "Harbor Logistics", "number": None, "po": "PO-1005", "item": "Packaging cartons", "qty": 10, "subtotal": 10000, "tax": 1800, "total": 11800, "style": "alternate"},
    {"file": "09_receipt_recheck.pdf", "vendor": "Cedar Office Supply", "number": "CO-3002", "po": "PO-1003", "item": "Desk chairs", "qty": 25, "subtotal": 25000, "tax": 4500, "total": 29500, "style": "standard"},
    {"file": "10_unapproved_vendor.pdf", "vendor": "Orion Cloud Services", "number": "OC-9001", "po": None, "item": "Cloud storage", "qty": 5, "subtotal": 5000, "tax": 900, "total": 5900, "style": "standard"},
    {"file": "11_scanned_invoice.pdf", "vendor": "Northstar Components", "number": "NC-2603", "po": "PO-1004", "item": "Sensor calibration kits", "qty": 20, "subtotal": 20000, "tax": 3600, "total": 23600, "style": "scan"},
    {"file": "12_arithmetic_error.pdf", "vendor": "Harbor Logistics", "number": "HL-5101", "po": "PO-1005", "item": "Packaging cartons", "qty": 10, "subtotal": 10000, "tax": 1800, "total": 12800, "style": "alternate"},
    {"file": "13_bundled_line.pdf", "vendor": "Harbor Logistics", "number": "HL-5102", "po": "PO-1005", "item": "Packaging cartons", "qty": 10, "subtotal": 10000, "tax": 1800, "total": 11800, "style": "bundle"},
]


def make_pdf(case: dict) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("Synthetic invoice")
    pdf.setFillColorRGB(0.1, 0.25, 0.31)
    pdf.rect(0, 730, A4[0], 112, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 23)
    pdf.drawString(44, 770, "INVOICE")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(44, 746, "Synthetic training document · no payment requested")
    pdf.setFillColorRGB(0.1, 0.18, 0.22)
    pdf.setFont("Helvetica", 11)
    is_alt = case["style"] == "alternate"
    labels = {"vendor": "Supplier" if is_alt else "Vendor", "number": "Bill No." if is_alt else "Invoice Number", "po": "PO Ref" if is_alt else "Purchase Order", "subtotal": "Net Amount" if is_alt else "Subtotal", "tax": "GST (18%)" if is_alt else "Tax (18%)", "total": "Amount Due" if is_alt else "Grand Total"}
    y = 690
    def field(label: str, value: str | None) -> None:
        nonlocal y
        if value is not None:
            pdf.drawString(44, y, f"{label}: {value}")
            y -= 24
    field(labels["vendor"], case["vendor"])
    field(labels["number"], case["number"])
    field("Invoice Date", "2026-10-24")
    field(labels["po"], case["po"])
    field("Currency", "INR")
    y -= 25
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(44, y, "Description | Qty | Unit Price | Amount")
    y -= 23
    pdf.setFont("Helvetica", 10)
    if case["style"] == "bundle":
        pdf.drawString(44, y, "Warehouse packaging service bundle — see attached schedule")
    else:
        pdf.drawString(44, y, f"{case['item']} | {case['qty']} | 1000.00 | {case['subtotal']:.2f}")
    y -= 48
    field(labels["subtotal"], f"{case['subtotal']:.2f}")
    field(labels["tax"], f"{case['tax']:.2f}")
    field(labels["total"], f"{case['total']:.2f}")
    if case["style"] == "inclusive":
        field("Pricing note", "Grand total includes GST shown above")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(44, 72, "All entities, amounts and document identifiers in this file are invented for a prototype.")
    pdf.save()
    digital = buffer.getvalue()
    if case["style"] != "scan":
        return digital
    rendered = fitz.open(stream=digital, filetype="pdf")
    image = rendered[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
    scanned = fitz.open()
    page = scanned.new_page(width=A4[0], height=A4[1])
    page.insert_image(page.rect, stream=image)
    return scanned.tobytes()


def make_evidence_pdf(title: str, lines: list[str]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("Synthetic evidence")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(44, 770, title)
    pdf.setFont("Helvetica", 11)
    for index, line in enumerate(lines):
        pdf.drawString(44, 715 - index * 28, line)
    pdf.drawString(44, 120, "Synthetic training record. Reviewer must verify the original before posting.")
    pdf.save()
    return buffer.getvalue()


def make_order_pdf(po: dict, vendor_name: str) -> bytes:
    lines = [
        f"Purchase order: {po['id']}",
        f"Approved supplier: {vendor_name}",
        f"Currency: {po['currency']}",
        f"Tax rate configured on order: {float(po['tax_rate']) * 100:.0f}%",
    ]
    for item in po["items"]:
        lines.extend([f"Item: {item['description']}", f"Ordered quantity: {item['quantity']}", f"Unit price: {item['unit_price']}"])
    lines.append(f"Order subtotal: {po['subtotal']}")
    lines.append("This synthetic order is the initial register record. Later scenario edits are versioned in the app.")
    return make_evidence_pdf("PURCHASE ORDER", lines)


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        payload = (SAMPLES / "01_standard.pdf").read_bytes() if case["file"] == "03_duplicate.pdf" else make_pdf(case)
        (SAMPLES / case["file"]).write_bytes(payload)
    (SAMPLES / "manifest.json").write_text(json.dumps([{key: value for key, value in case.items() if key != "style"} for case in CASES], indent=2), encoding="utf-8")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "credit_note.pdf").write_bytes(make_evidence_pdf("CREDIT NOTE", ["Reference: CN-4101", "Purchase Order: PO-1002", "Original Invoice: HL-4101", "Credit Amount: 59000.00 INR", "Credited Quantity: 50 freight pallets"]))
    (EVIDENCE / "receipt_correction.pdf").write_bytes(make_evidence_pdf("RECEIPT CORRECTION", ["Reference: GRN-1003", "Purchase Order: PO-1003", "Corrected received quantity: 10 desk chairs", "Reason: recount of goods physically received"]))
    (EVIDENCE / "receipt_amendment_250.pdf").write_bytes(make_evidence_pdf("RECEIPT CORRECTION", ["Reference: GRN-1002", "Purchase Order: PO-1002", "Corrected received quantity: 250 freight pallets", "Reason: synthetic receiving scenario after PO amendment"]))
    (EVIDENCE / "receipt_amendment_225.pdf").write_bytes(make_evidence_pdf("RECEIPT CORRECTION", ["Reference: GRN-1002", "Purchase Order: PO-1002", "Corrected received quantity: 225 freight pallets", "Reason: synthetic receiving scenario after PO amendment"]))
    ORDERS.mkdir(parents=True, exist_ok=True)
    register = json.loads((ROOT / "data" / "reference.json").read_text(encoding="utf-8"))
    vendors = {vendor["id"]: vendor["name"] for vendor in register["vendors"]}
    for po in register["purchase_orders"]:
        (ORDERS / f"{po['id']}.pdf").write_bytes(make_order_pdf(po, vendors[po["vendor_id"]]))
    print(f"Created {len(CASES)} synthetic invoice PDFs in {SAMPLES}")


if __name__ == "__main__":
    main()
