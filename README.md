# Artifacts: Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce Essays

Artifact repository of the FISAT 2026 paper *"Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce
Essays: A Cross-Model Study with Aggregation-Strategy Ablation"* (T. T. Trinh, T. D. Nguyen, N. U. Nguyen).

All **520** submissions (A1 137, A2 129, A3 123, A4 131) were scored by two human TAs; GT = mean of the two scores.
Systems: single-agent and multi-agent (Content / Structure / Language specialists + Chairman) on **GPT-5.2** and
**DeepSeek-V4-Flash**. Student identifiers are anonymized (`S0001`-`S0520`, random, no link to real IDs).

## Reproduce (no private data needed)
```bash
pip install -r requirements.txt
python scripts/build_release.py --repo .                 # QWK exactly as in the paper (observed-label mode)
python scripts/build_release.py --repo . --qwk-labels fixed   # sensitivity: full 0-10 label set
```
Output: `results/*.csv`, `results/fig3_pred_vs_gt.png`, `results/fig4_cross_model_qwk.png`, `results/verification_report.csv`.

## Paper -> file map
| Paper item | File |
|---|---|
| Table 1 (dataset, human agreement) | `results/table1_dataset_human.csv` |
| Table 2 (single-agent GPT-5.2) | `results/table2_single_agent_gpt52.csv` |
| Table 3 (multi-agent GPT-5.2) | `results/table3_multi_agent_gpt52.csv` |
| Table 4 (bias, Pearson, Spearman) | `results/table4_bias_and_rank_correlation.csv` |
| Table 5 (specialist disagreement) | `results/table5_specialist_disagreement.csv` |
| Table 6 (aggregation ablation) | `results/table6_aggregation_ablation.csv` (needs `data/specialists_gpt52.csv`) |
| Table 7 / Fig. 4 (cross-model) | `results/table7_cross_model.csv`, `results/fig4_cross_model_qwk.png` |
| Fig. 3 (pred vs GT) | `results/fig3_pred_vs_gt.png` |
| Section 5 numbers vs recomputed | `results/verification_report.csv` |

## Data (`data/`)
| File | Content |
|---|---|
| `scores_master.csv` | one row per submission: `assignment, student_id, rater1, rater2, gt, single_gpt52, multi_gpt52, single_deepseek, multi_deepseek` (+ `*_raw`, `*_source` provenance columns) |
| `specialists_deepseek.csv` | DeepSeek multi-agent specialist totals, spread, veto (A3 only) |
| `specialists_gpt52.csv` | GPT-5.2 per-submission specialist totals (only if provided at build time) |
| `specialists_gpt52_summary.csv` | GPT-5.2 specialist aggregates per assignment (veto rate, mean spread, specialist means) used for Table 5 when per-submission totals are not released |
| `per_criterion_deepseek.csv` | per-criterion scores `tc1..tc5` of the DeepSeek runs (no free text) |
| `data_quality_log.csv` | every reconciliation done while building the master table |

Scores: GPT-5.2 totals are multiples of 0.5. DeepSeek raw totals (multiples of 0.25) are rounded **half-up to the nearest 0.5**
(`single_deepseek`, `multi_deepseek`); the unrounded value is kept in `*_raw`.

