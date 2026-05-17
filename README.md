# MAPR Reviewer Artifact Repository

This repository is a cleaned, GitHub-ready artifact package for the MAPR submission.

## What is included
- `agents/single-agent/`: the single-agent grading pipeline
- `agents/multi-agent/`: the multi-agent grading pipeline
- `rubric/`: rubric documents for assignments `A1`-`A4`
- `output/anonymized_scores_a1.csv` ... `output/anonymized_scores_a4.csv`: anonymized assignment-level results
- `output/reviewer_data/`: reviewer-safe benchmark inputs for metric recomputation
- `scripts/rebuild_mapr_tables.py`: regenerate the public benchmark tables from the released reviewer package
- `output/mapr_analysis_tables.xlsx` and `output/mapr_analysis_summary.json`: ready-to-inspect benchmark outputs

## Public naming convention
To improve readability for international reviewers:
- original local assignment labels are released publicly as `A1`-`A4`
- local classroom identifier columns are released as `student_id`
- released identifiers are anonymized as `Sxxxx`

## Quick start
```bash
pip install -r requirements.txt
python scripts/rebuild_mapr_tables.py
```

## Repository layout
```text
agents/
  single-agent/
  multi-agent/
rubric/
output/
  anonymized_scores_a1.csv
  anonymized_scores_a2.csv
  anonymized_scores_a3.csv
  anonymized_scores_a4.csv
  reviewer_data/
scripts/
  rebuild_mapr_tables.py
```

## Privacy
This release excludes raw student submissions and any direct personal identifiers. See `DATA_POLICY.md`.

## Reviewer guide
See `ARTIFACTS.md` and `REPRODUCIBILITY.md`.
