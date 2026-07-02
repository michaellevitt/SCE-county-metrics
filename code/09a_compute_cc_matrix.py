#!/usr/bin/env python3
"""
09a_compute_cc_matrix.py

Compute the full pairwise weighted CC matrix for a SINGLE condition.
Save as a square CSV (metric x metric).

Usage:
  cat BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NEW.csv | \\
    python3 09a_compute_cc_matrix.py \\
      --metrics-file metrics_passing_GOOD.csv \\
      --weight-col population_2019 \\
      --threshold 54400 \\
      --power 0.00 \\
      --output full_cc_matrix.csv

Inputs:
  STDIN:          Full imputed county data CSV
  --metrics-file: CSV with column 'metric' listing candidate metric names
  --weight-col:   Weight column name (e.g. population_2019)
  --threshold:    Minimum value for weight column (counties below are excluded)
  --power:        Exponent applied to weights (0 = unweighted)

Output:
  Square CSV: rows and columns are metric names, values are signed CC.
  Death measures (asedx_p_202*) are included as the first rows/columns.
"""

import sys
import argparse
import time
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import rankdata


def weighted_rank(x, w):
    """Population-weighted average ranks (weighted-ECDF midranks).
    Reduces to ordinary average ranks (up to an additive constant) when weights
    are equal; a heavy observation occupies proportionally more rank space."""
    x = np.asarray(x, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    xs = x[order]; ws = w[order]
    below = np.cumsum(ws) - ws
    is_start = np.ones(len(xs), dtype=bool)
    is_start[1:] = xs[1:] != xs[:-1]
    grp = np.cumsum(is_start) - 1
    grp_w = np.bincount(grp, weights=ws)
    grp_below = below[is_start]
    rank_sorted = grp_below[grp] + 0.5 * grp_w[grp]
    out = np.empty(len(xs), dtype=np.float64)
    out[order] = rank_sorted
    return out

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



def log(msg, level=1, tee=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    indent = "  " * (level - 1)
    formatted = f"[{ts}] {indent}{msg}"
    print(formatted, flush=True)
    if tee:
        print(formatted, flush=True, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Compute full pairwise CC matrix for one condition.",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--metrics-file', required=True,
                        help="CSV with column 'metric'")
    parser.add_argument('--weight-col', required=True,
                        help="Weight column (e.g. population_2019)")
    parser.add_argument('--threshold', type=float, required=True,
                        help="Minimum weight value for county inclusion")
    parser.add_argument('--power', type=float, required=True,
                        help="Exponent on weights (0 = unweighted)")
    parser.add_argument('--method', choices=['pearson', 'spearman'], default='pearson',
                        help="Correlation type (default: pearson). 'spearman' = weighted "
                             "Pearson on per-column ranks.")
    parser.add_argument('--rank-mode', choices=['weighted', 'plain'], default='weighted',
                        help="Ranking for --method spearman (default: weighted). 'weighted' "
                             "= population-weighted ECDF ranks (proper); 'plain' = unweighted.")
    parser.add_argument('--output', default='full_cc_matrix.csv',
                        help="Output CSV path")
    args = parser.parse_args()

    # ---- Load metrics list ----
    metrics_df = pd.read_csv(args.metrics_file)
    metrics_from_file = metrics_df['metric'].tolist()
    log(f"Loaded {len(metrics_from_file)} candidate metrics from {args.metrics_file}", tee=True)

    # ---- Read county data ----
    log("Reading county data from STDIN...")
    t0 = time.time()
    df = pd.read_csv(sys.stdin, low_memory=False)
    log(f"Read {df.shape[0]} rows x {df.shape[1]} cols in {time.time()-t0:.1f} sec")

    # ---- Identify death measures ----
    death_measures = sorted([c for c in df.columns if c.startswith('asedx_p_202')])
    log(f"Found {len(death_measures)} death measures")

    # ---- Build metric list: death first, then candidates ----
    metrics_from_file = [m for m in metrics_from_file if m in df.columns]
    non_death = [m for m in metrics_from_file if not m.startswith('asedx_p_202')]
    metrics = death_measures + non_death
    n_metrics = len(metrics)
    log(f"Combined: {len(death_measures)} death + {len(non_death)} candidate = {n_metrics} total")

    # ---- Filter rows by threshold ----
    if args.threshold > 0:
        mask = df[args.weight_col] >= args.threshold
        filtered = df[mask]
    else:
        filtered = df
    n_counties = len(filtered)
    log(f"Condition: {args.weight_col} >= {args.threshold}, power={args.power:.2f} -> {n_counties} counties")

    # ---- Compute weights ----
    w_raw = filtered[args.weight_col].values.astype(np.float64)
    w = np.power(w_raw, args.power) if args.power > 0 else np.ones_like(w_raw)
    w_norm = w / w.sum()

    # ---- Extract data matrix ----
    data = filtered[metrics].values.astype(np.float64)

    # Handle inf (e.g. asedx_p for very small counties with ased_bl~0)
    inf_mask = np.isinf(data)
    if inf_mask.any():
        n_inf = int(inf_mask.sum())
        log(f"Replacing {n_inf} inf with NaN (then weighted column mean)")
        data = np.where(inf_mask, np.nan, data)

    # Handle NaN
    nan_mask = np.isnan(data)
    if nan_mask.any():
        n_nan = int(nan_mask.sum())
        log(f"Replacing {n_nan} NaN with weighted column means")
        col_means = np.nansum(w_norm[:, None] * np.where(nan_mask, 0, data), axis=0) / \
                    np.sum(w_norm[:, None] * ~nan_mask, axis=0)
        data = np.where(nan_mask, col_means, data)

    # ---- Spearman: rank-transform each column (then weighted Pearson on ranks) ----
    if args.method == "spearman":
        if args.rank_mode == "weighted":
            log("Weighted-ECDF rank transform per column (proper weighted Spearman)...")
            data = np.column_stack([weighted_rank(data[:, k], w_norm)
                                    for k in range(data.shape[1])])
        else:
            log("Plain (unweighted) rank transform per column...")
            data = np.apply_along_axis(rankdata, 0, data)

    # ---- Weighted CC matrix ----
    log(f"Computing {n_metrics}x{n_metrics} {args.method} CC matrix ({n_metrics*(n_metrics-1)//2:,} pairs)...", tee=True)
    t0 = time.time()

    means = np.sum(w_norm[:, None] * data, axis=0)
    centered = data - means
    variances = np.sum(w_norm[:, None] * centered**2, axis=0)
    stds = np.sqrt(variances)
    stds[stds == 0] = 1
    standardized = centered / stds
    weighted = standardized * np.sqrt(w_norm[:, None])
    cc = weighted.T @ weighted
    np.fill_diagonal(cc, 1.0)

    elapsed = time.time() - t0
    log(f"Done in {elapsed:.1f} sec", tee=True)

    # ---- Stats ----
    triu = cc[np.triu_indices(n_metrics, k=1)]
    log(f"CC range: [{triu.min():.4f}, {triu.max():.4f}]")
    log(f"Pairs |CC|>0.90: {np.sum(np.abs(triu) > 0.90):,}")
    log(f"Pairs |CC|>0.95: {np.sum(np.abs(triu) > 0.95):,}")

    # ---- Save ----
    log(f"Saving {n_metrics}x{n_metrics} matrix to {args.output}...")
    t0 = time.time()
    cc_df = pd.DataFrame(np.round(cc, 4), index=metrics, columns=metrics)
    cc_df.to_csv(args.output)
    _tee(args.output)
    log(f"Saved in {time.time()-t0:.1f} sec ({os.path.getsize(args.output) / 1e6:.1f} MB)", tee=True)

    log("Done.")


import os
import sys

if __name__ == "__main__":
    main()
