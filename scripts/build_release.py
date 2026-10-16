#!/usr/bin/env python3
"""
build_release.py - one script to (re)build the FISAT 2026 artifact repository.

Paper: "Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce Essays:
        A Cross-Model Study with Aggregation-Strategy Ablation"

TWO MODES
---------
1) OWNER MODE (needs the raw files that contain real student IDs; never commit them)
       python scripts/build_release.py --raw /path/to/raw_dir --repo . --archive-legacy
   - reads the per-assignment score files (BT1..BT4) + hand-graded file
   - cleans / reconciles them (every fix is logged)
   - anonymizes student IDs (random S0001..S0520; mapping saved OUTSIDE the public data)
   - writes data/*.csv, results/*.csv, figures, verification report, README/DATA_POLICY
   - archives files of the previous submission into archive/previous_submission/ (optional)

2) REVIEWER MODE (public; needs only data/scores_master.csv from this repo)
       python scripts/build_release.py --repo .
   - rebuilds Tables 2-7, figures and the paper-number verification report.

Raw files expected in --raw (names as exported by the pipeline):
   mau_cham_tay.xlsx                  sheets BT1..BT4: MSSV | GPT single total | GPT multi total | human1 | human2
   tong_hop_4_bt.xlsx                 sheets BT1..BT4 (only used as FALLBACK when a per-assignment file lacks a row)
   BT{1-4}_single_deepseek.xlsx       columns: mssv, tc1..tc5, total
   multiagent_deepseek_bt{1-4}.xlsx   columns: mssv, tc*, total, spread, veto_flag, total_content/structure/language
   multiagent_*gpt*bt{1-4}*.xlsx      OPTIONAL (GPT-5.2 multi-agent with specialist totals, keyed by mssv).
                                      Needed for Table 6 (ablation) with full linkage.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ASSIGN = {  # assignment -> (sheet / file index, expected N, #criteria)
    "A1": ("BT1", 1, 137),
    "A2": ("BT2", 2, 129),
    "A3": ("BT3", 3, 123),
    "A4": ("BT4", 4, 131),
}
SYSTEMS = ["single_gpt52", "multi_gpt52", "single_deepseek", "multi_deepseek"]
B_BOOT, SEED = 1000, 42            # paper: 1,000 submission-level bootstrap resamples
TOL_POINT, TOL_CI = 0.0006, 0.05   # point estimates must match to 3 decimals; CIs are seed-dependent

# --------------------------------------------------------------------------------------
# Paper values (FISAT 2026 camera-ready) used for the verification report
# --------------------------------------------------------------------------------------
P = {
    "human_qwk": [0.327, 0.611, 0.709, 0.630],
    "human_absdiff": [0.70, 0.49, 0.74, 0.47],
    "gt_sd": [0.69, 0.84, 1.28, 0.72],
    "single_gpt52_qwk": [0.272, 0.154, 0.792, 0.565],
    "single_gpt52_mae": [0.653, 2.141, 0.607, 0.479],
    "multi_gpt52_qwk": [-0.003, 0.375, 0.462, 0.325],
    "multi_gpt52_mae": [1.347, 0.607, 1.062, 0.746],
    "single_deepseek_qwk": [0.187, 0.118, 0.378, -0.008],
    "multi_deepseek_qwk": [-0.147, 0.105, 0.451, 0.219],
    "bias_single": [-0.511, -2.134, 0.103, 0.292],
    "bias_multi": [-1.325, -0.304, -0.804, -0.544],
    "pearson_single": [0.463, 0.657, 0.866, 0.742],
    "pearson_multi": [0.104, 0.554, 0.690, 0.397],
    "spearman_single": [0.401, 0.561, 0.828, 0.727],
    "spearman_multi": [0.113, 0.297, 0.711, 0.405],
    "t5_mean_diff": [-0.814, 1.830, -0.907, -0.836],
    "t5_veto": [0.993, 0.922, 0.772, 0.061],
    "t5_spread": [5.150, 3.387, 2.653, 1.133],
    "t5_content": [2.284, 3.820, 3.913, 6.631],
    "t5_structure": [6.460, 6.398, 6.140, 7.258],
    "t5_language": [7.418, 7.161, 6.365, 7.555],
    "t6_mean_qwk": [0.018, 0.340, 0.452, 0.284],
    "t6_mean_mae": [1.441, 0.647, 1.156, 0.796],
    "t6_median_qwk": [-0.003, 0.257, 0.573, 0.265],
    "t6_median_mae": [0.717, 0.766, 0.868, 0.734],
    "t6_weighted_qwk": [0.002, 0.262, 0.376, 0.222],
    "t6_weighted_mae": [2.206, 0.953, 1.456, 0.898],
    "t7_ds_veto": [None, None, 0.772, 0.074],
    "t7_ds_spread": [None, None, 2.664, 1.109],
}
P_CI = {  # 95% CIs from Tables 2-3 (bootstrap, seed unknown -> loose tolerance)
    "human_qwk": [(0.169, 0.468), (0.402, 0.744), (0.603, 0.799), (0.463, 0.747)],
    "single_gpt52_qwk": [(0.128, 0.410), (0.077, 0.245), (0.710, 0.852), (0.373, 0.700)],
    "single_gpt52_mae": [(0.555, 0.745), (2.006, 2.267), (0.508, 0.710), (0.410, 0.557)],
    "multi_gpt52_qwk": [(-0.078, 0.069), (0.103, 0.584), (0.337, 0.560), (0.150, 0.478)],
    "multi_gpt52_mae": [(1.224, 1.471), (0.512, 0.711), (0.956, 1.173), (0.664, 0.830)],
}


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------
def qwk(a, b, mode="observed"):
    """Quadratic weighted kappa on integer-rounded scores (np.rint = round-half-even).

    mode='observed': label set = values that actually occur (== sklearn cohen_kappa_score default,
                     which is what reproduces the paper). Gaps in the observed labels shrink distances.
    mode='fixed'   : full 0..10 scale (distance between 4 and 6 is always 2).
    """
    a = np.rint(np.asarray(a, float)).astype(int)
    b = np.rint(np.asarray(b, float)).astype(int)
    labels = np.arange(0, 11) if mode == "fixed" else np.union1d(a, b)
    k = len(labels)
    if k < 2:
        return np.nan
    ia, ib = np.searchsorted(labels, a), np.searchsorted(labels, b)
    o = np.zeros((k, k))
    np.add.at(o, (ia, ib), 1)
    w = np.subtract.outer(np.arange(k), np.arange(k)) ** 2
    e = np.outer(o.sum(1), o.sum(0)) / o.sum()
    den = (w * e).sum()
    return np.nan if den == 0 else 1 - (w * o).sum() / den


def boot_ci(fn, n, rng):
    idx = rng.integers(0, n, size=(B_BOOT, n))
    vals = np.array([fn(i) for i in idx], float)
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def half_up_05(x):
    """Round to nearest 0.5, ties up (this is how tong_hop_4_bt.xlsx rounded DeepSeek totals)."""
    return np.floor(np.asarray(x, float) * 2 + 0.5) / 2


# --------------------------------------------------------------------------------------
# Raw loading, cleaning, anonymization (OWNER MODE)
# --------------------------------------------------------------------------------------
def clean_id(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def find_one(raw: Path, pattern: str) -> Path | None:
    hits = sorted(p for p in raw.rglob("*") if p.is_file() and re.fullmatch(pattern, p.name, re.I))
    return hits[0] if hits else None


def load_raw(raw: Path, log: list, alias: bool = True):
    """Returns master (real IDs), specialists dict, per-criterion frame, dropped real IDs."""
    hand = raw / "mau_cham_tay.xlsx"
    if not hand.exists():
        sys.exit(f"[ERROR] {hand} not found")
    th_path = raw / "tong_hop_4_bt.xlsx"
    th_x = pd.ExcelFile(th_path) if th_path.exists() else None

    rows, spec_ds, spec_gpt, percrit, dropped = [], [], [], [], set()
    for a, (sheet, i, n_expected) in ASSIGN.items():
        # ---- roster + GPT totals + human scores (positional columns: header of BT2 is corrupted)
        m = pd.read_excel(hand, sheet_name=sheet).iloc[:, :5]
        m.columns = ["mssv", "single_gpt52", "multi_gpt52", "rater1", "rater2"]
        m["mssv"] = clean_id(m["mssv"])
        m = m.dropna(subset=["mssv"]).drop_duplicates("mssv")
        if m[["rater1", "rater2", "single_gpt52", "multi_gpt52"]].isna().any().any():
            sys.exit(f"[ERROR] {a}: missing values in hand-graded / GPT columns")
        if len(m) != n_expected:
            sys.exit(f"[ERROR] {a}: roster has {len(m)} rows, paper says {n_expected}")
        roster = set(m["mssv"])

        # ---- fallback table (tong_hop)
        th = None
        if th_x is not None:
            th = th_x.parse(sheet).iloc[:, :7]
            th.columns = ["mssv", "single_gpt52", "single_ds", "multi_gpt52", "multi_ds", "r1", "r2"]
            th["mssv"] = clean_id(th["mssv"])
            th = th.set_index("mssv")
            extra = set(th.index) - roster
            for x in extra:
                dropped.add(x)
            if extra:
                log.append(dict(assignment=a, system="tong_hop", student_id="", issue="row_not_in_roster",
                                action=f"dropped {len(extra)} row(s) (all-5.0 placeholder / not graded by humans)"))
            both = th.reindex(m["mssv"])
            for col in ("single_gpt52", "multi_gpt52"):
                bad = int((both[col].values != m[col].values).sum())
                if bad:
                    log.append(dict(assignment=a, system=col, student_id="", issue="gpt_total_mismatch_vs_tong_hop",
                                    action=f"{bad} rows differ; mau_cham_tay used"))

        # ---- DeepSeek per-assignment files
        out = m.set_index("mssv").copy()
        for sysname, fname, tcol in [("single_deepseek", f"BT{i}_single_deepseek.xlsx", "single_ds"),
                                     ("multi_deepseek", f"multiagent_deepseek_bt{i}.xlsx", "multi_ds")]:
            path = find_one(raw, re.escape(fname))
            raw_tot = pd.Series(np.nan, index=out.index)
            if path is None:
                log.append(dict(assignment=a, system=sysname, student_id="", issue="file_missing",
                                action=f"{fname} not found -> all values from tong_hop fallback"))
            else:
                d = pd.read_excel(path)
                d.columns = [str(c).strip().lower() for c in d.columns]
                d["mssv"] = clean_id(d["mssv"])
                d = d.drop_duplicates("mssv").set_index("mssv")
                extra, absent = set(d.index) - roster, roster - set(d.index)
                if alias and len(extra) == 1 and len(absent) == 1:   # one mislabeled id: same file, one unknown id, one missing id
                    wrong, right = next(iter(extra)), next(iter(absent))
                    dropped.add(wrong)
                    d = d.rename(index={wrong: right})
                    extra = set()
                    log.append(dict(assignment=a, system=sysname, student_id=right, issue="id_alias",
                                    action="file id not in roster; it is the only unknown id and the only roster id is missing -> relabelled (VERIFY)"))
                    print(f"[WARN] {a}/{sysname}: id '{wrong}' in {path.name} is not in the roster; '{right}' is missing -> treated as the same student. VERIFY.")
                for x in extra:
                    dropped.add(x)
                if extra:
                    log.append(dict(assignment=a, system=sysname, student_id="", issue="row_not_in_roster",
                                    action=f"dropped {len(extra)} row(s) present in score file"))
                raw_tot = d["total"].reindex(out.index)
                tcs = [c for c in d.columns if re.fullmatch(r"tc\d", c)]
                pc = d.reindex(out.index)[tcs].copy()
                pc.columns = [f"tc{j + 1}" for j in range(len(tcs))]
                pc["total_raw"] = raw_tot
                pc["assignment"], pc["system"], pc["mssv"] = a, sysname, out.index
                percrit.append(pc.dropna(subset=["total_raw"]).reset_index(drop=True))
                if sysname == "multi_deepseek" and {"total_content", "total_structure", "total_language"} <= set(d.columns):
                    s = d.reindex(out.index)[["total_content", "total_structure", "total_language", "spread", "veto_flag"]]
                    s.columns = ["content", "structure", "language", "spread", "veto"]
                    s = s.assign(assignment=a, mssv=out.index).dropna(subset=["spread"])
                    spec_ds.append(s.reset_index(drop=True))
            rounded = pd.Series(half_up_05(raw_tot.values), index=out.index)
            fb = th[tcol].reindex(out.index) if th is not None else pd.Series(np.nan, index=out.index)
            val = rounded.where(rounded.notna(), fb)
            src = np.where(rounded.notna(), "file", np.where(fb.notna(), "tong_hop_fallback", "missing"))
            if (src == "missing").any():
                sys.exit(f"[ERROR] {a}/{sysname}: {(src == 'missing').sum()} students have no score anywhere")
            # cross-check file vs tong_hop where both exist
            if th is not None and rounded.notna().any():
                bad = int(((rounded != fb) & rounded.notna() & fb.notna()).sum())
                if bad:
                    log.append(dict(assignment=a, system=sysname, student_id="", issue="file_vs_tong_hop_mismatch",
                                    action=f"{bad} rows differ after 0.5 rounding; file value used"))
            out[sysname] = val
            out[f"{sysname}_raw"] = raw_tot
            out[f"{sysname}_source"] = src
            if path is not None:
                for sid in out.index[src == "tong_hop_fallback"]:
                    log.append(dict(assignment=a, system=sysname, student_id=sid, issue="score_missing_in_file",
                                    action="taken from tong_hop_4_bt.xlsx (verify origin)"))

        # ---- optional GPT-5.2 multi-agent file with specialists
        gp = find_one(raw, rf"multiagent.*gpt.*bt{i}.*\.xlsx")
        if gp is not None:
            d = pd.read_excel(gp)
            d.columns = [str(c).strip().lower() for c in d.columns]
            if {"mssv", "total_content", "total_structure", "total_language"} <= set(d.columns):
                d["mssv"] = clean_id(d["mssv"])
                d = d[d["mssv"].isin(roster)].drop_duplicates("mssv")
                s = d[["mssv", "total_content", "total_structure", "total_language"]
                      + [c for c in ("spread", "veto_flag") if c in d.columns]].copy()
                s = s.rename(columns={"total_content": "content", "total_structure": "structure",
                                      "total_language": "language", "veto_flag": "veto"})
                s["assignment"] = a
                spec_gpt.append(s.reset_index(drop=True))

        out["assignment"] = a
        rows.append(out.reset_index())

    master = pd.concat(rows, ignore_index=True)
    master["gt"] = (master["rater1"] + master["rater2"]) / 2
    sp = lambda L: pd.concat(L, ignore_index=True) if L else pd.DataFrame()
    return master, sp(spec_gpt), sp(spec_ds), sp(percrit), dropped


def anonymize(frames: dict, private_dir: Path):
    """Random IDs S0001..; stable across reruns through private/id_map.csv (never committed)."""
    private_dir.mkdir(parents=True, exist_ok=True)
    map_path = private_dir / "id_map.csv"
    mp = dict(pd.read_csv(map_path, dtype=str)[["mssv", "student_id"]].values) if map_path.exists() else {}
    ids = sorted({x for f in frames.values() if len(f) for x in f["mssv"]})
    new = [x for x in ids if x not in mp]
    used = {int(v[1:]) for v in mp.values()}
    pool = [k for k in range(1, len(ids) + len(mp) + 1) if k not in used]
    secrets.SystemRandom().shuffle(pool)
    for x, k in zip(new, pool):
        mp[x] = f"S{k:04d}"
    pd.DataFrame({"mssv": list(mp), "student_id": list(mp.values())}).to_csv(map_path, index=False)
    out = {}
    for k, f in frames.items():
        if len(f):
            f = f.copy()
            f.insert(0, "student_id", f["mssv"].map(mp))
            f = f.drop(columns="mssv")
        out[k] = f
    return out, set(mp)


# --------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------
def r3(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)


def compute_tables(master, spec_gpt, spec_ds, legacy_gpt, mode):
    rng = np.random.default_rng(SEED)
    T, V = {}, {k: [None] * 4 for k in P}
    CI = {k: [None] * 4 for k in P_CI}
    t1, t2, t3, t4, t5, t6, t7 = [], [], [], [], [], [], []
    sens = []
    for ai, a in enumerate(ASSIGN):
        d = master[master.assignment == a].reset_index(drop=True)
        n, gt = len(d), d["gt"].to_numpy()
        gt_r = np.rint(gt)
        h1, h2 = d["rater1"].to_numpy(), d["rater2"].to_numpy()
        hq = qwk(h1, h2, mode)
        hci = boot_ci(lambda i: qwk(h1[i], h2[i], mode), n, rng)
        V["human_qwk"][ai], CI["human_qwk"][ai] = hq, hci
        V["human_absdiff"][ai], V["gt_sd"][ai] = np.abs(h1 - h2).mean(), gt.std(ddof=1)
        t1.append(dict(assignment=a, N=n, human_abs_diff=r3(V["human_absdiff"][ai]), gt_sd=r3(V["gt_sd"][ai]),
                       human_qwk=r3(hq), human_qwk_ci=f"[{hci[0]:.3f}, {hci[1]:.3f}]"))
        res = {}
        for s in SYSTEMS:
            p = d[s].to_numpy(float)
            q = qwk(gt_r, p, mode)
            mae = np.abs(p - gt).mean()
            qci = boot_ci(lambda i: qwk(gt_r[i], p[i], mode), n, rng)
            mci = boot_ci(lambda i: np.abs(p[i] - gt[i]).mean(), n, rng)
            res[s] = dict(qwk=q, mae=mae, qci=qci, mci=mci, bias=(p - gt).mean(),
                          r=pearsonr(p, gt)[0], rho=spearmanr(p, gt)[0], p=p)
            sens.append(dict(assignment=a, system=s, qwk_observed_labels=r3(qwk(gt_r, p, "observed")),
                             qwk_fixed_0_10=r3(qwk(gt_r, p, "fixed"))))
        sg, mg, sd, md = (res[s] for s in SYSTEMS)
        for key, rr in [("single_gpt52", sg), ("multi_gpt52", mg), ("single_deepseek", sd), ("multi_deepseek", md)]:
            V[f"{key}_qwk"][ai] = rr["qwk"]
            if f"{key}_mae" in V:
                V[f"{key}_mae"][ai] = rr["mae"]
            if f"{key}_qwk" in CI:
                CI[f"{key}_qwk"][ai] = rr["qci"]
            if f"{key}_mae" in CI:
                CI[f"{key}_mae"][ai] = rr["mci"]
        for k, rr in [("single", sg), ("multi", mg)]:
            V[f"bias_{k}"][ai], V[f"pearson_{k}"][ai], V[f"spearman_{k}"][ai] = rr["bias"], rr["r"], rr["rho"]
        fmt = lambda c: f"[{c[0]:.3f}, {c[1]:.3f}]"
        t2.append(dict(assignment=a, human_qwk=r3(hq), human_qwk_ci=fmt(hci), single_qwk=r3(sg["qwk"]),
                       single_qwk_ci=fmt(sg["qci"]), single_mae=r3(sg["mae"]), single_mae_ci=fmt(sg["mci"])))
        t3.append(dict(assignment=a, multi_qwk=r3(mg["qwk"]), multi_qwk_ci=fmt(mg["qci"]), multi_mae=r3(mg["mae"]),
                       multi_mae_ci=fmt(mg["mci"]), delta_qwk_multi_minus_single=r3(mg["qwk"] - sg["qwk"])))
        for k, rr in [("single_agent", sg), ("multi_agent", mg)]:
            t4.append(dict(assignment=a, condition=k, mean_bias=r3(rr["bias"]), pearson_r=r3(rr["r"]), spearman_rho=r3(rr["rho"])))
        mean_diff = (mg["p"] - sg["p"]).mean()
        V["t5_mean_diff"][ai] = mean_diff

        # ---- specialists (GPT-5.2): linked file preferred, else unlinked legacy aggregates
        row5 = dict(assignment=a, N=n, mean_multi_minus_single=r3(mean_diff))
        sp = spec_gpt[spec_gpt.assignment == a] if len(spec_gpt) else pd.DataFrame()
        if len(sp):
            spread = sp[["content", "structure", "language"]].max(1) - sp[["content", "structure", "language"]].min(1)
            sp = sp.assign(spread_calc=spread)
            veto = sp["veto"].astype(str).str.upper().isin(["TRUE", "Y", "1"]) if "veto" in sp else spread > 1.0
            sprd = sp["spread"] if "spread" in sp else spread
            row5.update(veto_rate=r3(veto.mean()), mean_spread=r3(sprd.mean()), content_mean=r3(sp.content.mean()),
                        structure_mean=r3(sp.structure.mean()), language_mean=r3(sp.language.mean()))
            for k, c in [("t5_veto", veto.mean()), ("t5_spread", sprd.mean()), ("t5_content", sp.content.mean()),
                         ("t5_structure", sp.structure.mean()), ("t5_language", sp.language.mean())]:
                V[k][ai] = c
            # ---- Table 6 ablation: needs linkage specialist <-> GT
            m_ = d[["student_id", "gt"]].merge(sp[["student_id", "content", "structure", "language"]], on="student_id")
            if len(m_) == n:
                g = np.rint(m_["gt"].to_numpy()); gexact = m_["gt"].to_numpy()
                ok = m_[["content", "structure", "language"]].notna().all(axis=1).to_numpy()   # a failed specialist call has no totals
                m_ = m_[ok]
                g = np.rint(m_["gt"].to_numpy()); gexact = m_["gt"].to_numpy()
                c, s_, l = (m_[x].to_numpy() for x in ("content", "structure", "language"))
                for name, v, key in [("Mean (recomputed)", (c + s_ + l) / 3, "mean"),
                                     ("Median", np.median(np.c_[c, s_, l], 1), "median"),
                                     ("Rubric-weighted", .5 * c + .25 * s_ + .25 * l, "weighted")]:
                    q6, m6 = qwk(g, v, mode), np.abs(v - gexact).mean()
                    V[f"t6_{key}_qwk"][ai], V[f"t6_{key}_mae"][ai] = q6, m6
                    t6.append(dict(assignment=a, variant=name, qwk=r3(q6), delta_qwk_vs_single=r3(q6 - sg["qwk"]),
                                   mae=r3(m6), delta_mae_vs_single=r3(m6 - sg["mae"])))
        elif legacy_gpt is not None and a in legacy_gpt:
            lg = legacy_gpt[a]
            row5.update(veto_rate=r3(lg["veto"]), mean_spread=r3(lg["spread"]), content_mean=r3(lg["content"]),
                        structure_mean=r3(lg["structure"]), language_mean=r3(lg["language"]),
                        note="aggregates only (per-submission specialist totals not linkable to current IDs)")
            for k, c in [("t5_veto", lg["veto"]), ("t5_spread", lg["spread"]), ("t5_content", lg["content"]),
                         ("t5_structure", lg["structure"]), ("t5_language", lg["language"])]:
                V[k][ai] = c
        t5.append(row5)

        row7 = dict(assignment=a, single_gpt52=r3(sg["qwk"]), single_deepseek=r3(sd["qwk"]),
                    multi_gpt52=r3(mg["qwk"]), multi_deepseek=r3(md["qwk"]),
                    gpt52_veto=row5.get("veto_rate"), gpt52_spread=row5.get("mean_spread"))
        sdp = spec_ds[spec_ds.assignment == a] if len(spec_ds) else pd.DataFrame()
        if len(sdp):
            vv = sdp["veto"].astype(str).str.upper().isin(["TRUE", "Y", "1"]).mean()
            row7.update(deepseek_veto=r3(vv), deepseek_spread=r3(sdp.spread.mean()))
            V["t7_ds_veto"][ai], V["t7_ds_spread"][ai] = vv, sdp.spread.mean()
        t7.append(row7)

    T["table1_dataset_human"] = pd.DataFrame(t1)
    T["table2_single_agent_gpt52"] = pd.DataFrame(t2)
    T["table3_multi_agent_gpt52"] = pd.DataFrame(t3)
    T["table4_bias_and_rank_correlation"] = pd.DataFrame(t4)
    T["table5_specialist_disagreement"] = pd.DataFrame(t5)
    if t6:
        T["table6_aggregation_ablation"] = pd.DataFrame(t6)
    T["table7_cross_model"] = pd.DataFrame(t7)
    T["qwk_label_sensitivity"] = pd.DataFrame(sens)
    return T, V, CI


def verify(V, CI, mode):
    rows = []
    names = [a for a in ASSIGN]
    for key, expect in P.items():
        for ai, e in enumerate(expect):
            if e is None:
                continue
            c = V[key][ai]
            if c is None or (isinstance(c, float) and np.isnan(c)):
                rows.append(dict(item=key, assignment=names[ai], paper=e, computed=None, diff=None, status="NOT COMPUTED"))
                continue
            diff = float(c) - e
            rows.append(dict(item=key, assignment=names[ai], paper=e, computed=round(float(c), 3), diff=round(diff, 3),
                             status="PASS" if abs(diff) <= (0.0051 if key in ("human_absdiff", "gt_sd") else TOL_POINT) else "DIFF"))
    for key, cis in P_CI.items():
        for ai, (lo, hi) in enumerate(cis):
            c = CI[key][ai]
            ok = c is not None and abs(c[0] - lo) <= TOL_CI and abs(c[1] - hi) <= TOL_CI
            rows.append(dict(item=key + "_95CI", assignment=names[ai], paper=f"[{lo}, {hi}]",
                             computed=None if c is None else f"[{c[0]:.3f}, {c[1]:.3f}]", diff=None,
                             status="PASS(CI~)" if ok else "DIFF(CI)"))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------
def make_figures(master, T, out: Path, mode):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"[WARN] matplotlib unavailable -> figures skipped ({e})")
        return
    fig, ax = plt.subplots(2, 4, figsize=(14, 6.5))
    for j, a in enumerate(ASSIGN):
        d = master[master.assignment == a]
        for i, (s, col) in enumerate([("single_gpt52", "#2166ac"), ("multi_gpt52", "#b2182b")]):
            ax[i, j].scatter(d["gt"], d[s], s=10, alpha=.5, color=col)
            lim = [min(d["gt"].min(), d[s].min()) - .5, max(d["gt"].max(), d[s].max()) + .5]
            ax[i, j].plot(lim, lim, "k:", lw=.8)
            ax[i, j].set_title(f"{a} - {'single' if i == 0 else 'multi'}-agent (GPT-5.2)", fontsize=9)
            ax[i, j].set_xlabel("Ground truth"); ax[i, j].set_ylabel("Predicted")
    fig.tight_layout(); fig.savefig(out / "fig3_pred_vs_gt.png", dpi=160); plt.close(fig)
    t7, t1 = T["table7_cross_model"], T["table1_dataset_human"]
    x = np.arange(4); w = .2
    fig, ax = plt.subplots(figsize=(8, 4))
    for k, (c, lab, col) in enumerate([("single_gpt52", "Single-GPT-5.2", "#2166ac"), ("single_deepseek", "Single-DeepSeek", "#67a9cf"),
                                       ("multi_gpt52", "Multi-GPT-5.2", "#b2182b"), ("multi_deepseek", "Multi-DeepSeek", "#ef8a62")]):
        ax.bar(x + (k - 1.5) * w, t7[c], w, label=lab, color=col)
    for j, v in enumerate(t1.human_qwk):
        ax.hlines(v, j - .4, j + .4, colors="k", linestyles="--", lw=.8)
    ax.set_xticks(x, list(ASSIGN)); ax.set_ylabel("QWK"); ax.legend(fontsize=7); ax.axhline(0, color="k", lw=.5)
    ax.set_title(f"Cross-model QWK (dashed = human QWK; label mode: {mode})", fontsize=9)
    fig.tight_layout(); fig.savefig(out / "fig4_cross_model_qwk.png", dpi=160); plt.close(fig)


# --------------------------------------------------------------------------------------
# Legacy handling and docs
# --------------------------------------------------------------------------------------
def load_legacy_specialists(search_roots):
    """Aggregate (veto rate, mean spread, specialist means) from the OLD anonymized multi-agent files."""
    out = {}
    for a in ASSIGN:
        for root in search_roots:
            if root is None or not Path(root).exists():
                continue
            hits = sorted(Path(root).rglob(f"multi_agent_scores_{a.lower()}.xlsx"))
            if hits:
                d = pd.read_excel(hits[0])
                veto = d["veto_flag"].astype(str).str.upper().isin(["Y", "TRUE", "1"]).mean()
                out[a] = dict(veto=float(veto), spread=float(d["spread"].mean()),
                              content=float(d["content_specialist_total"].mean()),
                              structure=float(d["structure_specialist_total"].mean()),
                              language=float(d["language_specialist_total"].mean()), n=len(d))
                break
    return out or None


LEGACY_ITEMS = ["output", "scripts/rebuild_tables_legacy.py", "ARTIFACTS.md", "REPRODUCIBILITY.md", "DATA_POLICY.md", "README.md"]


def archive_legacy(repo: Path, dry):
    dst = repo / "archive" / "previous_submission"
    moved = []
    for item in LEGACY_ITEMS:
        src = repo / item
        if src.exists():
            moved.append(item)
            if not dry:
                (dst / item).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst / item))
    return moved


README = """# Artifacts: Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce Essays

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
| `specialists_deepseek.csv` | DeepSeek multi-agent specialist totals, spread, veto (A3 {ds_spec_note}) |
| `specialists_gpt52.csv` | GPT-5.2 per-submission specialist totals (only if provided at build time) |
| `specialists_gpt52_summary.csv` | GPT-5.2 specialist aggregates per assignment (veto rate, mean spread, specialist means) used for Table 5 when per-submission totals are not released |
| `per_criterion_deepseek.csv` | per-criterion scores `tc1..tc5` of the DeepSeek runs (no free text) |
| `data_quality_log.csv` | every reconciliation done while building the master table |

