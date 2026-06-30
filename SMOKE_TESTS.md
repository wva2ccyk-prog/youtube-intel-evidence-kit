# Smoke Tests

These checks use only local synthetic fixtures and do not require paid APIs, YouTube downloads, OCR, ASR, or external source verification.

## Install

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install -e .[dev]
```

## Run

```bash
python -m pytest -q tests/test_public_smoke.py
```

Expected result:

```text
2 passed
```

## Optional Broader Local Check

Optional broader check after adding new files:

```bash
python -m pytest -q
```

This should remain synthetic-only. Do not add tests that require real videos, provider credentials, network access, or private runtime artifacts by default.
