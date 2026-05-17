# Artifact guide

## Core code
- `agents/single-agent/`: Phase 1 single-agent pipeline
- `agents/multi-agent/`: Phase 2 multi-agent pipeline
- `rubric/`: rubric documents for A1-A4

## Output groups

### 1. Single-agent results
Path: `output/01_single_agent_results/`
- `assignment_level_scores/single_agent_scores_a1.csv` ... `single_agent_scores_a4.csv`
- `full_dataset_totals/A1.xlsx` ... `A4.xlsx`

### 2. Multi-agent results
Path: `output/02_multi_agent_results/`
- `full_dataset_totals/A1.xlsx` ... `A4.xlsx`

### 3. Comparison metrics and subsets
Path: `output/03_comparison_metrics_and_subsets/`
- `human_evaluation_subset/human_subset_scores.xlsx`
- `human_evaluation_subset/id_map_summary.json`
- `external_baselines/gpt4o_full/A1.xlsx` ... `A4.xlsx`
- `external_baselines/gpt54mini_full/A1.xlsx` ... `A4.xlsx`
- `external_baselines/gpt54_subset/A1.xlsx` ... `A4.xlsx`
- `evaluation_reports/benchmark_metrics_tables.xlsx`
- `evaluation_reports/benchmark_metrics_summary.json`
- `evaluation_reports/single_vs_multi_ablation.xlsx`
- `evaluation_reports/validation_audit_summary.json`

## Naming note
`A1`-`A4` are the public reviewer labels corresponding to the four course assignments.
