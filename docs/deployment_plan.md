# Deployment and sharing plan

## Local prototype

Run the application from the repository root with Python 3.12 and Streamlit:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The default workflow uses synthetic PDFs bundled in the repository. The local SQLite database stores decisions, condition versions, evidence events, and audit revisions for the session.

## Optional public prototype

If the repository is shared publicly, keep the bundled documents synthetic and use a fresh disposable database for the demo. A hosted prototype should expose the bundled selectors and should not be used for real invoices or confidential documents.

The current application is SQLite-specific and suitable for a single-instance prototype. Durable multi-user use would require authenticated users, protected object storage, backups, access control, effective-dated amendments, and a managed relational database.

## Production boundary

Before real financial use, add reviewer authentication, approval authority enforcement, verified purchase-order amendments, controlled evidence provenance, encryption, retention rules, labeled accuracy evaluation, false-approval monitoring, and a formal payment-control boundary.
