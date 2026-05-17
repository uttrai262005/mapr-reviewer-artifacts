---
name: document-ingestion
description: "Paper-faithful document ingestion for the single-agent grading pipeline. Use to normalize PDF, DOCX, TXT, and image-based submissions into plain text before single-agent grading."
---

Normalize one submission into plain text.

Rules:
- detect file type
- extract PDF/DOCX/TXT directly when possible
- route images or scanned files through OCR when needed
- preserve enough text fidelity for rubric grading
- return one normalized text payload per submission

Primary script: `scripts/ingest.py`
