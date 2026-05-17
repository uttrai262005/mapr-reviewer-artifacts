from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'output' / 'reviewer_data'
OUT_XLSX = ROOT / 'output' / 'mapr_analysis_tables.xlsx'
OUT_JSON = ROOT / 'output' / 'mapr_analysis_summary.json'

ASSIGNMENTS = ['A1', 'A2', 'A3', 'A4']

def qwk_int(a, b):
    ai = np.round(np.asarray(a, dtype=float) * 2).astype('float')
    bi = np.round(np.asarray(b, dtype=float) * 2).astype('float')
    m = np.isfinite(ai) & np.isfinite(bi)
    if m.sum() == 0:
        return np.nan
    return float(cohen_kappa_score(ai[m].astype(int), bi[m].astype(int), weights='quadratic'))

def mae(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() == 0:
        return np.nan
    return float(np.mean(np.abs(a[m] - b[m])))

def pearson(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 2:
        return np.nan
    return float(pearsonr(a[m], b[m]).statistic)

def bootstrap_ci(metric_fn, x, y, B=3000, seed=42):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]
    n = len(x)
    if n == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(B):
        idx = rng.integers(0, n, size=n)
        vals.append(metric_fn(x[idx], y[idx]))
    return (float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5)))

def read_human_subset():
    path = SRC / 'human_subset_scores.xlsx'
    return {a: pd.read_excel(path, sheet_name=a) for a in ASSIGNMENTS}