Scores: GPT-5.2 totals are multiples of 0.5. DeepSeek raw totals (multiples of 0.25) are rounded **half-up to the nearest 0.5**
(`single_deepseek`, `multi_deepseek`); the unrounded value is kept in `*_raw`.

## Metrics
QWK on integer-rounded scores (GT rounded to nearest integer, `np.rint`), computed with the label set that occurs in the data
(equivalent to scikit-learn's default, used in the paper). MAE, bias, Pearson and Spearman use exact values. 95% CIs: {B}
submission-level bootstrap resamples (percentile, seed {SEED}); CIs may differ from the paper in the second decimal.
`results/qwk_label_sensitivity.csv` also gives QWK on the full 0-10 label set.

## Data policy
No raw submissions, names or student numbers are released. IDs are random; the mapping is not public. Free-text feedback
columns were excluded. See `DATA_POLICY.md`.

## Status of the paper numbers
{status}

## Not included
{missing}

## Cite
See `CITATION.cff`. Please cite the paper (FISAT 2026) when using these data or code.

```bibtex
@inproceedings{{trinh2026grading,
  title     = {{Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce Essays: A Cross-Model Study with Aggregation-Strategy Ablation}},
  author    = {{Trinh, Tin T. and Nguyen, Truc D. and Nguyen, Nhi U.}},
  booktitle = {{Proceedings of FISAT 2026}},
  year      = {{2026}}
}}
```
(Update volume, pages and DOI when the proceedings are published.) License: see `LICENSE` if present.
"""

DATA_POLICY = """# Data policy
* Source: routine coursework of an undergraduate Introduction to E-commerce course (UIT, VNU-HCM).
* Released: anonymized scores only (random IDs `S0001`-`S0520`), human TA scores (rater1/rater2, TAs not identified),
  LLM scores and specialist totals, per-criterion numeric scores.
* Not released: submissions, rubrics' student-specific material, real student IDs, ID mapping, free-text comments.
* IDs are random and not derived from student numbers or file order; the mapping is kept offline by the authors.
* Do not attempt re-identification.
"""

CFF = 'cff-version: 1.2.0\nmessage: "If you use these data or code, please cite the paper below."\ntitle: "Artifacts: Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce Essays"\ntype: dataset\nauthors:\n  - family-names: Trinh\n    given-names: "Tin T."\n    affiliation: "University of Information Technology, VNU-HCM"\n  - family-names: Nguyen\n    given-names: "Truc D."\n    affiliation: "University of Information Technology, VNU-HCM"\n  - family-names: Nguyen\n    given-names: "Nhi U."\n    affiliation: "University of Information Technology, VNU-HCM"\npreferred-citation:\n  type: conference-paper\n  title: "Single-Agent vs. Multi-Agent LLM Grading for Vietnamese E-commerce Essays: A Cross-Model Study with Aggregation-Strategy Ablation"\n  authors:\n    - family-names: Trinh\n      given-names: "Tin T."\n    - family-names: Nguyen\n      given-names: "Truc D."\n    - family-names: Nguyen\n      given-names: "Nhi U."\n  collection-title: "FISAT 2026"\n  year: 2026\n'

REQS = "numpy\npandas\nscipy\nopenpyxl\nmatplotlib\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="repository root (default: .)")
    ap.add_argument("--raw", help="directory with RAW files holding real student IDs (owner mode)")
    ap.add_argument("--private-dir", help="where the ID map is stored (default: <repo>/private, git-ignored)")
    ap.add_argument("--legacy-repo", help="old anonymized repo/dir used only to aggregate Table 5 if no GPT specialist file is given")
    ap.add_argument("--qwk-labels", choices=["observed", "fixed"], default="observed")
    ap.add_argument("--archive-legacy", action="store_true", help="move files of the previous submission to archive/previous_submission/")
    ap.add_argument("--write-docs", action="store_true", help="(re)write README/DATA_POLICY/requirements (default on in owner mode)")
    ap.add_argument("--no-id-alias", action="store_true", help="do not auto-relabel a single mislabeled id in DeepSeek files")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any paper number differs")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    data_dir, res_dir = repo / "data", repo / "results"
    log: list = []
    legacy_agg = None
    owner = args.raw is not None

    if owner:
        raw = Path(args.raw).resolve()
        master_r, spec_gpt_r, spec_ds_r, percrit_r, dropped = load_raw(raw, log, not args.no_id_alias)
        legacy_agg = load_legacy_specialists([args.legacy_repo, repo / "output", repo / "archive" / "previous_submission" / "output"])
        sm_old = data_dir / "specialists_gpt52_summary.csv"
        if legacy_agg is None and sm_old.exists():
            legacy_agg = {r["assignment"]: r for r in pd.read_csv(sm_old).to_dict("records")}
        pdir = Path(args.private_dir) if args.private_dir else repo / "private"
        anon, all_real_ids = anonymize({"m": master_r, "sg": spec_gpt_r, "sd": spec_ds_r, "pc": percrit_r}, pdir)
        master, spec_gpt, spec_ds, percrit = anon["m"], anon["sg"], anon["sd"], anon["pc"]
        id_lookup = dict(zip(master_r["mssv"], master["student_id"]))
        for r in log:
            if r.get("student_id"):
                r["student_id"] = id_lookup.get(r["student_id"], "")
        real_ids = all_real_ids | dropped
        master = master.sort_values(["assignment", "student_id"]).reset_index(drop=True)
        if legacy_agg and not len(spec_gpt) and not args.dry_run:
            data_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([{**v, "assignment": k} for k, v in legacy_agg.items()]).to_csv(
                data_dir / "specialists_gpt52_summary.csv", index=False)
        for f in (spec_gpt, spec_ds, percrit):
            if len(f):
                f.sort_values(["assignment", "student_id"], inplace=True)
        if not args.dry_run:
            data_dir.mkdir(parents=True, exist_ok=True)
            master.to_csv(data_dir / "scores_master.csv", index=False)
            if len(spec_ds):
                spec_ds.to_csv(data_dir / "specialists_deepseek.csv", index=False)
            if len(spec_gpt):
                spec_gpt.to_csv(data_dir / "specialists_gpt52.csv", index=False)
            if len(percrit):
                percrit.drop(columns=[c for c in percrit.columns if c == "mssv"], errors="ignore").to_csv(
                    data_dir / "per_criterion_deepseek.csv", index=False)
            pd.DataFrame(log, columns=["assignment", "system", "student_id", "issue", "action"]).to_csv(
                data_dir / "data_quality_log.csv", index=False)
            gi = repo / ".gitignore"
            lines = gi.read_text().splitlines() if gi.exists() else []
            for pat in ("private/", "raw/", "*_raw_*.xlsx", "__pycache__/"):
                if pat not in lines:
                    lines.append(pat)
            gi.write_text("\n".join(lines) + "\n")
    else:
        if not (data_dir / "scores_master.csv").exists():
            sys.exit("[ERROR] data/scores_master.csv not found. Run in owner mode with --raw first.")
        master = pd.read_csv(data_dir / "scores_master.csv")
        rd = lambda n: pd.read_csv(data_dir / n) if (data_dir / n).exists() else pd.DataFrame()
        spec_gpt, spec_ds = rd("specialists_gpt52.csv"), rd("specialists_deepseek.csv")
        real_ids = set()
        sm = data_dir / "specialists_gpt52_summary.csv"
        legacy_agg = {r["assignment"]: r for r in pd.read_csv(sm).to_dict("records")} if sm.exists() else None

    for a, (_, _, n) in ASSIGN.items():
        got = int((master.assignment == a).sum())
        assert got == n, f"{a}: {got} rows, expected {n}"
    assert not master.duplicated(["assignment", "student_id"]).any(), "duplicate student ids"

    T, V, CI = compute_tables(master, spec_gpt, spec_ds, legacy_agg, args.qwk_labels)
    ver = verify(V, CI, args.qwk_labels)

    if not args.dry_run:
        res_dir.mkdir(parents=True, exist_ok=True)
        for k, df in T.items():
            df.to_csv(res_dir / f"{k}.csv", index=False)
        ver.to_csv(res_dir / "verification_report.csv", index=False)
        make_figures(master, T, res_dir, args.qwk_labels)

    # ---- console report
    print("\n=== DATA QUALITY (owner mode) ===" if owner else "\n=== REVIEWER MODE ===")
    if owner:
        lg = pd.DataFrame(log)
        if len(lg):
            print(lg.groupby(["assignment", "system", "issue"]).size().to_string())
        print(f"IDs anonymized: {master.shape[0]} submissions; mapping in {pdir / 'id_map.csv'} (DO NOT COMMIT)")
        if dropped:
            print(f"Rows dropped (not in human-graded roster): {len(dropped)} id(s) -> see console only, not logged publicly")
    print(f"\n=== PAPER NUMBER CHECK (QWK label mode = {args.qwk_labels}) ===")
    bad = ver[~ver.status.isin(["PASS", "PASS(CI~)"])]
    print(ver.status.value_counts().to_string())
    if len(bad):
        print("\nNot reproduced:\n" + bad.to_string(index=False))
    sens = T["qwk_label_sensitivity"]
    diff = sens[(sens.qwk_observed_labels - sens.qwk_fixed_0_10).abs() > 0.005]
    if len(diff):
        print("\n[NOTE] QWK changes when the full 0-10 label set is used instead of observed labels:")
        print(diff.to_string(index=False))

    if owner and args.archive_legacy and (data_dir / "scores_master.csv").exists() and (repo / "README.md").exists() \
            and "scores_master.csv" in (repo / "README.md").read_text(errors="ignore"):
        print("\n[INFO] repository already migrated (new README present): --archive-legacy skipped")
    elif owner and args.archive_legacy:
        moved = archive_legacy(repo, args.dry_run)
        print(f"\nLegacy items {'(dry-run) would be' if args.dry_run else ''} moved to archive/previous_submission/: {moved}")

    # ---- docs
    if (owner or args.write_docs) and not args.dry_run:
        status = ("All reproduced numbers match the paper to 3 decimals (CIs within bootstrap noise)."
                  if not len(bad) else
                  "The following items differ from the paper or could not be computed (see `results/verification_report.csv`):\n\n"
                  + "\n".join(f"* `{r.item}` {r.assignment}: paper {r.paper}, recomputed {r.computed} ({r.status})"
                              for r in bad.itertuples()))
        miss = []
        if not len(spec_gpt):
            miss.append("* `data/specialists_gpt52.csv`: GPT-5.2 per-submission specialist totals (Table 6 needs them).")
        if "multi_deepseek_bt4" in " ".join(str(x) for x in log) or not (len(spec_ds) and (spec_ds.assignment == "A4").any()):
            miss.append("* DeepSeek specialist logs for A4 (and A1/A2, paper limitation L4).")
        miss.append("* Pipeline source code (`agents/`) and rubrics: see their own folders.")
        spec_note = "only" if len(spec_ds) else "n/a"
        (repo / "README.md").write_text(README.format(B=B_BOOT, SEED=SEED, status=status, missing="\n".join(miss),
                                                      ds_spec_note="/A4" if len(spec_ds) and (spec_ds.assignment == "A4").any() else "only"))
        (repo / "DATA_POLICY.md").write_text(DATA_POLICY)
        (repo / "requirements.txt").write_text(REQS)
        if not (repo / "CITATION.cff").exists():
            (repo / "CITATION.cff").write_text(CFF)
        sc = repo / "scripts"
        sc.mkdir(exist_ok=True)
        if Path(__file__).resolve() != (sc / "build_release.py").resolve():
            shutil.copy(__file__, sc / "build_release.py")

    # ---- leak check on everything we publish
    if owner and not args.dry_run:
        pat = re.compile(r"\b\d{6,9}\b")
        leaks = []
        for p in list(data_dir.glob("*")) + list(res_dir.glob("*.csv")) + [repo / "README.md", repo / "DATA_POLICY.md"]:
            if p.suffix in (".csv", ".md", ".txt"):
                found = set(pat.findall(p.read_text(errors="ignore"))) & real_ids
                if found:
                    leaks.append((p.name, len(found)))
        if leaks:
            print(f"\n[FATAL] real student IDs found in published files: {leaks}")
            sys.exit(2)
        print("\n[OK] leak check: no real student ID appears in data/, results/, README, DATA_POLICY")
        print("\nTODO (cannot be automated): copy full pipeline code into agents/ (orchestrator, chairman, specialists, extract_text),"
              "\n  de-identify rubric .docx names if needed, then:  git add -A && git commit && git tag v1.0-fisat2026")
    if args.strict and len(bad):
        sys.exit(1)


if __name__ == "__main__":
    main()
