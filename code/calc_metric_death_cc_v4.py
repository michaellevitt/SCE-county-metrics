#!/usr/bin/env python3
"""
calc_metric_death_cc.py

Read the imputed county data matrix (BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.csv)
and compute the weighted Pearson correlation coefficient of every non-death metric with each
of the 27 death measures (columns starting with 'asedx_p_').

Weights: <weight-col> ^ <weight-power>  (default base ased_bl_2019; e.g. population_2019).
         power 0 = unweighted. Non-positive/NaN base => weight 0 (county excluded).

Output CSV columns:
  metric, CC for each death measure

STDOUT:
  N_eff (Kish's effective sample size from weights)
  Log10(p-value) summary
  Smallest |CC| that achieves log10(p) < -5 (i.e. p < 0.00001)

STDERR:
  Progress, diagnostics, NaN pair listing with reasons

Usage:
  cat BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.csv | \
      python calc_metric_death_cc.py --output metric_x_death_cc.csv

Options:
  --input FILE           Input CSV (default: read from STDIN)
  --output FILE          Output CSV (default: metric_x_death_cc.csv)
  --min-valid N          Minimum number of valid (non-NaN) pairs required (default: 30)
  --prefixes-to-exclude  Comma-separated prefixes to skip (default: standard exclusions)
  --death-prefix PREFIX  Prefix identifying death measures (default: asedx_p_)
  --weight-power FLOAT   Power for weight transform (default: 0.5)
  --lp-threshold FLOAT   Log10(p) significance threshold (default: -5.0)
  --min-ased-bl FLOAT    Minimum ased_bl_2019 to include a county (default: 0.0)
  --min-pop2019 FLOAT    Minimum population_2019 to include a county (default: 0.0)
"""

import sys
import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
from datetime import datetime
from collections import Counter
from scipy import stats as scipy_stats

def _tee(path):
    """Print 'Saved <relpath>' to stdout and stderr."""
    _p = str(path)
    try:
        _rel = os.path.relpath(_p)
    except ValueError:
        _rel = _p
    msg = 'Saved ' + _rel
    print(msg)
    print(msg, file=sys.stderr, flush=True)


SCRIPT_VERSION = "calc_metric_death_cc.py v4.0"