## Metrics
QWK on integer-rounded scores (GT rounded to nearest integer, `np.rint`), computed with the label set that occurs in the data
(equivalent to scikit-learn's default, used in the paper). MAE, bias, Pearson and Spearman use exact values. 95% CIs: 1000
submission-level bootstrap resamples (percentile, seed 42); CIs may differ from the paper in the second decimal.
`results/qwk_label_sensitivity.csv` also gives QWK on the full 0-10 label set.

## Data policy
No raw submissions, names or student numbers are released. IDs are random; the mapping is not public. Free-text feedback
columns were excluded. See `DATA_POLICY.md`.

## Status of the paper numbers
The following items differ from the paper or could not be computed (see `results/verification_report.csv`):

* `single_gpt52_mae` A3: paper 0.607, recomputed 0.612 (DIFF)
* `multi_gpt52_mae` A3: paper 1.062, recomputed 1.071 (DIFF)
* `single_deepseek_qwk` A3: paper 0.378, recomputed 0.368 (DIFF)
* `multi_deepseek_qwk` A3: paper 0.451, recomputed 0.449 (DIFF)
* `bias_single` A3: paper 0.103, recomputed 0.104 (DIFF)
* `bias_multi` A3: paper -0.804, recomputed -0.811 (DIFF)
* `pearson_multi` A3: paper 0.69, recomputed 0.689 (DIFF)
* `spearman_single` A3: paper 0.828, recomputed 0.825 (DIFF)
* `spearman_multi` A3: paper 0.711, recomputed 0.708 (DIFF)
* `t5_mean_diff` A3: paper -0.907, recomputed -0.915 (DIFF)
* `t5_veto` A1: paper 0.993, recomputed None (NOT COMPUTED)
* `t5_veto` A2: paper 0.922, recomputed None (NOT COMPUTED)
* `t5_veto` A3: paper 0.772, recomputed None (NOT COMPUTED)
* `t5_veto` A4: paper 0.061, recomputed None (NOT COMPUTED)
* `t5_spread` A1: paper 5.15, recomputed None (NOT COMPUTED)
* `t5_spread` A2: paper 3.387, recomputed None (NOT COMPUTED)
* `t5_spread` A3: paper 2.653, recomputed None (NOT COMPUTED)
* `t5_spread` A4: paper 1.133, recomputed None (NOT COMPUTED)
* `t5_content` A1: paper 2.284, recomputed None (NOT COMPUTED)
* `t5_content` A2: paper 3.82, recomputed None (NOT COMPUTED)
* `t5_content` A3: paper 3.913, recomputed None (NOT COMPUTED)
* `t5_content` A4: paper 6.631, recomputed None (NOT COMPUTED)
* `t5_structure` A1: paper 6.46, recomputed None (NOT COMPUTED)
* `t5_structure` A2: paper 6.398, recomputed None (NOT COMPUTED)
* `t5_structure` A3: paper 6.14, recomputed None (NOT COMPUTED)
* `t5_structure` A4: paper 7.258, recomputed None (NOT COMPUTED)
* `t5_language` A1: paper 7.418, recomputed None (NOT COMPUTED)
* `t5_language` A2: paper 7.161, recomputed None (NOT COMPUTED)
* `t5_language` A3: paper 6.365, recomputed None (NOT COMPUTED)
* `t5_language` A4: paper 7.555, recomputed None (NOT COMPUTED)
* `t6_mean_qwk` A1: paper 0.018, recomputed None (NOT COMPUTED)
* `t6_mean_qwk` A2: paper 0.34, recomputed None (NOT COMPUTED)
* `t6_mean_qwk` A3: paper 0.452, recomputed None (NOT COMPUTED)
* `t6_mean_qwk` A4: paper 0.284, recomputed None (NOT COMPUTED)
* `t6_mean_mae` A1: paper 1.441, recomputed None (NOT COMPUTED)
* `t6_mean_mae` A2: paper 0.647, recomputed None (NOT COMPUTED)
* `t6_mean_mae` A3: paper 1.156, recomputed None (NOT COMPUTED)
* `t6_mean_mae` A4: paper 0.796, recomputed None (NOT COMPUTED)
* `t6_median_qwk` A1: paper -0.003, recomputed None (NOT COMPUTED)
* `t6_median_qwk` A2: paper 0.257, recomputed None (NOT COMPUTED)
* `t6_median_qwk` A3: paper 0.573, recomputed None (NOT COMPUTED)
* `t6_median_qwk` A4: paper 0.265, recomputed None (NOT COMPUTED)
* `t6_median_mae` A1: paper 0.717, recomputed None (NOT COMPUTED)
* `t6_median_mae` A2: paper 0.766, recomputed None (NOT COMPUTED)
* `t6_median_mae` A3: paper 0.868, recomputed None (NOT COMPUTED)
* `t6_median_mae` A4: paper 0.734, recomputed None (NOT COMPUTED)
* `t6_weighted_qwk` A1: paper 0.002, recomputed None (NOT COMPUTED)
* `t6_weighted_qwk` A2: paper 0.262, recomputed None (NOT COMPUTED)
* `t6_weighted_qwk` A3: paper 0.376, recomputed None (NOT COMPUTED)
* `t6_weighted_qwk` A4: paper 0.222, recomputed None (NOT COMPUTED)
* `t6_weighted_mae` A1: paper 2.206, recomputed None (NOT COMPUTED)
* `t6_weighted_mae` A2: paper 0.953, recomputed None (NOT COMPUTED)
* `t6_weighted_mae` A3: paper 1.456, recomputed None (NOT COMPUTED)
* `t6_weighted_mae` A4: paper 0.898, recomputed None (NOT COMPUTED)
* `t7_ds_veto` A4: paper 0.074, recomputed None (NOT COMPUTED)
* `t7_ds_spread` A4: paper 1.109, recomputed None (NOT COMPUTED)

## Not included
* `data/specialists_gpt52.csv`: GPT-5.2 per-submission specialist totals (Table 6 needs them).
* DeepSeek specialist logs for A4 (and A1/A2, paper limitation L4).
* Pipeline source code (`agents/`) and rubrics: see their own folders.

## Cite
Add the final BibTeX / DOI here after publication. (License: add one for code and one for data.)
