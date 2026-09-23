#!/usr/bin/env python3
"""
permutation_null_v2.py

County-label permutation null for the SCE county-metric screen.
Answers Frontiers Reviewer 1, major comment 1 (multiple comparisons).

Reproduces code/calc_metric_death_cc_v4.py exactly: weighted Pearson
correlation coefficient (CC), weights = population_2019 ^ 1.0, and a
per-(variable, year) valid set (both values finite, weight positive).

Null: permute county labels of the whole 5-year excess-death block, so the
year-to-year structure of the outcome is preserved and the max-over-years
statistic is not inflated. Predictors and weights stay with their county row.
The outcome's own missingness travels with it, exactly as re-running the
pipeline on permuted data would do.

Speed: the valid set differs from the full set by at most a handful of rows, so
the weighted sums are computed once over all counties and corrected by
subtracting the excluded rows. One matmul per permutation.
"""
import argparse, time, json
import numpy as np
import pandas as pd

DATA    = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
METLIST = 'ward_sem_clean2_k120/ward_sem_metrics.csv'
YEARS   = list(range(2020, 2025))
YCOLS   = [f'asedx_p_{y}' for y in YEARS]
WCOL    = 'population_2019'
MOD, STRONG = 0.30, 0.45


def cc_block(X, Xnan_cols, Xnan_rows, Yp, w, T1, T2):
    """
    Weighted Pearson CC for every (variable, year), with per-pair valid sets.
    X    : n x p, NaN already replaced by 0 (masked rows tracked separately)
    Yp   : n x 5, NaN marks invalid
    T1,T2: full-column weighted sums of x and x^2 (NaN rows contribute 0)
    Returns p x 5 array.
    """
    n, p = X.shape
    finite = np.isfinite(Yp)
    Yf = np.where(finite, Yp, 0.0)

    Xw = X * w[:, None]
    Sxy = Xw.T @ Yf                                   # p x 5, NaN-y rows drop out

    out = np.empty((p, 5))
    for k in range(5):
        bad = np.flatnonzero(~finite[:, k])           # counties with missing outcome
        Wk  = w.sum() - w[bad].sum()
        Sx  = T1 - (w[bad, None] * X[bad, :]).sum(axis=0)
        Sxx = T2 - (w[bad, None] * X[bad, :] ** 2).sum(axis=0)
        yk  = Yf[:, k]
        Sy  = w @ yk
        Syy = w @ (yk * yk)

        mx, my = Sx / Wk, Sy / Wk
        vx = Sxx / Wk - mx * mx
        vy = Syy / Wk - my * my
        cov = Sxy[:, k] / Wk - mx * my
        den = np.sqrt(np.maximum(vx, 0) * max(vy, 0))
        out[:, k] = np.where(den > 0, cov / den, np.nan)

        # variables carrying their own missing counties: correct exactly
        for j, rows in zip(Xnan_cols, Xnan_rows):
            ex = np.union1d(rows, bad)
            Wj = w.sum() - w[ex].sum()
            sx = T1[j] - (w[ex] * X[ex, j]).sum()
            sxx = T2[j] - (w[ex] * X[ex, j] ** 2).sum()
            sy = Sy - (w[ex] * yk[ex]).sum()
            syy = Syy - (w[ex] * yk[ex] ** 2).sum()
            sxy = Sxy[j, k] - (w[ex] * X[ex, j] * yk[ex]).sum()
            mxj, myj = sx / Wj, sy / Wj
            vxj = sxx / Wj - mxj * mxj
            vyj = syy / Wj - myj * myj
            dj = np.sqrt(max(vxj, 0) * max(vyj, 0))
            out[j, k] = (sxy / Wj - mxj * myj) / dj if dj > 0 else np.nan
    return out


