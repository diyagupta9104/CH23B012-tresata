"""Interactive invoice decisions, source records and policy replay."""

from __future__ import annotations

import copy
import json
import os
from decimal import Decimal
from html import escape
from pathlib import Path

import streamlit as st

from engine.config import po_capacity
from engine.workflow import (
    add_evidence,
    apply_config,
    clear_history,
    config_history,
    config_version,
    detail,
    evidence_document,
    events,
    get_config,
    history,
    preview_config,
    process_invoice,
    replay_history,
)

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
SAMPLE_EVIDENCE = ROOT / "sample_evidence"
SAMPLE_ORDERS = ROOT / "sample_orders"
DEMO_ONLY = os.getenv("DEMO_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}

st.set_page_config(page_title="Evidence Ledger", page_icon="🧾", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1320px; padding-top: 1.4rem;}
html, body, [class*="css"] {font-family: Inter, system-ui, sans-serif;}
.hero {padding:10px 0 22px; margin-bottom:12px; border-bottom:1px solid #dce5df;}
.hero .eyebrow {font-size:.7rem; letter-spacing:.17em; font-weight:700; color:#577269; text-transform:uppercase;}
.hero h1 {font-size:2rem; letter-spacing:-.045em; color:#193d32; margin:.2rem 0 .3rem; font-weight:650;}
.hero p {margin:0; color:#6b7872; font-size:.92rem;}
.decision {border-radius:15px; padding:17px 21px; margin:8px 0 17px; border:1px solid #dce7e8; background:#f7fafb;}
.decision strong {font-size:1.34rem;}
.decision.approve {background:#eef9f4; border-color:#a8d8be;}
.decision.review {background:#fff8e8; border-color:#edd69b;}
.decision.reject {background:#fff1f0; border-color:#eab9b3;}
.muted {color:#536875; font-size:.88rem;}
div[data-testid="stMetric"] {background:#f7fafb; border:1px solid #e0e9eb; border-radius:13px; padding:12px 15px;}
.number-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:10px 0 17px;}
.number-card {background:#f7fafb; border:1px solid #dce7e8; border-radius:12px; padding:12px 14px; min-width:0;}
.number-card .label {font-size:.78rem; color:#536875; font-weight:650; line-height:1.3;}
.number-card .value {font-size:1.12rem; font-weight:750; color:#172d3b; line-height:1.3; margin-top:5px; overflow-wrap:anywhere; white-space:normal;}
.number-table-wrap {overflow-x:auto; margin:12px 0;}
.number-table {border-collapse:collapse; width:100%; min-width:490px; font-variant-numeric:tabular-nums;}
.number-table th,.number-table td {padding:9px 11px; border-bottom:1px solid #dce7e8; text-align:right; white-space:nowrap;}
.number-table th:first-child,.number-table td:first-child {text-align:left; white-space:normal;}
.number-table th {font-size:.78rem; color:#536875;}
.number-table .total-row {background:#eef4f5; font-weight:700;}
[data-testid="stTabs"] [role="tablist"] {gap:24px; margin-bottom:22px;}
[data-testid="stTabs"] [role="tab"] {padding:12px 2px;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
.check-row {display:flex; justify-content:space-between; align-items:baseline; gap:14px; padding:10px 0; border-bottom:1px solid #e6ebe7; font-size:.9rem;}
.check-row span:last-child {text-align:right; font-variant-numeric:tabular-nums;}
.check-pass {color:#28684b;} .check-review {color:#946417;} .check-reject {color:#b33e35;}
</style>
""", unsafe_allow_html=True)

active_version, active_config = get_config()
all_runs = history()
st.markdown('<div class="hero"><div class="eyebrow">Invoice workspace</div><h1>Evidence Ledger</h1><p>Every decision, backed by evidence.</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Workspace")
    st.caption("Synthetic data · local prototype")
    st.caption(f"{len(all_runs)} invoices · Conditions v{active_version}")
    with st.expander("Decision guide"):
        st.write("Approve · All configured checks passed")
        st.write("Review · Evidence needs confirmation")
        st.write("Reject · A blocking check failed")


def format_quantity(value: str | int | Decimal) -> str:
    number = Decimal(str(value))
    return f"{number:,.0f}" if number == number.to_integral_value() else f"{number:,f}".rstrip("0").rstrip(".")


def money(value: str | int | Decimal) -> str:
    return f"₹{Decimal(str(value)):,.2f}"


def number_grid(items: list[tuple[str, str]]) -> None:
    cards = "".join(f'<div class="number-card"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>' for label, value in items)
    st.markdown(f'<div class="number-grid">{cards}</div>', unsafe_allow_html=True)


def prior_invoice_rows(result: dict, invoice_id: int | None) -> list[dict]:
    balances = result["balances"]
    saved = balances.get("prior_invoices")
    if saved is not None:
        return saved
    if invoice_id is None:
        return []
    candidates = []
    for run in reversed(history()):
        if run["id"] >= invoice_id or run["po"] != result["po_id"] or run["status"] == "reject":
            continue
        previous = detail(run["id"])["decision"]
        candidates.append({"run_id": run["id"], "filename": run["filename"], "quantity": previous["net_quantity"], "gross": previous["net_total"]})
    if (sum((Decimal(row["quantity"]) for row in candidates), Decimal(0)) != Decimal(balances["prior_quantity"])
            or sum((Decimal(row["gross"]) for row in candidates), Decimal(0)) != Decimal(balances["prior_gross"])):
        return []
    return candidates


def render_order(result: dict, context: str, invoice_id: int | None = None) -> None:
    po, balances = result.get("po_evidence"), result.get("balances")
    if not po or not balances:
        st.info("Purchase order needs confirmation.")
        return
    qty_used = Decimal(balances["cumulative_quantity"])
    received = Decimal(balances["received_quantity"])
    qty_over = balances.get("quantity_exceeded", any(item["code"] == "PO_EXCEEDED" for item in result["issues"]))
    gross_over = balances.get("gross_exceeded", any(item["code"] == "PO_EXCEEDED" for item in result["issues"]))
    receipt_short = po["receipt_required"] and qty_used > received
    with st.container(border=True):
        st.markdown("**Order checks**")
        checks = [
            ("PO quantity", f"{format_quantity(qty_used)} / {format_quantity(balances['ordered_quantity'])} units", "Over limit" if qty_over else "Within limit", "reject" if qty_over else "pass"),
            ("PO gross", f"{money(balances['cumulative_gross'])} / {money(balances['gross_cap'])}", "Over limit" if gross_over else "Within limit", "reject" if gross_over else "pass"),
            ("Receipt", f"{format_quantity(received)} received / {format_quantity(qty_used)} billed" if po["receipt_required"] else "Not required", "Needs review" if receipt_short else "Covered", "review" if receipt_short else "pass"),
        ]
        for label, value, state_text, state in checks:
            st.markdown(f'<div class="check-row"><span>{escape(label)} · <span class="check-{state}">{escape(state_text)}</span></span><span>{escape(value)}</span></div>', unsafe_allow_html=True)
        if receipt_short:
            st.caption(f"Missing receiving confirmation: {format_quantity(qty_used - received)} units.")
    with st.expander("Invoice breakdown"):
        rows = [
            ("Earlier invoices", balances["prior_quantity"], balances["prior_gross"], ""),
            ("This PDF", balances["current_quantity"], balances["current_gross"], ""),
            ("Total on PO", balances["cumulative_quantity"], balances["cumulative_gross"], "total-row"),
        ]
        body = "".join(f'<tr class="{kind}"><td>{escape(label)}</td><td>{format_quantity(qty)}</td><td>{money(amount)}</td></tr>' for label, qty, amount, kind in rows)
        st.markdown(f'<div class="number-table-wrap"><table class="number-table"><thead><tr><th>Source</th><th>Units</th><th>Gross after credits</th></tr></thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
        for previous in prior_invoice_rows(result, invoice_id):
            st.caption(f"Run #{previous['run_id']} · {previous['filename']} · {format_quantity(previous['quantity'])} units · {money(previous['gross'])}")
    with st.expander("Order & receipt sources"):
        number_grid([("PO subtotal", money(po["subtotal"])), ("Tax rate", format_quantity(Decimal(po["tax_rate"]) * 100) + "%")])
        for item in po["items"]:
            st.write(f"{item['description']} · {format_quantity(item['quantity'])} units × {money(item['unit_price'])}")
        st.caption("Receipt sources: " + "; ".join(po["receipt_sources"]))
        source_path = SAMPLE_ORDERS / f"{po['id']}.pdf"
        if source_path.exists():
            st.download_button("Original sample PO (v1)", source_path.read_bytes(), file_name=source_path.name, mime="application/pdf", key=f"order_pdf_{context}")
        st.caption(f"Decision uses conditions v{result.get('config_version', '?')}.")


NEXT_ACTION = {
    "PO_EXCEEDED": "Check earlier invoices or obtain an approved PO amendment.",
    "RECEIPT_SHORTFALL": "Confirm the receiving record or add a documented correction.",
    "EXACT_DUPLICATE": "Review the earlier invoice; do not pay twice.",
    "PO_UNRESOLVED": "Confirm the PO reference with procurement.",
    "LINE_ITEMS_MISSING": "Request an itemized invoice or supporting schedule.",
    "TAX_RATE_MISMATCH": "Ask a qualified reviewer to check the tax treatment.",
}


def render_decision(result: dict, context: str, invoice_id: int | None = None, filename: str | None = None) -> None:
    status = result["status"]
    title = {"approve": "Ready for approval", "review": "Needs review", "reject": "Do not approve"}[status]
    suffix = f"Run #{invoice_id} · " if invoice_id else ""
    st.markdown(f'<div class="decision {status}"><strong>{title}</strong><br><span class="muted">{suffix}Conditions v{result.get("config_version", "?")}</span></div>', unsafe_allow_html=True)
    if filename:
        st.caption(filename)
    st.caption(f"{result.get('vendor_id') or 'Supplier unresolved'} · {result.get('po_id') or 'PO unresolved'}")
    number_grid([
        ("This invoice · units", format_quantity(result.get("net_quantity", "0"))),
        ("Gross after credits", money(result.get("net_total", "0"))),
    ])
    if result["issues"]:
        primary = next((item for item in result["issues"] if item["severity"] == "reject"), result["issues"][0])
        st.write(NEXT_ACTION.get(primary["code"], primary["message"]))
    render_order(result, context, invoice_id)
    if result["issues"]:
        with st.expander(f"Decision reasons ({len(result['issues'])})"):
            for item in result["issues"]:
                st.markdown(f"**{item['code'].replace('_', ' ').title()}** · {item['severity'].upper()}")
                st.write(item["message"])
                st.caption("Sources: " + ", ".join(item["sources"]))
    with st.expander("Calculations & PDF quotes"):
        for name, value in result["calculations"].items():
            st.markdown(f"**{name.replace('_', ' ').title()}** · {value}")
        for name, source in result["sources"].items():
            st.write(f"{name.title()}: {source['value']} · page {source.get('page') or '?'} · {source['quote']}")
        st.caption(f"Extraction: {result.get('extraction_method')} · OCR confidence: {result.get('ocr_confidence')}")


def has_unsaved_condition_edits(version: int, config: dict) -> bool:
    if st.session_state.get("draft_base_version") == version and st.session_state.get("draft_config") != config:
        return True
    for po in config["purchase_orders"]:
        po_id = po["id"]
        for index, item in enumerate(po["items"]):
            for field, prefix in (("quantity", "qty"), ("unit_price", "price")):
                key = f"{prefix}_{version}_{po_id}_{index}"
                if key in st.session_state and Decimal(str(st.session_state[key])) != Decimal(str(item[field])):
                    return True
        for field, prefix in (("tax_rate", "tax"), ("receipt_required", "receipt_required")):
            key = f"{prefix}_{version}_{po_id}"
            if key in st.session_state:
                value = st.session_state[key]
                changed = Decimal(str(value)) / Decimal(100) != Decimal(str(po[field])) if field == "tax_rate" else value != po[field]
                if changed:
                    return True
    for vendor in config["vendors"]:
        key = f"vendor_{version}_{vendor['id']}"
        if key in st.session_state and st.session_state[key] != vendor["approved"]:
            return True
    for key, value in config["policy"].items():
        widget_key = f"setting_{version}_{key}"
        if widget_key in st.session_state and Decimal(str(st.session_state[widget_key])) != Decimal(str(value)):
            return True
    return False


def save_condition_draft(draft: dict, reviewer: str, reason: str) -> None:
    try:
        st.session_state["last_policy_result"] = apply_config(draft, reviewer, reason)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))


TEST_PLAN = [
    {"Order": 1, "PDF": "01_standard.pdf", "Expected on fresh data": "approve", "What it tests": "Invoice, PO and receipt match"},
    {"Order": 2, "PDF": "02_split_order.pdf", "Expected on fresh data": "approve", "What it tests": "Two invoices consume one PO exactly"},
    {"Order": 3, "PDF": "03_duplicate.pdf", "Expected on fresh data": "reject", "What it tests": "Repeated upload of invoice 01"},
    {"Order": 4, "PDF": "04_freight_first.pdf", "Expected on fresh data": "approve", "What it tests": "First partial bill on PO-1002"},
    {"Order": 5, "PDF": "05_freight_overspend.pdf", "Expected on fresh data": "reject", "What it tests": "Cumulative 225 units vs 200 ordered"},
    {"Order": 6, "PDF": "06_tax_inclusive.pdf", "Expected on fresh data": "approve", "What it tests": "Tax shown within the gross total"},
    {"Order": 7, "PDF": "07_missing_po.pdf", "Expected on fresh data": "review", "What it tests": "Unresolved PO reference"},
    {"Order": 8, "PDF": "08_missing_number.pdf", "Expected on fresh data": "review", "What it tests": "Missing critical invoice number"},
    {"Order": 9, "PDF": "09_receipt_recheck.pdf", "Expected on fresh data": "approve", "What it tests": "Later receipt correction can reopen this"},
    {"Order": 10, "PDF": "10_unapproved_vendor.pdf", "Expected on fresh data": "reject", "What it tests": "Supplier approval condition"},
    {"Order": 11, "PDF": "11_scanned_invoice.pdf", "Expected on fresh data": "approve", "What it tests": "Actual image-only PDF and OCR"},
    {"Order": 12, "PDF": "12_arithmetic_error.pdf", "Expected on fresh data": "reject", "What it tests": "Stated total contradicts calculation"},
    {"Order": 13, "PDF": "13_bundled_line.pdf", "Expected on fresh data": "review", "What it tests": "Cannot verify an unitemized bundle"},
]


process_tab, policy_tab, evidence_tab, history_tab, overview_tab = st.tabs(["Process invoice", "Conditions & replay", "Later evidence", "History & audit", "Test guide"])

with overview_tab:
    st.subheader("What this workspace checks")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("### 1 · Read")
            st.write("Digital text or local OCR for scans. Extracted fields keep page and text quotes.")
    with c2:
        with st.container(border=True):
            st.markdown("### 2 · Match")
            st.write("Compare the invoice with supplier approval, PO lines, receipts and earlier invoices.")
    with c3:
        with st.container(border=True):
            st.markdown("### 3 · Revisit")
            st.write("Save conditions for new invoices. Replay past invoices only when you choose to.")
    st.markdown("#### Test the sample PDFs in this order")
    st.caption("Expected outcomes assume the initial conditions and an empty history. Repeating a PDF or changing conditions changes later results.")
    st.dataframe(TEST_PLAN, hide_index=True, width="stretch")
    with st.expander("PO-1002 example"):
        st.write("Set the PO to 225 units, then process PDFs 04 and 05. Together they use 225 units. They still need review until receiving evidence confirms the units billed.")
    with st.expander("How to check every tab"):
        st.dataframe([
            {"Tab": "Test guide", "Try": "Read the 13-PDF checklist; reset conditions too for a baseline run."},
            {"Tab": "Process invoice", "Try": "Choose a sample, run checks, inspect reasons, PO limits and source quotes."},
            {"Tab": "Conditions & replay", "Try": "Edit a rule, save it for new invoices, then optionally rerun history."},
            {"Tab": "Later evidence", "Try": "Add a sample credit or receipt PDF and inspect its event log."},
            {"Tab": "History & audit", "Try": "Filter statuses, compare revisions, export JSON, or clear runs while keeping conditions."},
        ], hide_index=True, width="stretch")

with process_tab:
    left, right = st.columns([1, 1.7], gap="large")
    with left:
        st.subheader("Process an invoice")
        st.caption("Upload a PDF or try a sample.")
        unsaved_draft = has_unsaved_condition_edits(active_version, active_config)
        if unsaved_draft:
            st.warning(f"Condition edits are not active yet. Save and activate them in Conditions & replay before processing; the active version is still v{active_version}.")
        if DEMO_ONLY:
            st.info("Demo mode uses only the bundled synthetic invoice PDFs.")
            uploaded = None
        else:
            uploaded = st.file_uploader("Invoice PDF", type="pdf", key="invoice_file")
        sample_paths = sorted(SAMPLES.glob("*.pdf"))
        sample_name = st.selectbox("Or choose a sample", ["None"] + [path.name for path in sample_paths], key="sample_invoice")
        if st.button("Run invoice checks", type="primary", width="stretch", disabled=unsaved_draft):
            if uploaded is None and sample_name == "None":
                st.warning("Choose a PDF first.")
            else:
                filename = uploaded.name if uploaded is not None else sample_name
                payload = uploaded.getvalue() if uploaded is not None else (SAMPLES / sample_name).read_bytes()
                try:
                    with st.status("Processing invoice", expanded=True) as progress:
                        def stage(name: str, message: str) -> None:
                            st.write(f"**{name}** — {message}")
                        invoice_id, result = process_invoice(payload, filename, stage)
                        progress.update(label=f"Run #{invoice_id} completed", state="complete", expanded=False)
                    st.session_state["latest_run"] = invoice_id
                    all_runs = history()
                except Exception as exc:
                    st.error(f"Could not process the PDF: {exc}")
    with right:
        if st.session_state.get("latest_run"):
            run = detail(st.session_state["latest_run"])
            render_decision(run["decision"], "latest", run["id"], run["filename"])
            st.download_button("Download decision JSON", json.dumps(run, indent=2), file_name=f"invoice-decision-{run['id']}.json", mime="application/json", key="latest_json")
        else:
            st.info("Your decision will appear here.")

with policy_tab:
    st.subheader("Conditions")
    st.caption("Save for new invoices. Rerun history when you choose.")
    if st.session_state.get("draft_base_version") != active_version:
        st.session_state["draft_config"] = copy.deepcopy(active_config)
        st.session_state["draft_base_version"] = active_version
        st.session_state.pop("policy_preview", None)
        st.session_state.pop("policy_preview_fingerprint", None)
        st.session_state.pop("replay_preview", None)
        st.session_state.pop("replay_preview_signature", None)
    draft = st.session_state["draft_config"]
    if st.session_state.get("last_policy_result"):
        outcome = st.session_state.pop("last_policy_result")
        st.success(f"Conditions v{outcome['version']} saved for new invoices. Earlier decisions were not changed.")
    if st.session_state.get("last_replay_result"):
        outcome = st.session_state.pop("last_replay_result")
        st.success(f"Checked {outcome['recomputed']} past invoices; {len(outcome['revised_runs'])} decision records revised and {outcome['status_changes']} changed status.")
    st.caption(f"Active version {active_version} · Demo conditions")
    st.markdown("#### Purchase orders")
    po_id = st.selectbox("Choose an order to inspect or edit", [po["id"] for po in draft["purchase_orders"]], key=f"edit_po_{active_version}")
    po = next(item for item in draft["purchase_orders"] if item["id"] == po_id)
    vendor_name = next(vendor["name"] for vendor in draft["vendors"] if vendor["id"] == po["vendor_id"])
    st.caption(f"Supplier: {vendor_name} · Receipt record: {', '.join(item['id'] for item in po['receipts'])} · Change received quantity with a supporting PDF in Later evidence.")
    item_index = st.selectbox("PO line", list(range(len(po["items"]))), format_func=lambda index, items=po["items"]: items[index]["description"], key=f"item_{active_version}_{po_id}")
    item = po["items"][item_index]
    p1, p2, p3 = st.columns(3)
    ordered = p1.number_input("Ordered quantity", min_value=0.01, value=float(item["quantity"]), step=1.0, key=f"qty_{active_version}_{po_id}_{item_index}")
    unit_price = p2.number_input("Unit price (₹)", min_value=0.0, value=float(item["unit_price"]), step=10.0, key=f"price_{active_version}_{po_id}_{item_index}")
    tax_percent = p3.number_input("Configured tax rate (%)", min_value=0.0, max_value=100.0, value=float(po["tax_rate"]) * 100, step=1.0, key=f"tax_{active_version}_{po_id}")
    ordered_value = Decimal(str(ordered))
    price_value = Decimal(str(unit_price))
    tax_value = Decimal(str(tax_percent)) / Decimal(100)
    if ordered_value != Decimal(str(item["quantity"])):
        item["quantity"] = format(ordered_value.normalize(), "f")
    if price_value != Decimal(str(item["unit_price"])):
        item["unit_price"] = format(price_value.quantize(Decimal("0.01")), "f")
    if tax_value != Decimal(str(po["tax_rate"])):
        po["tax_rate"] = format(tax_value.normalize(), "f")
    subtotal_value = sum((Decimal(line["quantity"]) * Decimal(line["unit_price"]) for line in po["items"]), Decimal(0))
    if subtotal_value != Decimal(str(po["subtotal"])):
        po["subtotal"] = format(subtotal_value.quantize(Decimal("0.01")), "f")
    po["receipt_required"] = st.checkbox("Require receiving evidence for this PO", value=po["receipt_required"], key=f"receipt_required_{active_version}_{po_id}")
    capacity = po_capacity(po)
    receipt_quantities = {record["id"]: Decimal(str(record["quantity"])) for record in po["receipts"]}
    for event in reversed(events()):
        if event["kind"] == "receipt_correction" and event["po_id"] == po_id and event["reference"] in receipt_quantities:
            receipt_quantities[event["reference"]] = Decimal(str(event["quantity"]))
    active_received = sum(receipt_quantities.values(), Decimal(0))
    number_grid([
        ("Draft ordered quantity", format_quantity(capacity["ordered_quantity"])),
        ("Confirmed received", format_quantity(active_received)),
        ("Draft gross PO cap", money(capacity["gross_cap"])),
    ])
    if po["receipt_required"] and Decimal(capacity["ordered_quantity"]) > active_received:
        st.info(f"This order allows {capacity['ordered_quantity']} units, while receipts confirm {active_received}. An invoice beyond received quantity can still need review.")
    active_po = next(item for item in active_config["purchase_orders"] if item["id"] == po_id)
    active_capacity = po_capacity(active_po)
    if po != active_po:
        st.warning(f"Unsaved PO change: {po_id} is currently active at {active_capacity['ordered_quantity']} units (₹{active_capacity['gross_cap']} gross). Your draft is {capacity['ordered_quantity']} units (₹{capacity['gross_cap']} gross).")
    original_po = SAMPLE_ORDERS / f"{po_id}.pdf"
    if original_po.exists():
        st.download_button("Download original PO PDF (version 1)", original_po.read_bytes(), file_name=original_po.name, mime="application/pdf", key=f"draft_po_pdf_{po_id}")
    with st.expander("Vendor approval conditions"):
        for vendor in draft["vendors"]:
            vendor["approved"] = st.checkbox(f"{vendor['name']} ({vendor['id']}) approved", value=vendor["approved"], key=f"vendor_{active_version}_{vendor['id']}")
    with st.expander("Matching and tolerance settings"):
        labels = [
            ("Supplier possible match minimum (%)", "vendor_match_min", 0.0, 100.0, 1.0),
            ("Supplier automatic match minimum (%)", "vendor_auto_approve_min", 0.0, 100.0, 1.0),
            ("Item possible match minimum (%)", "item_match_min", 0.0, 100.0, 1.0),
            ("Item automatic match minimum (%)", "item_auto_approve_min", 0.0, 100.0, 1.0),
            ("OCR average confidence minimum", "ocr_average_min", 0.0, 1.0, 0.01),
            ("OCR line confidence minimum", "ocr_line_min", 0.0, 1.0, 0.01),
            ("Tax difference tolerance (₹)", "tax_tolerance", 0.0, 100000.0, 0.1),
            ("PO gross overage tolerance (₹)", "po_amount_tolerance", 0.0, 100000.0, 0.1),
            ("Unit price difference tolerance (₹)", "unit_price_tolerance", 0.0, 100000.0, 0.1),
            ("Line and invoice arithmetic tolerance (₹)", "line_amount_tolerance", 0.0, 100000.0, 0.1),
        ]
        for label, key, minimum, maximum, step in labels:
            value = st.number_input(label, min_value=minimum, max_value=maximum, value=float(draft["policy"][key]), step=step, key=f"setting_{active_version}_{key}")
            if key.endswith("_min") and "ocr" not in key:
                draft["policy"][key] = int(value)
            elif Decimal(str(value)) != Decimal(str(draft["policy"][key])):
                draft["policy"][key] = format(Decimal(str(value)).normalize(), "f")
    with st.expander("Complete rule catalog"):
        st.dataframe([
            {"Check": "Required fields and date", "Condition": "Supplier, number, date and total present; date valid", "Outcome": "Review if missing or invalid", "Editable": "Fixed safeguard"},
            {"Check": "Supplier identity", "Condition": "Name linked above similarity thresholds", "Outcome": "Review if uncertain", "Editable": "Match thresholds"},
            {"Check": "Supplier approval", "Condition": "Matched vendor approved", "Outcome": "Reject if unapproved", "Editable": "Vendor switch"},
            {"Check": "PO identity and currency", "Condition": "PO exists, belongs to supplier and uses same currency", "Outcome": "Review if missing; reject conflict", "Editable": "Fixed safeguard"},
            {"Check": "Invoice arithmetic", "Condition": "Nonnegative subtotal, tax and total; subtotal + tax = total", "Outcome": "Reject contradiction; review missing breakdown", "Editable": "Arithmetic tolerance"},
            {"Check": "Tax policy", "Condition": "Invoice tax near PO configured rate", "Outcome": "Review if outside tolerance", "Editable": "Rate and tolerance"},
            {"Check": "Line completeness and math", "Condition": "Quantity, unit price, amount and line sum reconcile", "Outcome": "Review unreadable; reject contradiction", "Editable": "Arithmetic tolerance"},
            {"Check": "Item and price match", "Condition": "Description and unit price agree with PO", "Outcome": "Review if uncertain or different", "Editable": "Match and price thresholds"},
            {"Check": "Cumulative PO capacity", "Condition": "Earlier + current quantity and gross within PO", "Outcome": "Reject if exceeded", "Editable": "PO quantity, price and gross tolerance"},
            {"Check": "Receiving evidence", "Condition": "Billed units within active receipts", "Outcome": "Review if short", "Editable": "PO requirement; receipt via PDF"},
            {"Check": "Duplicate", "Condition": "Supplier and invoice number already seen", "Outcome": "Reject same file; review reused number", "Editable": "Fixed safeguard"},
            {"Check": "Credit bounds", "Condition": "Total credits do not exceed invoice quantity or gross", "Outcome": "Review invalid credit", "Editable": "Fixed safeguard"},
            {"Check": "OCR and extraction", "Condition": "Scan confidence high; extraction sources agree", "Outcome": "Review low confidence or conflict", "Editable": "OCR thresholds"},
        ], hide_index=True, width="stretch")
    st.markdown("#### Save changes")
    if draft != active_config:
        reviewer = st.text_input("Reviewer identifier", key="policy_reviewer")
        reason = st.text_area("Change reason", key="policy_reason", placeholder="Example: PO-1002 ordered quantity revised to 225")
        if not reviewer.strip() or not reason.strip():
            st.caption("Enter a reviewer and reason to enable Save.")
        if st.button("Save and activate changes", type="primary", disabled=not reviewer.strip() or not reason.strip(), key="save_conditions_top"):
            save_condition_draft(draft, reviewer, reason)
    else:
        st.success(f"Conditions v{active_version} are active for new invoices.")
    current_fingerprint = json.dumps(draft, sort_keys=True)
    if st.button("Preview possible impact on past invoices"):
        try:
            st.session_state["policy_preview"] = preview_config(draft)
            st.session_state["policy_preview_fingerprint"] = current_fingerprint
        except ValueError as exc:
            st.error(str(exc))
    preview = st.session_state.get("policy_preview")
    preview_current = preview is not None and st.session_state.get("policy_preview_fingerprint") == current_fingerprint
    if preview and not preview_current:
        st.info("Draft changed. Preview again to see its current impact.")
    if preview_current:
        st.markdown("#### Possible impact if history is rerun")
        p1, p2, p3 = st.columns(3)
        p1.metric("Past invoices checked", preview["invoices"])
        p2.metric("Status changes", preview["status_changes"])
        p3.metric("Draft different from active", "Yes" if preview["config_changed"] else "No")
        st.dataframe([{"Run": item["id"], "PDF": item["filename"], "PO": item["po_id"], "Before": item["before"], "After": item["after"], "Changed status": item["status_changed"], "New reasons": ", ".join(item["after_issues"])} for item in preview["impacts"]], hide_index=True, width="stretch")
        changed_items = [item for item in preview["impacts"] if item["status_changed"]]
        if changed_items:
            selected_impact = st.selectbox("Inspect a changed decision", [item["id"] for item in changed_items], key="impact_run")
            impact = next(item for item in changed_items if item["id"] == selected_impact)
            st.write(f"Run #{selected_impact}: **{impact['before'].upper()} → {impact['after'].upper()}**")
            st.write("Before:", impact["before_calculations"])
            st.write("After:", impact["after_calculations"])
    st.markdown("#### Optional: rerun past invoices")
    st.caption("Uses the saved conditions version shown above. Saving a draft does not change the audit history.")
    replay_signature = (active_version, tuple((row["id"], row["version"], row["status"]) for row in all_runs))
    if st.button("Preview rerun with saved conditions", disabled=not all_runs):
        st.session_state["replay_preview"] = preview_config(active_config)
        st.session_state["replay_preview_signature"] = replay_signature
    replay_preview = st.session_state.get("replay_preview")
    replay_preview_current = replay_preview is not None and st.session_state.get("replay_preview_signature") == replay_signature
    if replay_preview and not replay_preview_current:
        st.info("History or conditions changed. Preview the rerun again.")
    if replay_preview_current:
        st.metric("Past statuses that would change", replay_preview["status_changes"])
        st.dataframe([{"Run": item["id"], "PDF": item["filename"], "Before": item["before"], "After": item["after"], "Current reasons": ", ".join(item["before_issues"]), "Rerun reasons": ", ".join(item["after_issues"])} for item in replay_preview["impacts"]], hide_index=True, width="stretch")
        replay_reviewer = st.text_input("Reviewer identifier for this rerun", key="replay_reviewer")
        replay_reason = st.text_area("Reason for rerunning past invoices", key="replay_reason")
        if st.button("Rerun history using saved conditions", disabled=not replay_reviewer.strip() or not replay_reason.strip()):
            try:
                st.session_state["last_replay_result"] = replay_history(replay_reviewer, replay_reason)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with st.expander("Condition version history"):
        st.markdown("#### Condition version history")
        st.dataframe(config_history(), hide_index=True, width="stretch")
        prior_id = st.selectbox("Inspect a saved version", [item["id"] for item in config_history()], key="saved_config_version")
        with st.expander("Saved version details"):
            st.json(config_version(prior_id))

with evidence_tab:
    st.subheader("Add later evidence")
    st.caption("Add a receipt correction or credit. Affected decisions are checked again.")
    kind_label = st.radio("Evidence type", ["Receipt correction", "Credit note"], horizontal=True)
    po_ids = [po["id"] for po in active_config["purchase_orders"]]
    po_id = st.selectbox("Purchase order", po_ids, key="evidence_po")
    po = next(item for item in active_config["purchase_orders"] if item["id"] == po_id)
    if kind_label == "Receipt correction":
        reference = st.selectbox("Receipt reference", [item["id"] for item in po["receipts"]])
        quantity = st.number_input("Corrected received quantity", min_value=0.0, value=float(po["receipts"][0]["quantity"]), step=1.0)
        amount = None
        invoice_id = None
    else:
        eligible = [row for row in all_runs if row["po"] == po_id]
        invoice_id = st.selectbox("Invoice being credited", [row["id"] for row in eligible]) if eligible else None
        if not eligible:
            st.info("Process an invoice for this PO before adding a credit.")
        reference = st.text_input("Credit note reference")
        amount = st.number_input("Credit amount including tax", min_value=0.0, step=100.0)
        quantity = st.number_input("Credited item quantity", min_value=0.0, step=1.0)
    note = st.text_area("Evidence note / reason")
    verified_by = st.text_input("Reviewer identifier", key="evidence_reviewer")
    if DEMO_ONLY:
        st.info("Demo mode uses only the bundled synthetic evidence PDFs.")
        source_upload = None
    else:
        source_upload = st.file_uploader("Supporting evidence PDF", type="pdf", key="evidence_file")
    source_samples = sorted(SAMPLE_EVIDENCE.glob("*.pdf"))
    source_sample = st.selectbox("Or choose a sample evidence PDF", ["None"] + [item.name for item in source_samples])
    st.caption("The reference and entered values must be present in the PDF. The reviewer remains accountable for document authenticity.")
    if st.button("Save evidence and replay", type="primary"):
        try:
            source_pdf = source_upload.getvalue() if source_upload is not None else (SAMPLE_EVIDENCE / source_sample).read_bytes() if source_sample != "None" else None
            revised = add_evidence("receipt_correction" if kind_label == "Receipt correction" else "credit", po_id, reference, str(quantity), str(amount) if amount is not None else None, note, invoice_id, verified_by, source_pdf)
            all_runs = history()
            st.success("Evidence saved. Revised runs: " + (", ".join(f"#{item}" for item in revised) or "none"))
        except ValueError as exc:
            st.error(str(exc))
    event_rows = events()
    if event_rows:
        with st.expander("Evidence log & source PDFs"):
            st.dataframe(event_rows, hide_index=True, width="stretch")
            event_id = st.selectbox("Inspect a source document", [item["id"] for item in event_rows])
            document = evidence_document(event_id)
            st.code(document["source_text"], language="text")
            if document["source_pdf"]:
                st.download_button("Download source PDF", document["source_pdf"], file_name=f"evidence-{event_id}.pdf", mime="application/pdf", key="event_pdf")

with history_tab:
    st.subheader("Run history & audit trail")
    if st.session_state.get("reset_notice"):
        st.success(st.session_state.pop("reset_notice"))
    with st.expander("Clear history / start fresh"):
        st.write("Clears invoice runs and evidence. Saved conditions stay active unless you also reset them. Sample PDFs stay available.")
        reset_conditions = st.checkbox("Also restore the original demo conditions", key="clear_reset_conditions")
        confirmation = st.text_input("Type CLEAR to confirm", key="clear_confirmation")
        has_activity = bool(all_runs) or bool(events()) or (reset_conditions and active_version > 1)
        if st.button("Clear saved demo activity", disabled=confirmation != "CLEAR" or not has_activity):
            try:
                removed = clear_history(confirmation, reset_conditions=reset_conditions)
                st.session_state.clear()
                condition_notice = "Original demo conditions restored." if reset_conditions else f"Saved conditions v{active_version} remain active."
                st.session_state["reset_notice"] = f"Cleared {removed['invoices']} invoices and {removed['evidence']} evidence records. {condition_notice}"
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if not all_runs:
        st.info("No invoices have been processed yet.")
    else:
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Total", len(all_runs))
        for col, status in zip((h2, h3, h4), ("approve", "review", "reject")):
            col.metric(status.title(), sum(row["status"] == status for row in all_runs))
        status_filter = st.selectbox("Filter decisions", ["All", "approve", "review", "reject"])
        visible = [row for row in all_runs if status_filter == "All" or row["status"] == status_filter]
        st.dataframe(visible, hide_index=True, width="stretch")
        if visible:
            chosen = st.selectbox("Inspect a run", [row["id"] for row in visible], format_func=lambda item: f"Run #{item} · {next(row['filename'] for row in visible if row['id'] == item)}")
            selected = detail(chosen)
            render_decision(selected["decision"], "history", chosen, selected["filename"])
            with st.expander("Every decision version"):
                for revision in selected["revisions"]:
                    st.markdown(f"**v{revision['version']} · {revision['status'].upper()}** · {revision['created_at']} · {revision['trigger']}")
            with st.expander("Original PDF text and extracted fields"):
                st.code("\n\n".join(selected["reading"]["pages"]), language="text")
                st.json(selected["parsed"])
            st.download_button("Download full audit JSON", json.dumps(selected, indent=2), file_name=f"audit-run-{chosen}.json", mime="application/json", key="history_json")
