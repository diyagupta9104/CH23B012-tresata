"""Auditable invoice decisions with versioned procurement evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from rapidfuzz.fuzz import ratio

from engine.extraction import extract_invoice, read_pdf
from engine.config import po_capacity, validate_config

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT / "data" / "reference.json").read_text(encoding="utf-8"))
DB_PATH = Path(os.getenv("INVOICE_DB", str(ROOT / "data" / "state.db")))
CENT = Decimal("0.01")


def dec(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value)) if value is not None and str(value).strip() else None
        return parsed if parsed is None or parsed.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS invoices (
          id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, filename TEXT NOT NULL,
          sha256 TEXT NOT NULL, parsed TEXT NOT NULL, reading TEXT NOT NULL,
          decision TEXT, status TEXT, version INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS evidence_events (
          id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL,
          po_id TEXT NOT NULL, invoice_id INTEGER, reference TEXT NOT NULL,
          quantity TEXT, amount TEXT, note TEXT NOT NULL, verified_by TEXT NOT NULL,
          source_sha256 TEXT NOT NULL, source_text TEXT NOT NULL, source_pdf BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS revisions (
          id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, version INTEGER NOT NULL,
          created_at TEXT NOT NULL, trigger TEXT NOT NULL, status TEXT NOT NULL,
          decision TEXT NOT NULL, FOREIGN KEY(invoice_id) REFERENCES invoices(id)
        );
        CREATE TABLE IF NOT EXISTS config_versions (
          id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, changed_by TEXT NOT NULL,
          note TEXT NOT NULL, config TEXT NOT NULL
        );
    """)
    event_columns = {row["name"] for row in db.execute("PRAGMA table_info(evidence_events)")}
    for name, definition in {
        "verified_by": "TEXT NOT NULL DEFAULT ''",
        "source_sha256": "TEXT NOT NULL DEFAULT ''",
        "source_text": "TEXT NOT NULL DEFAULT ''",
        "source_pdf": "BLOB NOT NULL DEFAULT X''",
    }.items():
        if name not in event_columns:
            db.execute(f"ALTER TABLE evidence_events ADD COLUMN {name} {definition}")
    if not db.execute("SELECT 1 FROM config_versions LIMIT 1").fetchone():
        db.execute("INSERT INTO config_versions(created_at,changed_by,note,config) VALUES(?,?,?,?)", (now(), "system", "Initial synthetic register", json.dumps(validate_config(REFERENCE))))
        db.commit()
    legacy = db.execute("SELECT decision FROM invoices WHERE decision IS NOT NULL LIMIT 1").fetchone()
    if legacy and "config_version" not in json.loads(legacy["decision"]):
        _replay(db, "configuration migration")
    try:
        yield db
    finally:
        db.close()


def _active_config(db: sqlite3.Connection) -> tuple[int, dict[str, Any]]:
    row = db.execute("SELECT id,config FROM config_versions ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"], json.loads(row["config"])


def get_config() -> tuple[int, dict[str, Any]]:
    with connect() as db:
        return _active_config(db)


def config_history() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id,created_at,changed_by,note FROM config_versions ORDER BY id DESC").fetchall()]


def config_version(version_id: int) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT id,created_at,changed_by,note,config FROM config_versions WHERE id=?", (version_id,)).fetchone()
    if not row:
        raise ValueError("Configuration version not found.")
    return {"id": row["id"], "created_at": row["created_at"], "changed_by": row["changed_by"], "note": row["note"], "config": json.loads(row["config"])}