def stats(CC):
    m = np.nanmax(np.abs(CC), axis=1)
    m = m[np.isfinite(m)]
    return int((m > MOD).sum()), int((m > STRONG).sum()), float(m.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-perm', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=20260918)
    ap.add_argument('--out-prefix', default='permutation_null/perm_null')
    ap.add_argument('--strata', type=int, default=0,
                    help='permute only within this many equal-count strata of 2019 population, '
                         'so an outcome can move only to a similarly sized county (0 = unrestricted)')
    ap.add_argument('--max-leverage', type=float, default=1.01,
                    help='drop predictors where one county supplies more than this share '
                         'of the weighted variance (1.01 = keep all)')
    a = ap.parse_args()

    t0 = time.time()
    mets = list(pd.read_csv(METLIST)['metric'])
    need = set(mets + YCOLS + [WCOL])
    df = pd.read_csv(DATA, usecols=lambda c: c in need, low_memory=False)
    mets = [m for m in mets if m in df.columns]

    X = df[mets].apply(pd.to_numeric, errors='coerce').values.astype(np.float64)
    Y = df[YCOLS].values.astype(np.float64)
    w = df[WCOL].values.astype(np.float64)
    X[~np.isfinite(X)] = np.nan
    Y[~np.isfinite(Y)] = np.nan
    ok = np.isfinite(w) & (w > 0)
    X, Y, w = X[ok], Y[ok], w[ok]
    n, p = X.shape

    if a.max_leverage < 1.0:
        wn0 = w / w.sum()
        mu0 = np.nansum(wn0[:, None] * X, axis=0)
        con = wn0[:, None] * (X - mu0) ** 2
        tot = np.nansum(con, axis=0)
        lev = np.nanmax(con, axis=0) / np.where(tot > 0, tot, np.nan)
        keepv = ~(lev > a.max_leverage)
        print(f'leverage filter {a.max_leverage}: dropping {int((~keepv).sum())} predictors')
        X = X[:, keepv]
        mets = [m for m, k in zip(mets, keepv) if k]
        p = X.shape[1]

    xnan = ~np.isfinite(X)
    Xnan_cols = list(np.flatnonzero(xnan.any(axis=0)))
    Xnan_rows = [np.flatnonzero(xnan[:, j]) for j in Xnan_cols]
    X = np.where(xnan, 0.0, X)
    T1 = w @ X
    T2 = w @ (X * X)
    neff = (w.sum() ** 2) / (w * w).sum()
    print(f'counties {n}   predictors {p}   Kish N_eff {neff:.1f}   '
          f'vars with missing cells {len(Xnan_cols)}   ({time.time()-t0:.0f}s)')

    # ---------- observed, validated against the production file ----------
    CC_obs = cc_block(X, Xnan_cols, Xnan_rows, Y, w, T1, T2)
    prod = pd.read_csv('full_w1.0/metric_x_death_cc_1.0_0.csv').set_index('metric').loc[mets, YCOLS].values
    print(f'max |difference| vs production CC file: {np.nanmax(np.abs(CC_obs - prod)):.2e}')
    del prod
    o30, o45, omax = stats(CC_obs)
    per_year = [int((np.abs(CC_obs[:, k]) > MOD).sum()) for k in range(5)]
    print(f'OBSERVED: >0.30 {o30}   >0.45 {o45}   max|CC| {omax:.3f}   per-year {per_year}')

    # ---------- permutations ----------
    rng = np.random.default_rng(a.seed)

    if a.strata > 0:
        edges = np.quantile(w, np.linspace(0, 1, a.strata + 1))
        grp = np.clip(np.searchsorted(edges, w, side='right') - 1, 0, a.strata - 1)
        blocks = [np.flatnonzero(grp == g) for g in range(a.strata)]
        blocks = [b for b in blocks if len(b) > 1]
        print(f'stratified permutation: {len(blocks)} population strata, '
              f'sizes {min(len(b) for b in blocks)}-{max(len(b) for b in blocks)}, '
              f'population ranges {edges[0]:,.0f} to {edges[-1]:,.0f}')

        def draw():
            idx = np.arange(n)
            for b in blocks:
                idx[b] = b[rng.permutation(len(b))]
            return idx
    else:
        def draw():
            return rng.permutation(n)

    rec = []
    t1 = time.time()
    for i in range(a.n_perm):
        CC = cc_block(X, Xnan_cols, Xnan_rows, Y[draw()], w, T1, T2)
        rec.append(stats(CC))
        if (i + 1) % 100 == 0:
            print(f'  {i+1}/{a.n_perm}   ({time.time()-t1:.0f}s)')

    c30 = np.array([r[0] for r in rec])
    c45 = np.array([r[1] for r in rec])
    mx  = np.array([r[2] for r in rec])
    N = len(rec)
    p30 = (int((c30 >= o30).sum()) + 1) / (N + 1)
    p45 = (int((c45 >= o45).sum()) + 1) / (N + 1)
    pmx = (int((mx >= omax).sum()) + 1) / (N + 1)
    crit = float(np.percentile(mx, 95))

    print(f'\n===== permutation null, {N} permutations =====')
    print(f'  variables with max|CC| > 0.30 : observed {o30:4d} | null mean {c30.mean():6.2f} '
          f'median {np.median(c30):5.1f} p95 {np.percentile(c30,95):5.1f} max {c30.max():4d} | p = {p30:.4f}')
    print(f'  variables with max|CC| > 0.45 : observed {o45:4d} | null mean {c45.mean():6.2f} '
          f'p95 {np.percentile(c45,95):5.1f} max {c45.max():4d} | p = {p45:.4f}')
    print(f'  global max |CC|               : observed {omax:.3f} | null mean {mx.mean():.3f} '
          f'p95 {crit:.3f} p99 {np.percentile(mx,99):.3f} max {mx.max():.3f} | p = {pmx:.4f}')
    print(f'\n  FWER-controlling critical |CC| (95th percentile of the null global max) = {crit:.3f}')
    print(f'  false-discovery estimate at the 0.30 band: {c30.mean():.2f} expected by chance '
          f'vs {o30} observed  ({100*c30.mean()/o30:.2f}%)')

    res = dict(data_file=DATA, n_counties=int(n), n_predictors=int(p), kish_n_eff=float(neff),
               n_perm=N, seed=a.seed, observed=dict(gt030=o30, gt045=o45, max_absCC=omax,
               per_year_gt030=dict(zip(YEARS, per_year))),
               null=dict(gt030=dict(mean=float(c30.mean()), median=float(np.median(c30)),
                                    p95=float(np.percentile(c30, 95)), max=int(c30.max()), p_value=p30),
                         gt045=dict(mean=float(c45.mean()), p95=float(np.percentile(c45, 95)),
                                    max=int(c45.max()), p_value=p45),
                         global_max=dict(mean=float(mx.mean()), median=float(np.median(mx)),
                                         p95=crit, p99=float(np.percentile(mx, 99)),
                                         max=float(mx.max()), p_value=pmx)),
               fwer_critical_absCC=crit)
    with open(a.out_prefix + '_summary.json', 'w') as f:
        json.dump(res, f, indent=2)
    pd.DataFrame(dict(n_gt_030=c30, n_gt_045=c45, global_max_absCC=mx)).to_csv(
        a.out_prefix + '_draws.csv', index=False)
    print(f'\nSaved {a.out_prefix}_summary.json and _draws.csv   total {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
