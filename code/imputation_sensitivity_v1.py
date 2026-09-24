#!/usr/bin/env python3
"""
imputation_sensitivity_v1.py

Two data-handling defects found while answering Frontiers Reviewer 2, and the
sensitivity analyses that bound their effect.

Defect 1, the outcome.
  Kalawao County, Hawaii (15005) and Loving County, Texas (48301) recorded no
  deaths across the 2017-2019 baseline, so their expected count is zero and the
  excess-death proportion is undefined. In 2022-2024 the source value is
  infinite and code/calc_metric_death_cc_v4.py drops the pair. In 2020 and 2021
  the source value is missing rather than infinite, so step 9 of
  code/00_assemble_merged_BEN_file_v7.py filled it with the column mean and both
  counties were retained. Test: drop them from every year.

Defect 2, the predictors.
  AHRF withholds any three-year or five-year vital-statistics count below 10,
  exactly the CDC WONDER rule, and leaves the cell blank. Step 9 filled those
  blanks with the column mean, which is the mean of the surviving large counts.
  A suppressed cell therefore received a high value when the true value is 0-9.
  Test: restore the suppressed cells to the ends of their true range, 0 and 9,
  and recompute. Also recompute using only the variables with no filled cell.

The decisive test, added 23 September 2026: leave every filled-in cell missing.
  The fill matters less through heavily filled variables than through single
  filled cells in very small counties. Where Kalawao's value for a count
  variable was blank, the fill supplied the mean county count, and division by
  its 85 residents made that hundreds of times the largest real county. Such a
  value can supply over 90% of a variable's weighted variance. Variables whose
  real data cover less than COVERAGE of the population are set aside in this
  test, since otherwise a variable seen in four counties is correlated on four
  points.

Weighted Pearson machinery is taken from code/permutation_null_v2.py, which
reproduces code/calc_metric_death_cc_v4.py to 5e-7.

Usage:
    python3 code/imputation_sensitivity_v1.py
"""
import json
import os

import numpy as np
import pandas as pd

DATA    = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
RAW     = 'data/raw/AHRF2020.fips.csv'
METLIST = 'ward_sem_clean2_k120/ward_sem_metrics.csv'
PROD    = 'full_w1.0/metric_x_death_cc_1.0_0.csv'
OUTDIR  = 'imputation_sensitivity'
YEARS   = list(range(2020, 2025))
YCOLS   = [f'asedx_p_{y}' for y in YEARS]
WCOL    = 'population_2019'
MOD, STRONG = 0.30, 0.45
ZERO_BASELINE = ['15005', '48301']          # Kalawao HI, Loving TX
KALAWAO = '15005'
# When filled-in cells are left missing, a variable with real data for only a
# handful of counties is correlated on a handful of points and can reach 1.000.
# Such variables are set aside: real data must cover this share of the weight.
COVERAGE = 0.90


def cc_block(X, Yp, w):
    """Weighted Pearson CC for every (variable, year) with per-pair valid sets.

    X may hold NaN; Yp may hold NaN. A county enters a given (variable, year)
    only when both values are finite and the weight is positive.
    """
    n, p = X.shape
    xnan = ~np.isfinite(X)
    nan_cols = list(np.flatnonzero(xnan.any(axis=0)))
    nan_rows = [np.flatnonzero(xnan[:, j]) for j in nan_cols]
    Xz = np.where(xnan, 0.0, X)
    T1 = w @ Xz
    T2 = w @ (Xz * Xz)

    finite = np.isfinite(Yp)
    Yf = np.where(finite, Yp, 0.0)
    Sxy = (Xz * w[:, None]).T @ Yf

    out = np.empty((p, Yp.shape[1]))
    for k in range(Yp.shape[1]):
        bad = np.flatnonzero(~finite[:, k])
        Wk = w.sum() - w[bad].sum()
        Sx = T1 - (w[bad, None] * Xz[bad, :]).sum(axis=0)
        Sxx = T2 - (w[bad, None] * Xz[bad, :] ** 2).sum(axis=0)
        yk = Yf[:, k]
        Sy = w @ yk
        Syy = w @ (yk * yk)

        mx, my = Sx / Wk, Sy / Wk
        vx = Sxx / Wk - mx * mx
        vy = Syy / Wk - my * my
        cov = Sxy[:, k] / Wk - mx * my
        den = np.sqrt(np.maximum(vx, 0) * max(vy, 0))
        out[:, k] = np.where(den > 0, cov / den, np.nan)

        for j, rows in zip(nan_cols, nan_rows):
            ex = np.union1d(rows, bad)
            Wj = w.sum() - w[ex].sum()
            sx = T1[j] - (w[ex] * Xz[ex, j]).sum()
            sxx = T2[j] - (w[ex] * Xz[ex, j] ** 2).sum()
            sy = Sy - (w[ex] * yk[ex]).sum()
            syy = Syy - (w[ex] * yk[ex] ** 2).sum()
            sxy = Sxy[j, k] - (w[ex] * Xz[ex, j] * yk[ex]).sum()
            mxj, myj = sx / Wj, sy / Wj
            vxj = sxx / Wj - mxj * mxj
            vyj = syy / Wj - myj * myj
            dj = np.sqrt(max(vxj, 0) * max(vyj, 0))
            out[j, k] = (sxy / Wj - mxj * myj) / dj if dj > 0 else np.nan
    return out


