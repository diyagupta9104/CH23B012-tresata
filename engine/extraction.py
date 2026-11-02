"""Read invoice PDFs and retain the text that supports each extracted field."""

from __future__ import annotations

import json
import os
import re
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pymupdf as fitz
import httpx
from invoice2data import extract_data
from invoice2data.extract.loader import read_templates
from invoice2data.input import pdfium
from rapidocr import RapidOCR

_OCR: RapidOCR | None = None
_TEMPLATES = None
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def _money(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
    try:
        return str(Decimal(cleaned).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return None


def read_pdf(payload: bytes) -> dict[str, Any]:
    if not payload.startswith(b"%PDF"):
        raise ValueError("The uploaded file is not a PDF.")
    if len(payload) > 10_000_000:
        raise ValueError("PDFs larger than 10 MB are outside this prototype's limit.")
    document = fitz.open(stream=payload, filetype="pdf")
    if document.page_count == 0 or document.page_count > 20:
        raise ValueError("Invoices must contain between 1 and 20 pages.")
    pages = [page.get_text(sort=True).strip() for page in document]
    text = "\n".join(pages)
    ocr_lines: list[dict[str, Any]] = []
    digital_chars = sum(len(page) for page in pages)
    method = "digital PDF"
    confidence = 1.0
    if digital_chars < 80:
        global _OCR
        if _OCR is None:
            _OCR = RapidOCR()
        pages = []
        scores: list[float] = []
        for page_number, page in enumerate(document, 1):
            image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
            result = _OCR(image)
            pages.append("\n".join(result.txts or ()))
            scores.extend(result.scores or ())
            ocr_lines.extend({"text": line, "score": round(float(score), 3), "page": page_number} for line, score in zip(result.txts or (), result.scores or ()))
        text = "\n".join(pages)
        confidence = sum(scores) / len(scores) if scores else 0.0
        method = "OCR"
    else:
        # The invoice extraction package provides a second, layout-oriented read.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(payload)
            path = Path(handle.name)
        try:
            alternate = pdfium.to_text(str(path)).strip()
            if len(alternate) >= 80:
                text = alternate
                method = "PDF text (layout reader)"
        except Exception:
            pass
        finally:
            path.unlink(missing_ok=True)
    if not any(page.strip() for page in pages):
        raise ValueError("No readable text was found in this PDF.")
    return {"pages": pages, "text": text, "method": method, "confidence": round(confidence, 3), "ocr_lines": ocr_lines}


def _field(text: str, patterns: list[str]) -> tuple[str | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip(), match.group(0).strip()
    return None, None


def _heuristic_parse(reading: dict[str, Any]) -> dict[str, Any]:
    text = reading["text"]
    patterns = {
        "vendor": [r"^(?:Vendor|Supplier|From)\s*[:#-]\s*(.+)$"],
        "number": [r"^(?:Invoice\s*(?:Number|No\.?|#)|Bill\s*No\.?)\s*[:#-]\s*([A-Z0-9\-/]+)\s*$"],
        "date": [r"^(?:Invoice\s*Date|Date\s*of\s*Invoice|Bill\s*Date)\s*[:#-]\s*([0-9\-/]+)\s*$"],
        "po": [r"^(?:Purchase\s*Order|PO\s*(?:Number|No\.?|#|Ref(?:erence)?))\s*[:#-]\s*([A-Z0-9\-/]+)\s*$"],
        "currency": [r"^Currency\s*[:#-]\s*([A-Z]{3})\s*$"],
        "subtotal": [r"^(?:Subtotal|Net\s*Amount|Taxable\s*Value)\s*[:#-]\s*([^\n]+)$"],
        "tax": [r"^(?:Tax(?:\s*\(.*?\))?|GST(?:\s*\(.*?\))?)\s*[:#-]\s*([^\n]+)$"],
        "total": [r"^(?:Grand\s*Total|Invoice\s*Total|Amount\s*Due|Total\s*Due|Total)\s*[:#-]\s*([^\n]+)$"],
    }
    out: dict[str, Any] = {"fields": {}, "lines": [], "warnings": []}
    for name, choices in patterns.items():
        value, evidence = _field(text, choices)
        if name in {"subtotal", "tax", "total"}:
            value = _money(value)
        out[name] = value
        if evidence:
            out["fields"][name] = {"value": value, "quote": evidence, "page": _page_for(evidence, reading["pages"]), "confidence": _ocr_score(evidence, reading)}
    for line in text.splitlines():
        match = re.match(r"^\s*(.+?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*([\d,]+\.\d{2})\s*\|\s*([\d,]+\.\d{2})\s*$", line)
        if match:
            out["lines"].append({"description": match.group(1).strip(), "quantity": match.group(2), "unit_price": _money(match.group(3)), "amount": _money(match.group(4)), "quote": line.strip(), "page": _page_for(line, reading["pages"]), "confidence": _ocr_score(line, reading)})
    if not out["lines"]:
        # Some layouts lose the visual separators during text extraction.
        for line in text.splitlines():
            match = re.match(r"^\s*([A-Za-z][A-Za-z0-9 ,/-]+?)\s{2,}(\d+(?:\.\d+)?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$", line)
            if match:
                out["lines"].append({"description": match.group(1).strip(), "quantity": match.group(2), "unit_price": _money(match.group(3)), "amount": _money(match.group(4)), "quote": line.strip(), "page": _page_for(line, reading["pages"]), "confidence": _ocr_score(line, reading)})
    return out


def _page_for(quote: str, pages: list[str]) -> int | None:
    for index, page in enumerate(pages, 1):
        if quote in page:
            return index
    return 1 if len(pages) == 1 else None


def _ocr_score(quote: str, reading: dict[str, Any]) -> float | None:
    if reading["method"] != "OCR":
        return None
    return next((item["score"] for item in reading["ocr_lines"] if item["text"].strip() == quote.strip()), None)


def _template_parse(payload: bytes, reading: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    if reading["method"] == "OCR":
        return current
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = read_templates(str(TEMPLATE_DIR))
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(payload)
        path = Path(handle.name)
    try:
        extracted = extract_data(str(path), templates=_TEMPLATES, input_module=pdfium)
    except Exception:
        return current
    finally:
        path.unlink(missing_ok=True)
    if not extracted:
        return current
    field_map = {"vendor": "vendor", "number": "invoice_number", "date": "date", "po": "po", "total": "amount"}
    for field, package_field in field_map.items():
        value = extracted.get(package_field)
        if value is None:
            continue
        if field == "date":
            value = value.strftime("%Y-%m-%d")
        elif field == "total":
            value = _money(str(value))
        else:
            value = str(value).strip()
        if current.get(field) and current[field] != value:
            current["warnings"].append(f"Template and direct extraction disagree on {field}; human review is needed.")
            continue
        quote = next((line.strip() for line in reading["text"].splitlines() if str(value).casefold() in line.casefold()), None)
        if quote:
            current[field] = value
            current["fields"][field] = {"value": value, "quote": quote, "page": _page_for(quote, reading["pages"]), "method": "invoice template + source check"}
    current["template"] = extracted.get("template_name")
    return current


def _model_parse(reading: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return current
    required = ("vendor", "number", "date", "po", "subtotal", "tax", "total")
    if all(current.get(field) for field in required) and current["lines"]:
        return current
    model = os.getenv("EXTRACTION_MODEL", "openrouter/free")
    prompt = ("Extract fields from this invoice. Return only a JSON object with keys vendor, number, "
              "date, po, currency, subtotal, tax, total, lines. Each line has description, quantity, "
              "unit_price, amount. Use null for unknown values. Do not invent data. Do not calculate "
              "missing money fields. Preserve the document's text exactly for identifiers.\n\n" + reading["text"][:25000])
    try:
        response = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}, timeout=35)
        response.raise_for_status()
        proposed = json.loads(response.json()["choices"][0]["message"]["content"])
        if not isinstance(proposed, dict):
            raise ValueError("Model response was not an object")
        for field in required + ("currency",):
            if not current.get(field) and proposed.get(field) is not None:
                value = str(proposed[field]).strip()
                quote = next((line.strip() for line in reading["text"].splitlines() if value.casefold() in line.casefold()), None)
                if quote:
                    current[field] = _money(value) if field in {"subtotal", "tax", "total"} else value
                    current["fields"][field] = {"value": current[field], "quote": quote, "page": _page_for(quote, reading["pages"]), "method": "model + source check"}
                else:
                    current["warnings"].append(f"Model proposed {field}, but no matching source text was found.")
        if not current["lines"] and isinstance(proposed.get("lines"), list):
            for line in proposed["lines"][:30]:
                if not isinstance(line, dict) or not line.get("description"):
                    continue
                quote = next((row.strip() for row in reading["text"].splitlines() if str(line["description"]).casefold() in row.casefold()), None)
                if quote:
                    current["lines"].append({"description": str(line["description"]), "quantity": str(line.get("quantity", "")), "unit_price": _money(str(line.get("unit_price"))), "amount": _money(str(line.get("amount"))), "quote": quote, "page": _page_for(quote, reading["pages"]), "method": "model + source check"})
        current["model"] = model
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
        current["warnings"].append(f"Model extraction unavailable: {type(exc).__name__}")
    return current


def extract_invoice(payload: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    reading = read_pdf(payload)
    parsed = _heuristic_parse(reading)
    parsed = _template_parse(payload, reading, parsed)
    parsed = _model_parse(reading, parsed)
    parsed["extraction_method"] = reading["method"]
    parsed["ocr_confidence"] = reading["confidence"]
    return parsed, reading
