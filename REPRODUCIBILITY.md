# Reproducibility

## Environment
- Python 3.10+

## Install
```bash
pip install -r requirements.txt
```

## Rebuild benchmark tables
```bash
python scripts/rebuild_mapr_tables.py
```

This regenerates:
- `output/03_comparison_metrics_and_subsets/evaluation_reports/benchmark_metrics_tables.xlsx`
- `output/03_comparison_metrics_and_subsets/evaluation_reports/benchmark_metrics_summary.json`

## Public analysis inputs
The released inputs used by the benchmark script are organized as follows:
- `output/01_single_agent_results/full_dataset_totals/`
- `output/02_multi_agent_results/full_dataset_totals/`
- `output/03_comparison_metrics_and_subsets/human_evaluation_subset/`
- `output/03_comparison_metrics_and_subsets/external_baselines/`

## Assignment naming
For reviewer readability, assignments are labeled `A1` through `A4` in the public package.