def summary(CC, label, valid=None):
    with np.errstate(all='ignore'):
        ab = np.abs(CC)
        m = np.nanmax(np.where(np.isfinite(ab), ab, np.nan), axis=1)
    if valid is not None:
        m = np.where(valid, m, np.nan)
    m = m[np.isfinite(m)]
    d = dict(label=label, n_valid=int(m.size), n_gt_030=int((m > MOD).sum()),
             n_gt_045=int((m > STRONG).sum()), max_abs=round(float(m.max()), 4),
             median_max=round(float(np.median(m)), 4))
    print('  %-46s n=%4d  >0.30 %4d  >0.45 %4d  max %.3f'
          % (label, d['n_valid'], d['n_gt_030'], d['n_gt_045'], d['max_abs']))
    return d


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    mets = list(pd.read_csv(METLIST)['metric'])
    need = set(mets + YCOLS + [WCOL, 'fips'])
    df = pd.read_csv(DATA, usecols=lambda c: c in need, low_memory=False)
    df['fips5'] = df['fips'].astype(str).str.zfill(5)
    mets = [m for m in mets if m in df.columns]

    X = df[mets].apply(pd.to_numeric, errors='coerce').values.astype(np.float64)
    Y = df[YCOLS].values.astype(np.float64)
    w = df[WCOL].values.astype(np.float64)
    X[~np.isfinite(X)] = np.nan
    Y[~np.isfinite(Y)] = np.nan
    fips = df['fips5'].values
    ok = np.isfinite(w) & (w > 0)
    X, Y, w, fips = X[ok], Y[ok], w[ok], fips[ok]
    print('counties %d   predictors %d' % X.shape)

    # ---- which cells were filled, reconstructed from the raw AHRF release ----
    hdr = pd.read_csv(RAW, nrows=0)
    fcol = [c for c in hdr.columns if c.lower() == 'fips'][0]
    raw = pd.read_csv(RAW, usecols=[fcol] + mets, dtype={fcol: str}, low_memory=False)
    raw[fcol] = raw[fcol].str.zfill(5)
    raw = raw.drop_duplicates(subset=fcol).set_index(fcol).reindex(fips)
    RAWNUM = raw[mets].apply(pd.to_numeric, errors='coerce').values.astype(np.float64)
    FILLED = ~np.isfinite(RAWNUM)
    per_var = FILLED.sum(axis=0)
    print('filled cells %d of %d (%.3f%%) in %d of %d variables'
          % (FILLED.sum(), FILLED.size, 100 * FILLED.sum() / FILLED.size,
             (per_var > 0).sum(), len(mets)))

    # A suppressed vital-statistics cell is identifiable: the variable's own
    # observed minimum is exactly 10, the AHRF withholding threshold.
    with np.errstate(all='ignore'):
        vmin = np.nanmin(np.where(np.isfinite(RAWNUM), RAWNUM, np.nan), axis=0)
    suppressed_var = (per_var > 0) & np.isclose(vmin, 10.0)
    print('variables whose blanks are small-count suppression (observed min = 10): %d'
          % suppressed_var.sum())

    results = []

    # ---------------- 0. production, validated ----------------
    print('\n0. production as published')
    CC0 = cc_block(X, Y, w)
    prod = pd.read_csv(PROD).set_index('metric').loc[mets, YCOLS].values
    print('  max |difference| vs %s: %.2e' % (PROD, np.nanmax(np.abs(CC0 - prod))))
    results.append(summary(CC0, 'production'))

    # ---------------- 1. drop the two zero-baseline counties ----------------
    print('\n1. Kalawao and Loving dropped from every year')
    keep = ~np.isin(fips, ZERO_BASELINE)
    print('  counties dropped: %d  (weight share %.2e)'
          % ((~keep).sum(), w[~keep].sum() / w.sum()))
    results.append(summary(cc_block(X[keep], Y[keep], w[keep]),
                           'zero-baseline counties dropped'))

    # ---------------- 2. suppressed predictor cells set to either end ----------
    for val, name in [(0.0, 'suppressed cells set to 0'),
                      (9.0, 'suppressed cells set to 9')]:
        print('\n2. %s' % name)
        Xs = X.copy()
        mask = FILLED & suppressed_var[None, :]
        Xs[mask] = val
        print('  cells changed: %d in %d variables' % (mask.sum(), suppressed_var.sum()))
        results.append(summary(cc_block(Xs, Y, w), name))

    # ---------------- 3. every filled-in cell left missing ----------------
    # This is the decisive test of the mean fill. Leaving only the suppression
    # variables missing, as an earlier version did, misses the cells that matter:
    # single filled cells in very small counties, where a filled-in count divided
    # by a tiny population gives an extreme per-capita value.
    covered = ((~FILLED) * w[:, None]).sum(axis=0) / w.sum() >= COVERAGE
    print('\n3. every filled-in cell left missing; variables need real data for '
          '%.0f%% of the weight: %d of %d kept' % (100 * COVERAGE, covered.sum(), len(mets)))
    Xm = X.copy()
    Xm[FILLED] = np.nan
    results.append(summary(cc_block(Xm, Y, w), 'all filled-in cells left missing',
                           valid=covered))
    results.append(summary(cc_block(Xm[keep], Y[keep], w[keep]),
                           'all filled cells missing, Kalawao and Loving dropped',
                           valid=covered))

    # ---------------- 4. only variables with no filled cell ----------------
    print('\n4. restricted to variables with no filled cell')
    novar = per_var == 0
    print('  variables kept: %d of %d' % (novar.sum(), len(mets)))
    results.append(summary(cc_block(X[:, novar], Y, w),
                           'complete variables only'))

    # ---------------- Kalawao: through which cells does it act? ----------------
    k = int(np.flatnonzero(fips == KALAWAO)[0])
    wn = w / w.sum()
    mu = np.nansum(wn[:, None] * X, axis=0)
    con = wn[:, None] * (X - mu) ** 2
    tot = np.nansum(con, axis=0)
    shk = con[k] / np.where(tot > 0, tot, np.nan)
    with np.errstate(all='ignore'):
        holds_max = X[k] >= np.nanmax(X, axis=0) - 1e-9
    kf = FILLED[k]
    print('\nKalawao County (85 residents)')
    print('  variables where its cell was filled in              : %d' % kf.sum())
    print('  variables where it holds the maximum                : %d, of which filled in %d'
          % (holds_max.sum(), (holds_max & kf).sum()))
    print('  variables where it supplies >50%% of weighted variance: %d, of which filled in %d'
          % ((shk > 0.5).sum(), ((shk > 0.5) & kf).sum()))
    print('  variables where it supplies >90%% of weighted variance: %d, of which filled in %d'
          % ((shk > 0.9).sum(), ((shk > 0.9) & kf).sum()))

    # ---------------- does any reported result rest on a filled cell? -------
    print('\nimputation load among the variables that reach each threshold')
    m0 = np.nanmax(np.abs(CC0), axis=1)
    frac = 100.0 * per_var / X.shape[0]
    for lab, sel in [('all valid', np.isfinite(m0)),
                     ('|CC| > 0.30', m0 > MOD), ('|CC| > 0.45', m0 > STRONG)]:
        f = frac[sel]
        print('  %-12s n=%4d   filled-cell fraction: max %.2f%%  median %.2f%%  '
              'variables over 5%% filled: %d'
              % (lab, sel.sum(), f.max(), np.median(f), int((f > 5).sum())))

    tab = pd.DataFrame(results)
    tab.to_csv(os.path.join(OUTDIR, 'sensitivity_summary.csv'), index=False)
    pd.DataFrame({'metric': mets, 'n_filled': per_var,
                  'pct_filled': frac, 'is_suppression': suppressed_var,
                  'max_abs_cc': m0}).to_csv(
        os.path.join(OUTDIR, 'per_variable_imputation.csv'), index=False)
    with open(os.path.join(OUTDIR, 'sensitivity_summary.json'), 'w') as fh:
        json.dump(results, fh, indent=2)
    print('\nwrote %s/' % OUTDIR)


if __name__ == '__main__':
    main()
