"""Run the real workflow on synthetic PDFs and record observed outcomes."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
sys.path.insert(0, str(ROOT))

EXPECTED = {
    "01_standard.pdf": "approve",
    "02_split_order.pdf": "approve",
    "03_duplicate.pdf": "reject",
    "04_freight_first.pdf": "approve",
    "05_freight_overspend.pdf": "reject",
    "06_tax_inclusive.pdf": "approve",
    "07_missing_po.pdf": "review",
    "08_missing_number.pdf": "review",
    "09_receipt_recheck.pdf": "approve",
    "10_unapproved_vendor.pdf": "reject",
    "11_scanned_invoice.pdf": "approve",
    "12_arithmetic_error.pdf": "reject",
    "13_bundled_line.pdf": "review",
}


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        os.environ["INVOICE_DB"] = str(Path(temp) / "evaluation.db")
        import engine.workflow as workflow
        from engine.workflow import add_evidence, apply_config, clear_history, detail, events, get_config, history, preview_config, process_invoice, replay_history

        observations = []
        ids = {}
        for filename, expected in EXPECTED.items():
            invoice_id, result = process_invoice((SAMPLES / filename).read_bytes(), filename)
            ids[filename] = invoice_id
            observations.append({"file": filename, "expected": expected, "observed": result["status"], "issue_codes": [issue["code"] for issue in result["issues"]], "pass": result["status"] == expected, "method": result["extraction_method"]})
            print(f"{filename}: expected={expected}, observed={result['status']}")
        initial_version, initial_config = get_config()
        proposed = copy.deepcopy(initial_config)
        freight_po = next(po for po in proposed["purchase_orders"] if po["id"] == "PO-1002")
        freight_po["items"][0]["quantity"] = "250"
        freight_po["subtotal"] = "250000.00"
        preview = preview_config(proposed)
        freight_impact = next(item for item in preview["impacts"] if item["id"] == ids["05_freight_overspend.pdf"])
        preview_check = freight_impact["before"] == "reject" and freight_impact["after"] == "review" and preview["status_changes"] >= 1
        applied = apply_config(proposed, "evaluation-reviewer", "Synthetic PO capacity scenario")
        after_policy = detail(ids["05_freight_overspend.pdf"])["decision"]
        save_only_check = after_policy["status"] == "reject" and after_policy["config_version"] == initial_version and applied["version"] == initial_version + 1
        replayed = replay_history("evaluation-reviewer", "Apply saved PO capacity to historical invoices")
        after_replay = detail(ids["05_freight_overspend.pdf"])["decision"]["status"]
        replay_check = after_replay == "review" and ids["05_freight_overspend.pdf"] in replayed["revised_runs"]
        unchanged_replay = replay_history("evaluation-reviewer", "Verify a repeated rerun is stable")
        unchanged_check = not unchanged_replay["revised_runs"] and unchanged_replay["status_changes"] == 0
        changed_freight_receipt = add_evidence("receipt_correction", "PO-1002", "GRN-1002", "250", None, "Synthetic receipt correction following PO scenario", verified_by="evaluation-reviewer", source_pdf=(ROOT / "sample_evidence" / "receipt_amendment_250.pdf").read_bytes())
        after_freight_receipt = detail(ids["05_freight_overspend.pdf"])["decision"]["status"]
        freight_receipt_check = after_freight_receipt == "approve" and ids["05_freight_overspend.pdf"] in changed_freight_receipt
        restored = apply_config(initial_config, "evaluation-reviewer", "Restore initial PO capacity for credit scenario")
        before_restore_replay = detail(ids["05_freight_overspend.pdf"])["decision"]["status"]
        replay_history("evaluation-reviewer", "Apply restored PO capacity to historical invoices")
        after_restore = detail(ids["05_freight_overspend.pdf"])["decision"]["status"]
        restore_check = before_restore_replay == "approve" and after_restore == "reject" and restored["version"] == initial_version + 2
        before_credit = detail(ids["05_freight_overspend.pdf"])["decision"]["status"]
        changed_credit = add_evidence("credit", "PO-1002", "CN-4101", "50", "59000.00", "Synthetic vendor credit for 50 freight pallets", ids["04_freight_first.pdf"], "evaluation-reviewer", (ROOT / "sample_evidence" / "credit_note.pdf").read_bytes())
        after_credit = detail(ids["05_freight_overspend.pdf"])["decision"]["status"]
        credit_check = before_credit == "reject" and after_credit == "approve" and ids["05_freight_overspend.pdf"] in changed_credit
        before_receipt = detail(ids["06_tax_inclusive.pdf"])["decision"]["status"]
        changed_receipt = add_evidence("receipt_correction", "PO-1003", "GRN-1003", "10", None, "Synthetic recount found only 10 chairs", verified_by="evaluation-reviewer", source_pdf=(ROOT / "sample_evidence" / "receipt_correction.pdf").read_bytes())
        after_receipt = detail(ids["06_tax_inclusive.pdf"])["decision"]["status"]
        receipt_check = before_receipt == "approve" and after_receipt == "review" and ids["06_tax_inclusive.pdf"] in changed_receipt
        try:
            clear_history("incorrect")
            rejected_unconfirmed = False
        except ValueError:
            rejected_unconfirmed = True
        reset_counts = clear_history("CLEAR", reset_conditions=True)
        reset_check = rejected_unconfirmed and reset_counts["invoices"] == len(EXPECTED) and not history() and not events() and get_config()[0] == 1
        workflow.DB_PATH = Path(temp) / "future_conditions.db"
        future_first_id, future_first = process_invoice((SAMPLES / "04_freight_first.pdf").read_bytes(), "04_freight_first.pdf")
        apply_config(proposed, "evaluation-reviewer", "Future-only PO capacity")
        saved_first = detail(future_first_id)["decision"]
        future_second_id, future_second = process_invoice((SAMPLES / "05_freight_overspend.pdf").read_bytes(), "05_freight_overspend.pdf")
        future_only_check = future_first["status"] == "approve" and saved_first["config_version"] == 1 and saved_first["status"] == "approve" and future_second["status"] == "review" and future_second["config_version"] == 2
        add_evidence("receipt_correction", "PO-1002", "GRN-1002", "250", None, "Synthetic receipt correction after future-only condition", verified_by="evaluation-reviewer", source_pdf=(ROOT / "sample_evidence" / "receipt_amendment_250.pdf").read_bytes())
        evidence_policy_check = detail(future_first_id)["decision"]["config_version"] == 1 and detail(future_second_id)["decision"]["config_version"] == 2 and detail(future_second_id)["decision"]["status"] == "approve"
        preserved_counts = clear_history("CLEAR")
        new_first_id, new_first = process_invoice((SAMPLES / "04_freight_first.pdf").read_bytes(), "04_freight_first.pdf")
        preserve_conditions_check = preserved_counts["invoices"] == 2 and get_config()[0] == 2 and new_first_id == 1 and new_first["config_version"] == 2
        workflow.DB_PATH = Path(temp) / "exact_225.db"
        _, exact_config = get_config()
        exact_config = copy.deepcopy(exact_config)
        exact_po = next(po for po in exact_config["purchase_orders"] if po["id"] == "PO-1002")
        exact_po["items"][0]["quantity"] = "225"
        exact_po["subtotal"] = "225000.00"
        apply_config(exact_config, "evaluation-reviewer", "Set exact freight PO capacity to 225")
        _, exact_first = process_invoice((SAMPLES / "04_freight_first.pdf").read_bytes(), "04_freight_first.pdf")
        exact_second_id, exact_second = process_invoice((SAMPLES / "05_freight_overspend.pdf").read_bytes(), "05_freight_overspend.pdf")
        exact_codes = [item["code"] for item in exact_second["issues"]]
        exact_225_check = exact_first["status"] == "approve" and exact_second["status"] == "review" and exact_codes == ["RECEIPT_SHORTFALL"] and exact_second["balances"]["cumulative_quantity"] == exact_second["balances"]["ordered_quantity"] == "225" and exact_second["balances"]["cumulative_gross"] == exact_second["balances"]["gross_cap"] == "265500.00"
        add_evidence("receipt_correction", "PO-1002", "GRN-1002", "225", None, "Synthetic receipt correction for exact PO capacity", verified_by="evaluation-reviewer", source_pdf=(ROOT / "sample_evidence" / "receipt_amendment_225.pdf").read_bytes())
        exact_receipt_check = detail(exact_second_id)["decision"]["status"] == "approve"
        report = {
            "dataset": "13 synthetic PDFs generated by scripts/make_samples.py; one is rasterized to require OCR",
            "cases": observations,
            "initial_outcomes_correct": sum(case["pass"] for case in observations),
            "initial_cases": len(observations),
            "policy_preview": {"before": freight_impact["before"], "after": freight_impact["after"], "status_changes": preview["status_changes"], "pass": preview_check},
            "save_conditions_without_replay": {"status": after_policy["status"], "original_conditions_version": after_policy["config_version"], "pass": save_only_check},
            "manual_policy_replay": {"after": after_replay, "recomputed": replayed["recomputed"], "pass": replay_check},
            "repeat_replay": {"revised_runs": unchanged_replay["revised_runs"], "pass": unchanged_check},
            "future_invoice_uses_new_conditions": {"status": future_second["status"], "conditions_version": future_second["config_version"], "pass": future_only_check},
            "later_evidence_preserves_invoice_conditions": {"pass": evidence_policy_check},
            "freight_receipt_replay": {"after": after_freight_receipt, "pass": freight_receipt_check},
            "restore_policy": {"after": after_restore, "pass": restore_check},
            "credit_replay": {"before": before_credit, "after": after_credit, "changed_runs": changed_credit, "pass": credit_check},
            "receipt_replay": {"before": before_receipt, "after": after_receipt, "changed_runs": changed_receipt, "pass": receipt_check},
            "history_reset": {"removed": reset_counts, "pass": reset_check},
            "clear_history_keeps_conditions": {"active_version": get_config()[0], "pass": preserve_conditions_check},
            "exact_225_po_limit": {"status": exact_second["status"], "issues": exact_codes, "balances": exact_second["balances"], "pass": exact_225_check},
            "exact_225_with_receipt": {"status": detail(exact_second_id)["decision"]["status"], "pass": exact_receipt_check},
            "known_limits": ["The PDFs use a small set of generated layouts and should not be treated as a measured accuracy rate on real vendor invoices.", "A bundled line without quantity and unit price is routed to review rather than inferred.", "This evaluation does not measure handwriting, multilingual scans, nonstandard tax regimes or document tampering."],
        }
        destination = ROOT / "reports" / "evaluation.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved {destination}")
        if not all(case["pass"] for case in observations) or not all((preview_check, save_only_check, replay_check, unchanged_check, future_only_check, evidence_policy_check, freight_receipt_check, restore_check, credit_check, receipt_check, reset_check, preserve_conditions_check, exact_225_check, exact_receipt_check)):
            raise SystemExit("Evaluation found a mismatch; inspect reports/evaluation.json")


if __name__ == "__main__":
    main()
