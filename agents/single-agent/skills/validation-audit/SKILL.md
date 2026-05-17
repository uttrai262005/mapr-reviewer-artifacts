---
name: validation-audit
description: "Validation and audit skill for the paper-faithful single-agent pipeline. Use to ensure one-to-one mapping between submissions and exported scores, and to detect missing or duplicate records."
---

Validate grading records.

Checks:
- one submission -> one score row
- no duplicate student IDs
- no missing exported rows
- preserve extraction/API failure notes

Primary script: `scripts/audit_rows.py`
