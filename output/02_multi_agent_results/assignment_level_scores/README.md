# Multi-agent detailed score tables

This folder contains anonymized assignment-level detailed score tables from the multi-agent pipeline, parallel to `output/01_single_agent_results/assignment_level_scores/`.

## Files
- `multi_agent_scores_a1.xlsx`
- `multi_agent_scores_a2.xlsx`
- `multi_agent_scores_a3.xlsx`
- `multi_agent_scores_a4.xlsx`

## Key columns
- `student_id`: anonymized student code in the form `Sxxxx`
- `multi_agent_total(/10)`: final phase-2 / multi-agent score
- `single_agent_total(/10)`: corresponding phase-1 / single-agent score included in the original phase-2 workbook
- `delta(multi-single)`: score difference between the two pipelines
- `veto_flag`: chairman veto indicator
- `spread`: disagreement spread across specialist agents before final aggregation
- `content_specialist_total`, `structure_specialist_total`, `language_specialist_total`: specialist branch totals before final aggregation
- `chairman_comment`: final aggregate comment from the chairman stage
