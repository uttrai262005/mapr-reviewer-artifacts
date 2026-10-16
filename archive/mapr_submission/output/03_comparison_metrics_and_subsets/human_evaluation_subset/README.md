# Reviewer data package

This directory contains only anonymized derived score tables.

## Included
- `human_subset_scores.xlsx`: human-scored subset used as ground truth for the benchmark subset
- `gpt52_single_full/`: full-dataset totals from the single-agent pipeline
- `gpt52_multi_full/`: full-dataset totals from the multi-agent pipeline
- `gpt4o_full/`: comparison model totals
- `gpt54mini_full/`: comparison model totals
- `gpt54_subset/`: subset totals aligned to the human-scored subset

## Naming
- Assignments are labeled `A1` through `A4` for international reviewer readability.
- Student identifiers are anonymized as `Sxxxx`.
- Public tables use `student_id` instead of local classroom identifiers.