def load_total_table(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    sid = 'student_id' if 'student_id' in df.columns else 'student'
    return pd.DataFrame({'student_id': df[sid].astype(str).str.strip(), 'total': pd.to_numeric(df['total'], errors='coerce')}).drop_duplicates(subset=['student_id'])

def load_sources():
    return {
        'gpt52_single_full': {a: load_total_table(SRC / 'gpt52_single_full' / f'{a}.xlsx') for a in ASSIGNMENTS},
        'gpt52_multi_full': {a: load_total_table(SRC / 'gpt52_multi_full' / f'{a}.xlsx') for a in ASSIGNMENTS},
        'gpt4o_full': {a: load_total_table(SRC / 'gpt4o_full' / f'{a}.xlsx') for a in ASSIGNMENTS},
        'gpt54mini_full': {a: load_total_table(SRC / 'gpt54mini_full' / f'{a}.xlsx') for a in ASSIGNMENTS},
        'gpt54_subset': {a: load_total_table(SRC / 'gpt54_subset' / f'{a}.xlsx') for a in ASSIGNMENTS},
    }

def build_subset_tables(human_subset, sources):
    merged = {}
    for a in ASSIGNMENTS:
        base = human_subset[a].copy()
        base['GT'] = (base['human1'] + base['human2']) / 2
        base = base.merge(sources['gpt54_subset'][a].rename(columns={'total': 'gpt54'}), on='student_id', how='left')
        base = base.merge(sources['gpt4o_full'][a].rename(columns={'total': 'gpt4o'}), on='student_id', how='left')
        base = base.merge(sources['gpt54mini_full'][a].rename(columns={'total': 'gpt54mini'}), on='student_id', how='left')
        base = base.merge(sources['gpt52_single_full'][a].rename(columns={'total': 'gpt52_single_full'}), on='student_id', how='left')
        base = base.merge(sources['gpt52_multi_full'][a].rename(columns={'total': 'gpt52_multi_full'}), on='student_id', how='left')
        merged[a] = base
    return merged

def compute_summary(subset_tables):
    rows = []
    ci_rows = []
    bias_rows = []
    multi_rows = []
    for i, a in enumerate(ASSIGNMENTS, start=1):
        df = subset_tables[a]
        gt = df['GT']
        human_qwk = qwk_int(df['human1'], df['human2'])
        human_ci = bootstrap_ci(qwk_int, df['human1'], df['human2'], seed=100 + i)
        bias = {'Assignment': a, 'Mean_GT': float(np.nanmean(gt))}
        row = {'Assignment': a, 'Human_QWK': human_qwk}
        ci_row = {'Assignment': a, 'Human_QWK': human_qwk, 'Human_QWK_CI95_low': human_ci[0], 'Human_QWK_CI95_high': human_ci[1]}
        model_series = {'gpt52_single': df['gpt52_single'], 'gpt54': df['gpt54'], 'gpt4o': df['gpt4o'], 'gpt54mini': df['gpt54mini']}
        for j, (model, vals) in enumerate(model_series.items(), start=1):
            row[f'{model}_QWK'] = qwk_int(vals, gt)
            row[f'{model}_MAE'] = mae(vals, gt)
            row[f'{model}_Pearson_r'] = pearson(vals, gt)
            qwk_ci = bootstrap_ci(qwk_int, vals, gt, seed=1000 + i * 10 + j)
            mae_ci = bootstrap_ci(mae, vals, gt, seed=2000 + i * 10 + j)
            ci_row[f'{model}_QWK'] = row[f'{model}_QWK']
            ci_row[f'{model}_QWK_CI95_low'] = qwk_ci[0]
            ci_row[f'{model}_QWK_CI95_high'] = qwk_ci[1]
            ci_row[f'{model}_MAE'] = row[f'{model}_MAE']
            ci_row[f'{model}_MAE_CI95_low'] = mae_ci[0]
            ci_row[f'{model}_MAE_CI95_high'] = mae_ci[1]
            ci_row[f'{model}_Pearson_r'] = row[f'{model}_Pearson_r']
            bias[f'{model}_Bias'] = float(np.nanmean(vals - gt))
        rows.append(row)
        ci_rows.append(ci_row)
        bias_rows.append(bias)
        multi_rows.append({'Assignment': a, 'Single_Agent_QWK': row['gpt52_single_QWK'], 'Multi_Agent_QWK': qwk_int(df['gpt52_multi'], gt), 'Multi_Agent_MAE': mae(df['gpt52_multi'], gt), 'Multi_Agent_Pearson_r': pearson(df['gpt52_multi'], gt)})
    return pd.DataFrame(rows), pd.DataFrame(ci_rows), pd.DataFrame(bias_rows), pd.DataFrame(multi_rows)

def compute_full_deltas(sources):
    rows = []
    for a in ASSIGNMENTS:
        p1 = sources['gpt52_single_full'][a].rename(columns={'total': 'p1'})
        p2 = sources['gpt52_multi_full'][a].rename(columns={'total': 'p2'})
        m = p1.merge(p2, on='student_id', how='inner')
        delta = pd.to_numeric(m['p2'], errors='coerce') - pd.to_numeric(m['p1'], errors='coerce')
        rows.append({'Assignment': a, 'N_full': int(len(m)), 'mean_P2_minus_P1': float(np.nanmean(delta)), 'median_P2_minus_P1': float(np.nanmedian(delta))})
    return pd.DataFrame(rows)

def main():
    human_subset = read_human_subset()
    sources = load_sources()
    subset_tables = build_subset_tables(human_subset, sources)
    summary, ci, bias, multi = compute_summary(subset_tables)
    full_delta = compute_full_deltas(sources)

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine='openpyxl') as writer:
        summary.to_excel(writer, sheet_name='summary', index=False)
        ci.to_excel(writer, sheet_name='ci_metrics', index=False)
        bias.to_excel(writer, sheet_name='bias_table', index=False)
        multi.to_excel(writer, sheet_name='multiagent_subset', index=False)
        full_delta.to_excel(writer, sheet_name='full_dataset_delta', index=False)
        for a, df in subset_tables.items():
            df.to_excel(writer, sheet_name=f'subset_{a}', index=False)

    payload = {'summary_rows': summary.to_dict(orient='records'), 'bias_rows': bias.to_dict(orient='records'), 'multiagent_rows': multi.to_dict(orient='records'), 'full_delta_rows': full_delta.to_dict(orient='records')}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved: {OUT_XLSX}')
    print(f'Saved: {OUT_JSON}')

if __name__ == '__main__':
    main()
