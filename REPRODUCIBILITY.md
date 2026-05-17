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
- `output/mapr_analysis_tables.xlsx`
- `output/mapr_analysis_summary.json`

## Public analysis inputs
The released inputs used by the benchmark script are in `output/reviewer_data/`.

## Assignment naming
For reviewer readability, assignments are labeled `A1` through `A4` in the public package.
