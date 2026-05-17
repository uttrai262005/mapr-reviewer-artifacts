---
name: agentic-evaluation
description: "Paper-faithful single-agent grading skill. Use to grade one normalized submission with the full instructor rubric in exactly one LLM call and return structured JSON."
---

Grade one submission in one pass.

Rules:
- use the full rubric
- make exactly one grading call per submission
- return structured JSON only
- score all criteria in the same response
- do not split the grading task across specialist agents

Primary script: `scripts/grade_once.py`
