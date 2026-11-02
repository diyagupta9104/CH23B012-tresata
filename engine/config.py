"""Validation for versioned purchase-order and decision settings."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
from typing import Any


def number(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if not result.is_finite():
        raise ValueError(f"{label} must be a finite number.")
    return result


def validate_config(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a safe copy or explain why a proposed configuration cannot run."""
    config = copy.deepcopy(candidate)
    currency = config.get("currency")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise ValueError("Base currency must be a three-letter code.")
    vendors = config.get("vendors")
    orders = config.get("purchase_orders")
    if not isinstance(vendors, list) or not 1 <= len(vendors) <= 100:
        raise ValueError("Add between 1 and 100 vendors.")
    if not isinstance(orders, list) or not 1 <= len(orders) <= 100:
        raise ValueError("Add between 1 and 100 purchase orders.")
    vendor_ids = set()
    for vendor in vendors:
        if not vendor.get("id") or not vendor.get("name") or type(vendor.get("approved")) is not bool:
            raise ValueError("Every vendor needs an ID, name and approval flag.")
        if vendor["id"] in vendor_ids:
            raise ValueError(f"Vendor ID {vendor['id']} is repeated.")
        vendor_ids.add(vendor["id"])
    order_ids = set()
    for po in orders:
        if not po.get("id") or po["id"] in order_ids:
            raise ValueError("Each purchase order needs a unique ID.")
        order_ids.add(po["id"])
        if po.get("vendor_id") not in vendor_ids:
            raise ValueError(f"PO {po['id']} has no matching vendor.")
        if po.get("currency") != currency:
            raise ValueError(f"PO {po['id']} currency must match the configured currency.")
        rate = number(po.get("tax_rate"), f"PO {po['id']} tax rate")
        if not 0 <= rate <= 1:
            raise ValueError(f"PO {po['id']} tax rate must be between 0 and 1.")
        if type(po.get("receipt_required")) is not bool:
            raise ValueError(f"PO {po['id']} needs a receipt-required setting.")
        if not isinstance(po.get("items"), list) or not po["items"]:
            raise ValueError(f"PO {po['id']} needs at least one line item.")
        subtotal = Decimal(0)
        for item in po["items"]:
            if not item.get("description"):
                raise ValueError(f"PO {po['id']} has an item without a description.")
            qty = number(item.get("quantity"), f"PO {po['id']} item quantity")
            price = number(item.get("unit_price"), f"PO {po['id']} unit price")
            if qty <= 0 or price < 0:
                raise ValueError(f"PO {po['id']} needs positive quantities and nonnegative prices.")
            subtotal += qty * price
        declared = number(po.get("subtotal"), f"PO {po['id']} subtotal")
        if abs(subtotal - declared) > Decimal("0.01"):
            raise ValueError(f"PO {po['id']} subtotal must equal quantity × unit price across its items.")
        if not isinstance(po.get("receipts"), list):
            raise ValueError(f"PO {po['id']} receipts must be a list.")
        receipt_ids = set()
        for receipt in po["receipts"]:
            if not receipt.get("id") or receipt["id"] in receipt_ids:
                raise ValueError(f"PO {po['id']} receipt IDs must be unique.")
            receipt_ids.add(receipt["id"])
            if number(receipt.get("quantity"), f"PO {po['id']} received quantity") < 0:
                raise ValueError(f"PO {po['id']} received quantity cannot be negative.")
        if po["receipt_required"] and not po["receipts"]:
            raise ValueError(f"PO {po['id']} requires a receipt record.")
    policy = config.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("Decision policy is missing.")
    for low, high in (("vendor_match_min", "vendor_auto_approve_min"), ("item_match_min", "item_auto_approve_min")):
        minimum = number(policy.get(low), low)
        automatic = number(policy.get(high), high)
        if not 0 <= minimum <= automatic <= 100:
            raise ValueError(f"{low} and {high} must be ordered percentages between 0 and 100.")
    for key in ("ocr_average_min", "ocr_line_min"):
        if not 0 <= number(policy.get(key), key) <= 1:
            raise ValueError(f"{key} must be between 0 and 1.")
    for key in ("tax_tolerance", "po_amount_tolerance", "unit_price_tolerance", "line_amount_tolerance"):
        if number(policy.get(key), key) < 0:
            raise ValueError(f"{key} cannot be negative.")
    return config


def po_capacity(po: dict[str, Any]) -> dict[str, str]:
    quantity = sum((number(item["quantity"], "quantity") for item in po["items"]), Decimal(0))
    gross = (number(po["subtotal"], "subtotal") * (Decimal(1) + number(po["tax_rate"], "tax rate"))).quantize(Decimal("0.01"))
    received = sum((number(item["quantity"], "receipt quantity") for item in po["receipts"]), Decimal(0))
    return {"ordered_quantity": str(quantity), "received_quantity": str(received), "gross_cap": str(gross)}
