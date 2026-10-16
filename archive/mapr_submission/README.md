# MAPR Reviewer Artifact Repository

This repository is a cleaned, GitHub-ready artifact package for the MAPR submission.

## What is included
- `agents/single-agent/`: the single-agent grading pipeline
- `agents/multi-agent/`: the multi-agent grading pipeline
- `rubric/`: rubric documents for assignments `A1`-`A4`
- `output/01_single_agent_results/`: single-agent outputs
- `output/02_multi_agent_results/`: multi-agent outputs
- `output/03_comparison_metrics_and_subsets/`: comparison package, metrics, and human-evaluated subset
- `scripts/rebuild_mapr_tables.py`: regenerate the public benchmark tables from the released reviewer package

## Output structure
```text
output/
  01_single_agent_results/
    assignment_level_scores/
      single_agent_scores_a1.csv
      single_agent_scores_a2.csv
      single_agent_scores_a3.csv
      single_agent_scores_a4.csv
    full_dataset_totals/
      A1.xlsx ... A4.xlsx
  02_multi_agent_results/
    assignment_level_scores/
      multi_agent_scores_a1.xlsx
      multi_agent_scores_a2.xlsx
      multi_agent_scores_a3.xlsx
      multi_agent_scores_a4.xlsx
    full_dataset_totals/
      A1.xlsx ... A4.xlsx
  03_comparison_metrics_and_subsets/
    human_evaluation_subset/
      human_subset_scores.xlsx
      id_map_summary.json
    external_baselines/
      gpt4o_full/
      gpt54mini_full/
      gpt54_subset/
    evaluation_reports/
      benchmark_metrics_tables.xlsx
      benchmark_metrics_summary.json
      single_vs_multi_ablation.xlsx
      validation_audit_summary.json
```

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

## Privacy
This release excludes raw student submissions and any direct personal identifiers. See `DATA_POLICY.md`.

## Reviewer guide
See `ARTIFACTS.md`, `REPRODUCIBILITY.md`, and `output/README.md`.