def log_message(msg, level=1, tee=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    indent = "  " * (level - 1)
    formatted = f"[{ts}] {indent}{msg}"
    print(formatted, flush=True)
    if tee:
        print(formatted, flush=True, file=sys.stderr)

def effective_n(weights):
    """Kish's effective sample size: N_eff = (sum w)^2 / sum(w^2)"""
    w = np.asarray(weights, dtype=np.float64)
    w = w[~np.isnan(w) & (w > 0)]
    s1 = np.sum(w)
    s2 = np.sum(w * w)
    if s2 == 0:
        return 0.0
    return (s1 * s1) / s2

def cc_to_log10_pvalue(r, n_eff):
    """Log10 of two-tailed p-value from CC r and effective N."""
    if n_eff <= 2 or np.isnan(r):
        return np.nan
    df = n_eff - 2.0
    r_abs = min(abs(r), 1.0 - 1e-15)
    t_stat = r_abs * np.sqrt(df / (1.0 - r_abs * r_abs))
    pval = 2.0 * scipy_stats.t.sf(t_stat, df)
    if pval <= 0:
        return -300.0  # underflow floor
    return np.log10(pval)

def parse_args():
    p = argparse.ArgumentParser(description="Weighted Pearson CC of metrics vs death measures")
    p.add_argument("--input", type=str, default=None,
                   help="Input CSV path (default: STDIN)")
    p.add_argument("--output", type=str, default="metric_x_death_cc.csv",
                   help="Output CSV path")
    p.add_argument("--min-valid", type=int, default=30,
                   help="Min valid pairs for CC (default: 30)")
    p.add_argument("--death-prefix", type=str, default="asedx_p_",
                   help="Prefix for death measure columns")
    p.add_argument("--prefixes-to-exclude", type=str,
                   default="asmr,cmr_,cmrx,deat,fips,le_2,le_b,lex_,popu,PHT_,f00001,M_,E_,MP_,EP_,F_,EPL_,SPL_,RPL_,Dy,One,Two,PCTPOV,MEDHHINC,POV_",
                   help="Comma-separated prefixes to exclude from metrics")
    p.add_argument("--weight-col", type=str, default="ased_bl_2019",
                   help="Column used as the weight base (default: ased_bl_2019; e.g. population_2019)")
    p.add_argument("--weight-power", type=float, default=0.5,
                   help="Power to raise the weight base to (default: 0.5; 0 = unweighted)")
    p.add_argument("--lp-threshold", type=float, default=-5.0,
                   help="Log10(p-value) threshold for significance (default: -5.0, i.e. p < 0.00001)")
    p.add_argument("--min-ased-bl", type=float, default=0.0,
                   help="Minimum ased_bl_2019 to include a county (default: 0.0, no filter)")
    p.add_argument("--min-pop2019", type=float, default=0.0,
                   help="Minimum population_2019 to include a county (default: 0.0, no filter)")
    return p.parse_args()

def main():
    args = parse_args()
    log_message(SCRIPT_VERSION)

    # ---- Load data ----
    log_message("Loading data...")
    t0 = time.time()
    if args.input:
        df = pd.read_csv(args.input, low_memory=False)
    else:
        df = pd.read_csv(sys.stdin, low_memory=False)
    log_message(f"  Loaded {df.shape[0]} rows x {df.shape[1]} cols in {time.time()-t0:.1f}s", 2)

    # ---- Identify death measure columns ----
    death_cols = sorted([c for c in df.columns if c.startswith(args.death_prefix)])
    log_message(f"  Found {len(death_cols)} death measures: {death_cols}", 2)
    if len(death_cols) == 0:
        log_message("ERROR: No death measure columns found!", 1)
        sys.exit(1)

    # ---- Replace inf with NaN in death measures (from ased_bl==0 counties) ----
    n_inf_total = 0
    for dcol in death_cols:
        n_inf = np.isinf(df[dcol]).sum()
        if n_inf > 0:
            df[dcol] = df[dcol].replace([np.inf, -np.inf], np.nan)
            n_inf_total += n_inf
            log_message(f"  {dcol}: replaced {n_inf} inf values with NaN", 2)
    if n_inf_total > 0:
        log_message(f"  Total inf->NaN replacements in death measures: {n_inf_total}", 2)
    else:
        log_message(f"  No inf values found in death measures", 2)

    # ---- Build weights from <weight_col> ^ <power> ----
    weight_col = args.weight_col
    if weight_col not in df.columns:
        log_message(f"ERROR: Weight column '{weight_col}' not found in data!", 1)
        sys.exit(1)
    raw_weights = df[weight_col].values.astype(np.float64)
    # Guard against division by zero / invalid bases: a non-positive or NaN base
    # gets weight 0 (county excluded), so it can never divide a zero weight-sum.
    safe_base = np.where(np.isnan(raw_weights) | (raw_weights <= 0), 0.0, raw_weights)
    weights = np.where(safe_base > 0, np.power(safe_base, args.weight_power), 0.0)
    weights = np.where(np.isnan(weights) | (weights < 0), 0.0, weights)

    # ---- Apply --min-ased-bl filter: zero out weights for counties below threshold ----
    # Always keyed to ased_bl_2019 (county-inclusion criterion), independent of --weight-col.
    if args.min_ased_bl > 0:
        if "ased_bl_2019" not in df.columns:
            log_message("ERROR: 'ased_bl_2019' not found -- cannot apply --min-ased-bl filter", 1)
            sys.exit(1)
        ased_bl = df["ased_bl_2019"].values.astype(np.float64)
        below = np.isnan(ased_bl) | (ased_bl < args.min_ased_bl)
        n_below = np.sum(below & (weights > 0))
        weights = np.where(below, 0.0, weights)
        log_message(f"  --min-ased-bl {args.min_ased_bl}: excluded {n_below} counties with ased_bl_2019 < {args.min_ased_bl}", 2)

    # ---- Apply --min-pop2019 filter: zero out weights for counties below threshold ----
    if args.min_pop2019 > 0:
        pop_col = "population_2019"
        if pop_col not in df.columns:
            log_message(f"ERROR: '{pop_col}' not found -- cannot apply --min-pop2019 filter", 1)
            sys.exit(1)
        pop_vals = df[pop_col].values.astype(np.float64)
        below_pop = np.isnan(pop_vals) | (pop_vals < args.min_pop2019)
        n_below_pop = np.sum(below_pop & (weights > 0))
        weights = np.where(below_pop, 0.0, weights)
        log_message(f"  --min-pop2019 {args.min_pop2019}: excluded {n_below_pop} counties with {pop_col} < {args.min_pop2019}", 2)

    n_valid_w = np.sum(weights > 0)
    log_message(f"  Weights: {weight_col}^{args.weight_power}, {n_valid_w} counties with positive weight", 2)

    # ---- Compute and report N_eff ----
    n_eff_global = effective_n(weights)
    log_message(f"  N_eff (Kish): {n_eff_global:.1f}  (from {int(n_valid_w)} counties with positive weight)", 2)

    # ---- Identify metric columns (exclude deaths, excluded prefixes, non-numeric) ----
    exclude_prefixes = [p.strip() for p in args.prefixes_to_exclude.split(",") if p.strip()]
    exclude_prefixes.append("asedx_p_")
    exclude_prefixes.append("ased_")
    exclude_prefixes.append("asedx_")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    metric_cols = []
    for c in numeric_cols:
        skip = False
        for px in exclude_prefixes:
            if c.startswith(px):
                skip = True
                break
        if not skip:
            metric_cols.append(c)

    # Exclude specific metrics by exact name
    exact_exclude = {'POP_COU'}
    metric_cols = [c for c in metric_cols if c not in exact_exclude]

    metric_cols = sorted(metric_cols)
    log_message(f"  {len(metric_cols)} metric columns after exclusions", 2)

    # ---- Replace inf with NaN in metric columns ----
    n_inf_metrics = 0
    for mcol in metric_cols:
        n_inf = np.isinf(df[mcol]).sum()
        if n_inf > 0:
            df[mcol] = df[mcol].replace([np.inf, -np.inf], np.nan)
            n_inf_metrics += n_inf
    if n_inf_metrics > 0:
        log_message(f"  Replaced {n_inf_metrics} inf values with NaN across metric columns", 2)

    # ---- Compute weighted Pearson CC for each metric x each death measure ----
    log_message(f"Computing weighted Pearson CC: {len(metric_cols)} metrics x {len(death_cols)} death measures...")
    t1 = time.time()

    results = []        # rows for output CSV (CC values)
    nan_reasons = []    # diagnostic: (metric, death_col, reason)
    n_metrics = len(metric_cols)
    report_every = max(1, n_metrics // 20)

    # Collect CC + n_eff per pair for p-value computation
    all_cc = []         # list of (metric, death_col, cc, n_eff_pair)

    for i, mcol in enumerate(metric_cols):
        if (i + 1) % report_every == 0:
            log_message(f"  {i+1}/{n_metrics} metrics processed...", 2)

        row = {"metric": mcol}
        x = df[mcol].values.astype(np.float64)

        for dcol in death_cols:
            y = df[dcol].values.astype(np.float64)

            # Valid pairs: both finite (excludes NaN AND inf) and positive weight
            valid = np.isfinite(x) & np.isfinite(y) & (weights > 0)
            nv = np.sum(valid)

            if nv < args.min_valid:
                row[dcol] = np.nan
                row[f"LP_{dcol}"] = np.nan
                nan_reasons.append((mcol, dcol, f"too_few_valid (n={nv}, need {args.min_valid})"))
            else:
                xv = x[valid]
                yv = y[valid]
                wv = weights[valid]
                w_sum = np.sum(wv)
                wn = wv / w_sum

                xm = np.sum(wn * xv)
                ym = np.sum(wn * yv)
                xc = xv - xm
                yc = yv - ym

                cov_xy = np.sum(wn * xc * yc)
                var_x  = np.sum(wn * xc * xc)
                var_y  = np.sum(wn * yc * yc)
                denom  = np.sqrt(var_x * var_y)

                if denom > 0:
                    cc = cov_xy / denom
                    row[dcol] = round(cc, 6)
                    neff_pair = effective_n(wv)
                    lp = cc_to_log10_pvalue(cc, neff_pair)
                    row[f"LP_{dcol}"] = round(lp, 3) if not np.isnan(lp) else np.nan
                    all_cc.append((mcol, dcol, cc, neff_pair, lp))
                else:
                    row[dcol] = np.nan
                    row[f"LP_{dcol}"] = np.nan
                    if var_x == 0 and var_y == 0:
                        reason = "zero_variance_both"
                    elif var_x == 0:
                        reason = "zero_variance_metric"
                    else:
                        reason = "zero_variance_death"
                    nan_reasons.append((mcol, dcol, reason))

        results.append(row)

    elapsed = time.time() - t1
    log_message(f"  Done in {elapsed:.1f}s", 2)

    # ---- Build output DataFrame ----
    out = pd.DataFrame(results)

    # ---- Compute Sum_|LP|_LP<={threshold} for each metric ----
    sum_col_name = f"Sum_|LP|_LP<={args.lp_threshold}"
    sum_vals = []
    for idx, row in out.iterrows():
        total = 0.0
        for dcol in death_cols:
            lp_val = row[f"LP_{dcol}"]
            if not np.isnan(lp_val) and lp_val <= args.lp_threshold:
                total += abs(lp_val)
        sum_vals.append(round(total, 6))
    out[sum_col_name] = sum_vals

    # ---- Sort descending by Sum_|LP| ----
    out = out.sort_values(sum_col_name, ascending=False).reset_index(drop=True)

    # ---- Build count of significant metrics per death measure ----
    count_sig = {}
    for dcol in death_cols:
        lp_col = f"LP_{dcol}"
        count_sig[dcol] = (out[lp_col] <= args.lp_threshold).sum()
    count_sig[sum_col_name] = (out[sum_col_name] > 0).sum()

    # ---- Assemble column order ----
    col_order = ["metric"]
    for dcol in death_cols:
        col_order.append(dcol)
        col_order.append(f"LP_{dcol}")
    col_order.append(sum_col_name)

    out = out[col_order]

    # ---- Save CC CSV (no count row) ----
    out.to_csv(args.output, index=False)
    _tee(args.output)
    log_message(f"Wrote {out.shape[0]} x {out.shape[1]} to {args.output}")

    # ---- Print count of significant metrics to STDERR ----
    log_message(f"")
    log_message(f"Count of significant metrics (LP <= {args.lp_threshold}) per death measure:")
    log_message(f"  {'Death measure':<30} {'Count':>6}  {f'Min |CC| at LP<={args.lp_threshold}':>20}  {'CC at min LP':>14}", 2)
    log_message(f"  {'-'*30} {'-'*6}  {'-'*20}  {'-'*14}", 2)
    for dcol in death_cols:
        lp_col = f"LP_{dcol}"
        sig_mask = out[lp_col] <= args.lp_threshold
        cnt = count_sig[dcol]
        if cnt > 0:
            min_abs_cc = out.loc[sig_mask, dcol].abs().min()
            idx_min_lp = out[lp_col].idxmin()
            cc_at_min_lp = out.loc[idx_min_lp, dcol]
            log_message(f"  {dcol:<30} {cnt:>6}  {min_abs_cc:>20.6f}  {cc_at_min_lp:>+14.6f}", 2)
        else:
            log_message(f"  {dcol:<30} {cnt:>6}  {'n/a':>20}  {'n/a':>14}", 2)
    log_message(f"  {sum_col_name:<30} {count_sig[sum_col_name]:>6}", 2)

    # ---- Summary stats to STDERR ----
    cc_vals = out[death_cols].values.astype(float).flatten()
    cc_valid = cc_vals[~np.isnan(cc_vals)]
    log_message(f"  CC range: [{np.min(cc_valid):.4f}, {np.max(cc_valid):.4f}]", 2)
    log_message(f"  Mean |CC|: {np.mean(np.abs(cc_valid)):.4f}", 2)
    n_nan = np.sum(np.isnan(cc_vals))
    log_message(f"  NaN entries: {n_nan} / {len(cc_vals)}", 2)

    # ---- Print NaN diagnostics to STDERR ----
    if nan_reasons:
        log_message(f"", 1)
        log_message(f"NaN diagnostic breakdown ({len(nan_reasons)} NaN pairs):", 1)
        reason_counts = Counter(r.split(" (")[0].strip() for _, _, r in nan_reasons)
        for reason, cnt in reason_counts.most_common():
            log_message(f"  {reason}: {cnt}", 2)

        log_message(f"", 1)
        log_message(f"Full NaN pair list:", 1)
        for mcol, dcol, reason in sorted(nan_reasons):
            log_message(f"  {mcol} x {dcol} : {reason}", 2)

    # ======================================================================
    # STDOUT output: N_eff, log10(p-values), significance threshold
    # ======================================================================
    print("=" * 80)
    print(f"N_eff (Kish, global): {n_eff_global:.1f}  (from {int(n_valid_w)} counties)")
    print("=" * 80)

    # Compute log10(p) for all valid CC pairs
    print(f"\nTotal valid CC pairs: {len(all_cc)}")

    lp_vals = np.array([lp for _, _, _, _, lp in all_cc if not np.isnan(lp)])
    print(f"\nLog10(p-value) summary:")
    print(f"  min log10(p)    = {np.min(lp_vals):.2f}")
    print(f"  max log10(p)    = {np.max(lp_vals):.2f}")
    print(f"  median log10(p) = {np.median(lp_vals):.2f}")

    # Find significance threshold: smallest |CC| with p < 0.00001 (log10(p) < -5)
    sig_threshold = args.lp_threshold
    sig_pairs = [(m, d, cc, neff, lp) for m, d, cc, neff, lp in all_cc
                 if not np.isnan(lp) and lp <= sig_threshold]

    pval_str = f"10^{sig_threshold}"
    print(f"\n{'=' * 80}")
    print(f"Pairs with p < {pval_str} (log10(p) < {sig_threshold}): {len(sig_pairs)} / {len(all_cc)}")

    if sig_pairs:
        abs_ccs_sig = [abs(cc) for _, _, cc, _, _ in sig_pairs]
        min_abs_cc = min(abs_ccs_sig)
        max_abs_cc = max(abs_ccs_sig)
        print(f"  |CC| range among significant pairs: [{min_abs_cc:.6f}, {max_abs_cc:.6f}]")
        print(f"  Smallest |CC| with p < {pval_str}:  {min_abs_cc:.6f}")
        diff = max_abs_cc - min_abs_cc
        # Find the death measure with highest |CC|
        max_pair = max(sig_pairs, key=lambda t: abs(t[2]))
        max_cc_death = max_pair[1]
        print(f"  Final: N_eff * (Max|CC| - Min|CC|)^2 = {n_eff_global:.1f} * ({max_abs_cc:.6f} - {min_abs_cc:.6f})^2 = {n_eff_global * diff * diff:.2f}  max_death={max_cc_death}  --min-ased-bl={args.min_ased_bl} --min-pop2019={args.min_pop2019} --weight-power={args.weight_power}")

        # Show the pair(s) at that boundary
        for m, d, cc, neff, lp in sig_pairs:
            if abs(abs(cc) - min_abs_cc) < 1e-8:
                print(f"    -> metric={m}, death={d}, CC={cc:.6f}, N_eff={neff:.1f}, log10(p)={lp:.2f}")
    else:
        print("  No pairs reach this significance level.")

    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