def clear_history(confirmation: str, reset_conditions: bool = False) -> dict[str, int]:
    """Clear saved invoices and evidence; keep active conditions unless requested."""
    if confirmation != "CLEAR":
        raise ValueError("Type CLEAR to confirm the history reset.")
    with connect() as db:
        counts = {
            "invoices": db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
            "evidence": db.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0],
            "condition_versions": max(db.execute("SELECT COUNT(*) FROM config_versions").fetchone()[0] - 1, 0) if reset_conditions else 0,
        }
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM revisions")
            db.execute("DELETE FROM evidence_events")
            db.execute("DELETE FROM invoices")
            if reset_conditions:
                db.execute("DELETE FROM config_versions")
                db.execute(
                    "INSERT INTO config_versions(created_at,changed_by,note,config) VALUES(?,?,?,?)",
                    (now(), "system", "Initial synthetic register", json.dumps(validate_config(REFERENCE))),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return counts


def reference_po(po_id: str, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    source = config if config is not None else get_config()[1]
    return next((po for po in source["purchase_orders"] if po["id"].casefold() == po_id.casefold()), None)


def _vendor(name: str | None, config: dict[str, Any]) -> tuple[dict[str, Any] | None, float]:
    if not name:
        return None, 0.0
    ranked = sorted(((ratio(name.casefold(), vendor["name"].casefold()), vendor) for vendor in config["vendors"]), key=lambda row: row[0], reverse=True)
    return ranked[0][1], ranked[0][0]


def _active_receipt(po: dict[str, Any], events: list[sqlite3.Row]) -> tuple[Decimal, list[str]]:
    receipts = {item["id"]: (dec(item["quantity"]) or Decimal(0), item["source"]) for item in po["receipts"]}
    for event in events:
        if event["po_id"] == po["id"] and event["kind"] == "receipt_correction":
            receipts[event["reference"]] = (dec(event["quantity"]) or Decimal(0), f"event:{event['id']} {event['note']}")
    return sum((value for value, _ in receipts.values()), Decimal(0)), [source for _, source in receipts.values()]


def _credits(invoice_id: int, events: list[sqlite3.Row]) -> tuple[Decimal, Decimal, list[str]]:
    matching = [event for event in events if event["kind"] == "credit" and event["invoice_id"] == invoice_id]
    amount = sum((dec(event["amount"]) or Decimal(0) for event in matching), Decimal(0))
    quantity = sum((dec(event["quantity"]) or Decimal(0) for event in matching), Decimal(0))
    return amount, quantity, [f"event:{event['id']} {event['reference']}" for event in matching]


def _issue(code: str, severity: str, message: str, sources: list[str]) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "sources": sources}


def decide(row: sqlite3.Row, earlier: list[tuple[sqlite3.Row, dict[str, Any]]], events: list[sqlite3.Row], config: dict[str, Any], config_version: int) -> dict[str, Any]:
    invoice = json.loads(row["parsed"])
    issues: list[dict[str, Any]] = []
    calculations: dict[str, str] = {}
    policy = config["policy"]
    po_evidence = None
    balances = None
    vendor, score = _vendor(invoice.get("vendor"), config)
    if not vendor or score < float(policy["vendor_match_min"]):
        issues.append(_issue("VENDOR_UNKNOWN", "review", "Supplier could not be confidently linked to an approved record.", ["invoice:vendor", "vendor register"]))
    elif not vendor["approved"]:
        issues.append(_issue("VENDOR_UNAPPROVED", "reject", "Supplier is not approved in the vendor register.", ["invoice:vendor", f"vendor:{vendor['id']}"]))
    elif score < float(policy["vendor_auto_approve_min"]):
        issues.append(_issue("VENDOR_ALIAS", "review", f"Supplier name is a possible match ({score:.0f}%); confirm the identity.", ["invoice:vendor", f"vendor:{vendor['id']}"]))
    for name in ("vendor", "number", "date", "total"):
        if not invoice.get(name):
            issues.append(_issue("MISSING_" + name.upper(), "review", f"Invoice {name} is missing or unreadable.", [f"invoice:{name}"]))
    if invoice.get("extraction_method") == "OCR" and invoice.get("ocr_confidence", 0) < float(policy["ocr_average_min"]):
        issues.append(_issue("LOW_OCR_CONFIDENCE", "review", "Scan recognition confidence is too low for automatic approval.", ["invoice:scan"]))
    if invoice.get("extraction_method") == "OCR":
        critical_scores = [source.get("confidence") for source in invoice.get("fields", {}).values() if source.get("confidence") is not None]
        critical_scores += [line.get("confidence") for line in invoice.get("lines", []) if line.get("confidence") is not None]
        if critical_scores and min(critical_scores) < float(policy["ocr_line_min"]):
            issues.append(_issue("UNCERTAIN_OCR_FIELD", "review", "A critical OCR line is below the automatic-approval confidence threshold.", ["invoice:scan"]))
    if any("disagree" in warning for warning in invoice.get("warnings", [])):
        issues.append(_issue("EXTRACTION_CONFLICT", "review", "Two extraction methods disagree on a field; confirm the source document.", ["invoice:fields"]))
    if invoice.get("date"):
        try:
            datetime.strptime(invoice["date"], "%Y-%m-%d")
        except ValueError:
            issues.append(_issue("INVALID_DATE", "review", "Invoice date is not a valid YYYY-MM-DD date.", ["invoice:date"]))
    po = reference_po(invoice.get("po") or "", config)
    if not po:
        candidates = [item["id"] for item in config["purchase_orders"] if vendor and item["vendor_id"] == vendor["id"]]
        issues.append(_issue("PO_UNRESOLVED", "review", "Purchase order reference is missing or not found. Candidate orders: " + (", ".join(candidates) or "none"), ["invoice:po", "purchase order register"]))
    elif vendor and po["vendor_id"] != vendor["id"]:
        issues.append(_issue("PO_VENDOR_CONFLICT", "reject", "Purchase order belongs to a different supplier.", ["invoice:po", "invoice:vendor", f"po:{po['id']}"]))
    if po and (invoice.get("currency") or config["currency"]) != po["currency"]:
        issues.append(_issue("CURRENCY_CONFLICT", "reject", "Invoice and purchase order currencies differ.", ["invoice:currency", f"po:{po['id']}"]))
    subtotal, tax, total = (dec(invoice.get(name)) for name in ("subtotal", "tax", "total"))
    for name, value in (("subtotal", subtotal), ("tax", tax), ("total", total)):
        if value is not None and value < 0:
            issues.append(_issue("NEGATIVE_" + name.upper(), "reject", f"Invoice {name} cannot be negative.", [f"invoice:{name}"]))
    if subtotal is None or tax is None:
        issues.append(_issue("TAX_BREAKDOWN_MISSING", "review", "Subtotal or tax is missing, so the gross amount cannot be verified.", ["invoice:subtotal", "invoice:tax"]))
    elif total is not None:
        expected_total = (subtotal + tax).quantize(CENT)
        calculations["invoice_arithmetic"] = f"{subtotal} + {tax} = {expected_total}; stated {total}"
        if abs(expected_total - total) > (dec(policy["line_amount_tolerance"]) or Decimal(0)):
            issues.append(_issue("ARITHMETIC_MISMATCH", "reject", "Invoice subtotal plus tax does not equal its stated total.", ["invoice:subtotal", "invoice:tax", "invoice:total"]))
    if po and subtotal is not None and tax is not None:
        rate = dec(po["tax_rate"]) or Decimal(0)
        expected_tax = (subtotal * rate).quantize(CENT)
        calculations["tax_check"] = f"{subtotal} × {rate} = {expected_tax}; stated {tax}"
        if abs(expected_tax - tax) > (dec(policy["tax_tolerance"]) or Decimal(0)):
            issues.append(_issue("TAX_RATE_MISMATCH", "review", "Tax differs from the configured purchase order rate; a person must check the tax treatment.", ["invoice:tax", f"po:{po['id']}"]))
    line_quantity = Decimal(0)
    line_subtotal = Decimal(0)
    if not invoice.get("lines"):
        issues.append(_issue("LINE_ITEMS_MISSING", "review", "Line items could not be verified against the purchase order and receipts.", ["invoice:lines"]))
    else:
        for index, line in enumerate(invoice["lines"], 1):
            quantity, unit_price, amount = (dec(line.get(name)) for name in ("quantity", "unit_price", "amount"))
            if quantity is None or unit_price is None or amount is None:
                issues.append(_issue("LINE_UNREADABLE", "review", f"Line {index} lacks a valid quantity, unit price or amount.", [f"invoice:line:{index}"]))
                continue
            line_quantity += quantity
            line_subtotal += amount
            if quantity <= 0 or unit_price < 0 or amount < 0:
                issues.append(_issue("INVALID_LINE_VALUE", "reject", f"Line {index} has a nonpositive quantity or negative value.", [f"invoice:line:{index}"]))
            if abs(quantity * unit_price - amount) > (dec(policy["line_amount_tolerance"]) or Decimal(0)):
                issues.append(_issue("LINE_ARITHMETIC", "reject", f"Line {index} amount does not equal quantity times unit price.", [f"invoice:line:{index}"]))
            if po:
                best = max(((ratio(line["description"].casefold(), item["description"].casefold()), item) for item in po["items"]), key=lambda pair: pair[0])
                if best[0] < float(policy["item_match_min"]):
                    issues.append(_issue("ITEM_UNRESOLVED", "review", f"Line {index} description does not clearly match an order item.", [f"invoice:line:{index}", f"po:{po['id']}"]))
                elif best[0] < float(policy["item_auto_approve_min"]):
                    issues.append(_issue("ITEM_ALIAS", "review", f"Line {index} is a possible item match ({best[0]:.0f}%); confirm it.", [f"invoice:line:{index}", f"po:{po['id']}"]))
                if abs(unit_price - (dec(best[1]["unit_price"]) or Decimal(0))) > (dec(policy["unit_price_tolerance"]) or Decimal(0)):
                    issues.append(_issue("UNIT_PRICE_MISMATCH", "review", f"Line {index} unit price differs from the order.", [f"invoice:line:{index}", f"po:{po['id']}"]))
        if subtotal is not None and abs(line_subtotal - subtotal) > (dec(policy["line_amount_tolerance"]) or Decimal(0)):
            issues.append(_issue("LINE_SUM_MISMATCH", "reject", "Line amounts do not sum to the stated subtotal.", ["invoice:lines", "invoice:subtotal"]))
    for previous, old_result in earlier:
        prior = json.loads(previous["parsed"])
        if invoice.get("number") and prior.get("number") and invoice["number"].casefold() == prior["number"].casefold() and vendor and old_result.get("vendor_id") == vendor["id"]:
            code = "EXACT_DUPLICATE" if previous["sha256"] == row["sha256"] else "INVOICE_NUMBER_REUSED"
            issues.append(_issue(code, "reject" if code == "EXACT_DUPLICATE" else "review", "An earlier invoice from this supplier has the same invoice number.", [f"invoice:{row['id']}", f"invoice:{previous['id']}"]))
    credit_amount, credit_qty, credit_sources = _credits(row["id"], events)
    invalid_credit = credit_amount > (total or Decimal(0)) or credit_qty > line_quantity
    applied_credit_amount = Decimal(0) if invalid_credit else credit_amount
    applied_credit_qty = Decimal(0) if invalid_credit else credit_qty
    net_total = (total or Decimal(0)) - applied_credit_amount
    net_quantity = line_quantity - applied_credit_qty
    calculations["net_after_credits"] = f"{total or 0} - {applied_credit_amount} = {net_total}"
    if invalid_credit:
        issues.append(_issue("CREDIT_EXCEEDS_INVOICE", "review", "Credit amount or quantity exceeds the invoice.", [f"invoice:{row['id']}"] + credit_sources))
    if po:
        prior_total = Decimal(0)
        prior_qty = Decimal(0)
        prior_invoices = []
        for previous, result in earlier:
            if result.get("po_id") == po["id"] and result["status"] != "reject":
                prior_total += dec(result.get("net_total")) or Decimal(0)
                prior_qty += dec(result.get("net_quantity")) or Decimal(0)
                prior_invoices.append({"run_id": previous["id"], "filename": previous["filename"], "quantity": result.get("net_quantity", "0"), "gross": result.get("net_total", "0")})
        order_limit = ((dec(po["subtotal"]) or Decimal(0)) * (Decimal(1) + (dec(po["tax_rate"]) or Decimal(0)))).quantize(CENT)
        order_qty = sum((dec(item["quantity"]) or Decimal(0) for item in po["items"]), Decimal(0))
        receipt_qty, receipt_sources = _active_receipt(po, events)
        po_evidence = {**po, **po_capacity(po), "active_received_quantity": str(receipt_qty), "receipt_sources": receipt_sources}
        quantity_exceeded = prior_qty + net_quantity > order_qty
        gross_exceeded = prior_total + net_total > order_limit + (dec(policy["po_amount_tolerance"]) or Decimal(0))
        balances = {"prior_gross": str(prior_total), "current_gross": str(net_total), "cumulative_gross": str(prior_total + net_total), "gross_cap": str(order_limit), "prior_quantity": str(prior_qty), "current_quantity": str(net_quantity), "cumulative_quantity": str(prior_qty + net_quantity), "ordered_quantity": str(order_qty), "received_quantity": str(receipt_qty), "prior_invoices": prior_invoices, "quantity_exceeded": quantity_exceeded, "gross_exceeded": gross_exceeded}
        calculations["cumulative_gross"] = f"{prior_total} + {net_total} = {prior_total + net_total}; PO cap {order_limit}"
        calculations["cumulative_quantity"] = f"{prior_qty} + {net_quantity} = {prior_qty + net_quantity}; ordered {order_qty}; received {receipt_qty}"
        if gross_exceeded or quantity_exceeded:
            issues.append(_issue("PO_EXCEEDED", "reject", "Cumulative invoices exceed the purchase order amount or quantity.", [f"po:{po['id']}", f"invoice:{row['id']}"] + [f"invoice:{previous['id']}" for previous, result in earlier if result.get("po_id") == po["id"]]))
        if po["receipt_required"] and prior_qty + net_quantity > receipt_qty:
            issues.append(_issue("RECEIPT_SHORTFALL", "review", "Invoiced quantity exceeds confirmed received quantity.", [f"po:{po['id']}"] + receipt_sources + [f"invoice:{row['id']}"]))
    status = "reject" if any(item["severity"] == "reject" for item in issues) else "review" if issues else "approve"
    return {"status": status, "config_version": config_version, "vendor_id": vendor["id"] if vendor else None, "vendor_match_score": round(score, 1), "vendor_evidence": vendor, "po_id": po["id"] if po else None, "po_evidence": po_evidence, "balances": balances, "net_total": str(net_total), "net_quantity": str(net_quantity), "issues": issues, "calculations": calculations, "sources": invoice.get("fields", {}), "extraction_method": invoice.get("extraction_method"), "ocr_confidence": invoice.get("ocr_confidence"), "credit_sources": credit_sources}


def _evaluate_rows(invoices: list[sqlite3.Row], events: list[sqlite3.Row], config: dict[str, Any], config_version: int) -> list[tuple[sqlite3.Row, dict[str, Any]]]:
    earlier: list[tuple[sqlite3.Row, dict[str, Any]]] = []
    for row in invoices:
        decision = decide(row, earlier, events, config, config_version)
        earlier.append((row, decision))
    return earlier


def _replay(db: sqlite3.Connection, trigger: str, use_active_policy: bool = False) -> list[int]:
    invoices = db.execute("SELECT * FROM invoices ORDER BY id").fetchall()
    events = db.execute("SELECT * FROM evidence_events ORDER BY id").fetchall()
    active_version, active_config = _active_config(db)
    versions = {row["id"]: json.loads(row["config"]) for row in db.execute("SELECT id,config FROM config_versions")}
    changed: list[int] = []
    earlier: list[tuple[sqlite3.Row, dict[str, Any]]] = []
    for row in invoices:
        old = json.loads(row["decision"]) if row["decision"] else None
        version = active_version if use_active_policy else (old or {}).get("config_version", active_version)
        decision = decide(row, earlier, events, versions.get(version, active_config), version)
        earlier.append((row, decision))
        if old != decision:
            version = row["version"] + 1
            db.execute("UPDATE invoices SET decision=?, status=?, version=? WHERE id=?", (json.dumps(decision), decision["status"], version, row["id"]))
            db.execute("INSERT INTO revisions(invoice_id,version,created_at,trigger,status,decision) VALUES(?,?,?,?,?,?)", (row["id"], version, now(), trigger, decision["status"], json.dumps(decision)))
            changed.append(row["id"])
    db.commit()
    return changed


def preview_config(candidate: dict[str, Any]) -> dict[str, Any]:
    proposed = validate_config(candidate)
    with connect() as db:
        current_version, current = _active_config(db)
        invoices = db.execute("SELECT * FROM invoices ORDER BY id").fetchall()
        events = db.execute("SELECT * FROM evidence_events ORDER BY id").fetchall()
        target_version = current_version + 1 if proposed != current else current_version
        evaluated = _evaluate_rows(invoices, events, proposed, target_version)
    impacts = []
    for row, after in evaluated:
        before = json.loads(row["decision"]) if row["decision"] else {}
        before_codes = [item["code"] for item in before.get("issues", [])]
        after_codes = [item["code"] for item in after["issues"]]
        impacts.append({"id": row["id"], "filename": row["filename"], "before": before.get("status"), "after": after["status"], "status_changed": before.get("status") != after["status"], "before_issues": before_codes, "after_issues": after_codes, "before_calculations": before.get("calculations", {}), "after_calculations": after["calculations"], "po_id": after["po_id"]})
    return {"current_version": current_version, "proposed_version": target_version, "config_changed": proposed != current, "invoices": len(invoices), "status_changes": sum(item["status_changed"] for item in impacts), "impacts": impacts}


def apply_config(candidate: dict[str, Any], changed_by: str, note: str) -> dict[str, Any]:
    proposed = validate_config(candidate)
    if not changed_by.strip() or not note.strip():
        raise ValueError("Reviewer identifier and change reason are required.")
    with connect() as db:
        _, current = _active_config(db)
        if proposed == current:
            raise ValueError("No condition has changed.")
        cursor = db.execute("INSERT INTO config_versions(created_at,changed_by,note,config) VALUES(?,?,?,?)", (now(), changed_by.strip(), note.strip(), json.dumps(proposed)))
        db.commit()
        return {"version": cursor.lastrowid}


def replay_history(changed_by: str, note: str) -> dict[str, Any]:
    """Explicitly re-evaluate saved invoices under the currently active conditions."""
    if not changed_by.strip() or not note.strip():
        raise ValueError("Reviewer identifier and replay reason are required.")
    with connect() as db:
        before = {row["id"]: row["status"] for row in db.execute("SELECT id,status FROM invoices")}
        active_version, _ = _active_config(db)
        revised = _replay(db, f"manual replay of conditions v{active_version} by {changed_by.strip()}: {note.strip()}", use_active_policy=True)
        after = {row["id"]: row["status"] for row in db.execute("SELECT id,status FROM invoices")}
    return {"recomputed": len(before), "revised_runs": revised, "status_changes": sum(before[item] != after[item] for item in before)}


def process_invoice(payload: bytes, filename: str, stage: Callable[[str, str], None] | None = None) -> tuple[int, dict[str, Any]]:
    def emit(name: str, description: str) -> None:
        if stage:
            stage(name, description)
    emit("Read PDF", "Reading document text and running OCR if needed")
    parsed, reading = extract_invoice(payload)
    emit("Extract fields", f"Found {len(parsed['fields'])} fields and {len(parsed['lines'])} line items using {reading['method']}")
    emit("Link evidence", "Looking up supplier, purchase order, receipts and prior invoices")
    with connect() as db:
        cursor = db.execute("INSERT INTO invoices(created_at,filename,sha256,parsed,reading) VALUES(?,?,?,?,?)", (now(), Path(filename).name, hashlib.sha256(payload).hexdigest(), json.dumps(parsed), json.dumps({"pages": reading["pages"], "method": reading["method"], "confidence": reading["confidence"]})))
        invoice_id = cursor.lastrowid
        emit("Calculate decision", "Checking arithmetic, duplicates, cumulative order usage and receiving evidence")
        row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        earlier_rows = db.execute("SELECT * FROM invoices WHERE id<? ORDER BY id", (invoice_id,)).fetchall()
        earlier = [(previous, json.loads(previous["decision"])) for previous in earlier_rows if previous["decision"]]
        events = db.execute("SELECT * FROM evidence_events ORDER BY id").fetchall()
        config_version, config = _active_config(db)
        decision = decide(row, earlier, events, config, config_version)
        db.execute("UPDATE invoices SET decision=?,status=?,version=1 WHERE id=?", (json.dumps(decision), decision["status"], invoice_id))
        db.execute("INSERT INTO revisions(invoice_id,version,created_at,trigger,status,decision) VALUES(?,?,?,?,?,?)", (invoice_id, 1, now(), f"new invoice:{invoice_id}", decision["status"], json.dumps(decision)))
        db.commit()
        emit("Save history", "Decision and source evidence saved")
        return invoice_id, decision


def add_evidence(kind: str, po_id: str, reference: str, quantity: str | None, amount: str | None, note: str, invoice_id: int | None = None, verified_by: str = "", source_pdf: bytes | None = None) -> list[int]:
    po = reference_po(po_id)
    if not po:
        raise ValueError("Purchase order not found.")
    if kind not in {"receipt_correction", "credit"}:
        raise ValueError("Unsupported evidence type.")
    if not reference.strip() or not note.strip() or not verified_by.strip():
        raise ValueError("An evidence reference, explanation and reviewer identifier are required.")
    if not source_pdf or len(source_pdf) > 5_000_000:
        raise ValueError("Upload a supporting PDF smaller than 5 MB.")
    source = read_pdf(source_pdf)
    source_text = source["text"].replace(",", "")
    if reference.strip().casefold() not in source_text.casefold():
        raise ValueError("The evidence reference could not be found in the uploaded PDF.")
    if dec(quantity) is not None:
        quantity_text = format(dec(quantity).normalize(), "f")
        if not re.search(rf"(?<!\d){re.escape(quantity_text)}(?:\.0+)?(?!\d)", source_text):
            raise ValueError("The entered quantity could not be found in the uploaded PDF.")
    if amount is not None and dec(amount) is not None and str(dec(amount).quantize(CENT)) not in source_text:
        raise ValueError("The entered credit amount could not be found in the uploaded PDF.")
    if kind == "receipt_correction":
        if reference not in {item["id"] for item in po["receipts"]}:
            raise ValueError("Receipt reference does not belong to this purchase order.")
        if dec(quantity) is None or dec(quantity) < 0:
            raise ValueError("Enter a nonnegative corrected receipt quantity.")
    if kind == "credit":
        if invoice_id is None or dec(amount) is None or dec(amount) <= 0 or dec(quantity) is None or dec(quantity) < 0:
            raise ValueError("Credit needs an invoice, positive amount and nonnegative quantity.")
    with connect() as db:
        if kind == "credit" and db.execute("SELECT 1 FROM evidence_events WHERE kind='credit' AND po_id=? AND reference=?", (po_id, reference.strip())).fetchone():
            raise ValueError("This credit note reference has already been recorded for the purchase order.")
        if invoice_id is not None:
            row = db.execute("SELECT parsed,decision FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            if not row or json.loads(row["decision"])["po_id"] != po_id:
                raise ValueError("Credited invoice must belong to the selected order.")
            if kind == "credit":
                parsed = json.loads(row["parsed"])
                previous = db.execute("SELECT amount,quantity FROM evidence_events WHERE kind='credit' AND invoice_id=?", (invoice_id,)).fetchall()
                prior_amount = sum((dec(item["amount"]) or Decimal(0) for item in previous), Decimal(0))
                prior_quantity = sum((dec(item["quantity"]) or Decimal(0) for item in previous), Decimal(0))
                line_quantity = sum((dec(item.get("quantity")) or Decimal(0) for item in parsed["lines"]), Decimal(0))
                if prior_amount + (dec(amount) or Decimal(0)) > (dec(parsed.get("total")) or Decimal(0)) or prior_quantity + (dec(quantity) or Decimal(0)) > line_quantity:
                    raise ValueError("Cumulative credits cannot exceed the invoice amount or quantity.")
        cursor = db.execute("INSERT INTO evidence_events(created_at,kind,po_id,invoice_id,reference,quantity,amount,note,verified_by,source_sha256,source_text,source_pdf) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (now(), kind, po_id, invoice_id, reference.strip(), quantity, amount, note.strip(), verified_by.strip(), hashlib.sha256(source_pdf).hexdigest(), source["text"], source_pdf))
        db.commit()
        return _replay(db, f"new {kind} event:{cursor.lastrowid}")


def history() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT id,created_at,filename,status,version,parsed,decision FROM invoices ORDER BY id DESC").fetchall()
    return [{"id": row["id"], "created_at": row["created_at"], "filename": row["filename"], "status": row["status"], "version": row["version"], "policy_version": json.loads(row["decision"]).get("config_version") if row["decision"] else None, "vendor": json.loads(row["parsed"]).get("vendor"), "number": json.loads(row["parsed"]).get("number"), "po": json.loads(row["decision"]).get("po_id") if row["decision"] else None, "total": json.loads(row["parsed"]).get("total")} for row in rows]


def detail(invoice_id: int) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not row:
            raise ValueError("Invoice not found.")
        revisions = db.execute("SELECT version,created_at,trigger,status,decision FROM revisions WHERE invoice_id=? ORDER BY version DESC", (invoice_id,)).fetchall()
    return {"id": row["id"], "filename": row["filename"], "created_at": row["created_at"], "parsed": json.loads(row["parsed"]), "reading": json.loads(row["reading"]), "decision": json.loads(row["decision"]), "revisions": [{"version": item["version"], "created_at": item["created_at"], "trigger": item["trigger"], "status": item["status"], "decision": json.loads(item["decision"])} for item in revisions]}


def events() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id,created_at,kind,po_id,invoice_id,reference,quantity,amount,note,verified_by,source_sha256 FROM evidence_events ORDER BY id DESC").fetchall()]


def evidence_document(event_id: int) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT reference,source_text,source_pdf,source_sha256 FROM evidence_events WHERE id=?", (event_id,)).fetchone()
    if not row:
        raise ValueError("Evidence event not found.")
    return dict(row)
