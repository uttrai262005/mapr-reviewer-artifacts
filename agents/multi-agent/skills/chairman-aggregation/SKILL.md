---
name: chairman-aggregation
description: "Paper-faithful chairman aggregation skill for the multi-agent grading pipeline. Use to combine the three specialist JSON outputs, compute disagreement/spread, and produce the final record."
---

Combine the three specialist outputs.

Rules:
- keep all specialists on the same rubric
- aggregate their JSON outputs
- preserve spread/disagreement signal
- emit a final auditable record

Primary script: `scripts/combine.py`
