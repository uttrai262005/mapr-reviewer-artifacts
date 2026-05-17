# Single-Agent Paper Pipeline

Stages exactly matching the paper:
1. skills/document-ingestion
2. skills/agentic-evaluation
3. skills/validation-audit
4. skills/export

Design rule:
- exactly one LLM grading call per submission
- full rubric in that call
- output is auditable Excel rows
