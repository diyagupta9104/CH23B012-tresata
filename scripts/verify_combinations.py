"""Bounded combination checks using real PDFs and isolated SQLite databases."""

from __future__ import annotations

import copy
import itertools
import json
import os
import sys
import tempfile
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    counts = Counter()
    failures = []
    with tempfile.TemporaryDirectory() as temp:
        os.environ["INVOICE_DB"] = str(Path(temp) / "initial.db")
        import engine.workflow as w

        # Reuse extraction only for identical bytes; database and decisions run afresh.
        w.extract_invoice = lru_cache(maxsize=32)(w.extract_invoice)
        base = copy.deepcopy(w.get_config()[1])
        pdfs = {name: (ROOT / "samples" / name).read_bytes() for name in (
            "01_standard.pdf", "02_split_order.pdf", "03_duplicate.pdf",
            "04_freight_first.pdf", "05_freight_overspend.pdf",
        )}
        first, second = "04_freight_first.pdf", "05_freight_overspend.pdf"
        scenario = 0

        def fresh():
            nonlocal scenario
            scenario += 1
            w.DB_PATH = Path(temp) / f"scenario-{scenario}.db"

        def check(group, label, operation):
            try:
                operation()
                counts[group] += 1
            except Exception as exc:
                failures.append({"group": group, "case": label, "error": repr(exc)})

        def setup(cap=225, received=200, required=True):
            config = copy.deepcopy(base)
            po = next(p for p in config["purchase_orders"] if p["id"] == "PO-1002")
            po["items"][0]["quantity"] = str(cap)
            po["subtotal"] = f"{cap * 1000:.2f}"
            po["receipts"][0]["quantity"] = str(received)
            po["receipt_required"] = required
            if config != w.get_config()[1]:
                w.apply_config(config, "verification", "Combination scenario")
            return config

        def credit(invoice_id):
            return w.add_evidence("credit", "PO-1002", "CN-4101", "50", "59000.00", "Credit scenario", invoice_id, "verification", (ROOT / "sample_evidence/credit_note.pdf").read_bytes())

        def receipt():
            return w.add_evidence("receipt_correction", "PO-1002", "GRN-1002", "225", None, "Receipt scenario", verified_by="verification", source_pdf=(ROOT / "sample_evidence/receipt_amendment_225.pdf").read_bytes())

        for order, cap, received, required, credited in itertools.product(
            itertools.permutations((first, second)), (74, 149, 150, 200, 224, 225, 250),
            (0, 74, 150, 200, 224, 225, 250), (False, True), (False, True),
        ):
            def capacity_case():
                fresh()
                setup(cap, received, required)
                ids = {name: w.process_invoice(pdfs[name], name)[0] for name in order}
                if credited:
                    credit(ids[first])
                previous_quantity = 0
                for name in order:
                    qty = (100 if credited else 150) if name == first else 75
                    total = previous_quantity + qty
                    expected = "reject" if total > cap else "review" if required and total > received else "approve"
                    result = w.detail(ids[name])["decision"]
                    assert result["status"] == expected, (name, expected, result["status"])
                    assert int(result["balances"]["cumulative_quantity"]) == total
                    assert float(result["net_total"]) == qty * 1180
                    if expected != "reject":
                        previous_quantity += qty
                before = w.history()
                assert not w.replay_history("verification", "Same conditions")["revised_runs"]
                assert w.history() == before
            check("capacity_receipt_credit", [list(order), cap, received, required, credited], capacity_case)

        for order in itertools.permutations(("04", "05", "save", "receipt", "credit")):
            if order.index("credit") < order.index("04"):
                continue
            def timeline_case():
                fresh()
                ids = {}
                for action in order:
                    if action in ("04", "05"):
                        name = first if action == "04" else second
                        ids[action] = w.process_invoice(pdfs[name], name)[0]
                    elif action == "save":
                        before = {i: w.detail(i) for i in ids.values()}
                        setup()
                        assert before == {i: w.detail(i) for i in ids.values()}
                    elif action == "receipt":
                        receipt()
                    else:
                        credit(ids["04"])
                before_preview = w.history()
                preview = w.preview_config(w.get_config()[1])
                assert w.history() == before_preview
                w.replay_history("verification", "Apply saved conditions")
                for item in preview["impacts"]:
                    assert w.detail(item["id"])["decision"]["status"] == item["after"] == "approve"
                assert not w.replay_history("verification", "Repeated replay")["revised_runs"]
            check("event_order", list(order), timeline_case)

        for order in itertools.permutations(("01_standard.pdf", "02_split_order.pdf", "03_duplicate.pdf")):
            def duplicate_case():
                fresh()
                seen = False
                for name in order:
                    _, result = w.process_invoice(pdfs[name], name)
                    is_duplicate = name != "02_split_order.pdf" and seen
                    assert result["status"] == ("reject" if is_duplicate else "approve")
                    if name != "02_split_order.pdf":
                        seen = True
                assert not w.replay_history("verification", "Stable duplicate sequence")["revised_runs"]
            check("duplicate_order", list(order), duplicate_case)

        for reset_conditions in (False, True):
            def clear_case():
                fresh()
                setup()
                invoice_id, _ = w.process_invoice(pdfs[first], first)
                credit(invoice_id)
                version = w.get_config()[0]
                w.clear_history("CLEAR", reset_conditions=reset_conditions)
                assert not w.history() and not w.events()
                assert w.get_config()[0] == (1 if reset_conditions else version)
                assert not w.replay_history("verification", "Empty replay")["revised_runs"]
                assert w.process_invoice(pdfs[first], first)[1]["status"] == "approve"
            check("clear_and_restart", reset_conditions, clear_case)

        for invalid in ("negative_quantity", "nan_quantity", "bad_subtotal", "bad_thresholds", "negative_tolerance", "bad_tax"):
            def invalid_config_case():
                fresh()
                config = copy.deepcopy(base)
                po = config["purchase_orders"][0]
                if invalid == "negative_quantity": po["items"][0]["quantity"] = "-1"
                if invalid == "nan_quantity": po["items"][0]["quantity"] = "NaN"
                if invalid == "bad_subtotal": po["subtotal"] = "1"
                if invalid == "bad_thresholds": config["policy"]["vendor_match_min"] = 101
                if invalid == "negative_tolerance": config["policy"]["tax_tolerance"] = "-1"
                if invalid == "bad_tax": po["tax_rate"] = "2"
                try:
                    w.apply_config(config, "verification", "Invalid settings")
                except ValueError:
                    assert w.get_config()[0] == 1
                else:
                    raise AssertionError("Invalid condition was accepted")
            check("invalid_conditions", invalid, invalid_config_case)

        for invalid in ("missing_document", "wrong_quantity", "wrong_po", "missing_reviewer", "duplicate_credit"):
            def invalid_evidence_case():
                fresh()
                invoice_id, _ = w.process_invoice(pdfs[first], first)
                params = dict(kind="credit", po_id="PO-1002", reference="CN-4101", quantity="50", amount="59000.00", note="Validation", invoice_id=invoice_id, verified_by="verification", source_pdf=(ROOT / "sample_evidence/credit_note.pdf").read_bytes())
                if invalid == "missing_document": params["source_pdf"] = None
                if invalid == "wrong_quantity": params["quantity"] = "999"
                if invalid == "wrong_po": params["po_id"] = "PO-1001"
                if invalid == "missing_reviewer": params["verified_by"] = ""
                if invalid == "duplicate_credit": credit(invoice_id)
                before = (w.events(), w.detail(invoice_id))
                try:
                    w.add_evidence(**params)
                except ValueError:
                    assert before == (w.events(), w.detail(invoice_id))
                else:
                    raise AssertionError("Invalid evidence was accepted")
            check("invalid_evidence", invalid, invalid_evidence_case)

    report = {"passed": sum(counts.values()), "failed": len(failures), "groups": dict(counts), "failures": failures,
              "coverage": "Exhaustive within the listed finite grids, not every possible document or numeric input. Identical PDF bytes share cached real extraction; every scenario uses a fresh database. OCR and all 13 layouts are exercised separately by evaluate.py."}
    (ROOT / "reports/combinations.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
