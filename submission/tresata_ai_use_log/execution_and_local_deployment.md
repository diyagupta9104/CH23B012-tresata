# Execution and local deployment record

## Build

The prototype is a Python 3.12-compatible Streamlit application. Its runtime components are:

- `app.py` for the user interface and workflow entrypoint.
- `engine/extraction.py` for PDF text extraction, OCR, and optional candidate proposals.
- `engine/workflow.py` for state, matching, rules, decisions, and replay.
- `engine/config.py` for policy validation and purchase-order calculations.
- `data/reference.json` for synthetic suppliers, purchase orders, receipts, and policy.
- SQLite for local condition versions, evidence events, decisions, and revisions.

The standard workflow does not require an external model API key. The optional model path is nonessential and is constrained by source-text checks.

## Local run

The application was run locally with Streamlit from the repository root. The documented start command is:

```powershell
python -m streamlit run app.py
```

The local app exposes processing, conditions and replay, later evidence, history and audit, and a test guide. It accepts bundled synthetic PDFs and can also process an uploaded PDF in the normal local mode.

## Verification

The repository contains 13 generated invoice PDFs. The recorded evaluation reports all 13 initial expected statuses as observed correctly, including one OCR case. The combination checks cover policy changes, historical replay, receipt corrections, credit notes, duplicates, and invalid-input behavior.

The test artifacts are:

- `reports/evaluation.json`
- `reports/combinations.json`
- `docs/testing_guide.md`

## What is and is not claimed

This verifies that the bounded workflow runs on the synthetic corpus. It does not claim real-world extraction accuracy, handwriting coverage, multilingual coverage, document-tampering detection, or legal/tax correctness.

There is evidence of a local run and local test artifacts. There is no verified public hosting URL or screen recording in this archive. Do not describe the application as publicly deployed unless that is completed and independently checked.
