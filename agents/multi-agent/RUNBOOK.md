# Multi-Agent Paper Pipeline

Stages exactly matching the paper:
1. skills/document-ingestion
2. skills/content-specialist
3. skills/structure-specialist
4. skills/language-specialist
5. skills/chairman-aggregation
6. skills/validation-audit
7. skills/export

Design rule:
- three specialists use the same rubric
- run concurrently when possible
- chairman aggregates and preserves disagreement/veto-style signals
