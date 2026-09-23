#!/usr/bin/env python3
"""
suppression_analysis_v1.py

Quantifies CDC WONDER small-count suppression in the county mortality outcome and
tests whether the headline correlations depend on reconstructed values.
Answers Frontiers Reviewer 1, major comment 8.

CDC WONDER suppresses any sub-national cell whose death count is 1-9, and returns
no row at all for a count of 0. Any county-year in this file carrying a count of
0-9 therefore could not have been read directly and must have been recovered.
That gives an exact lower bound on the reconstruction burden without needing the
upstream code.

Outputs counts, the affected county list, and a re-run of the whole 2,745-variable
screen with reconstruction-dependent counties removed.
"""
import json
import numpy as np
import pandas as pd

SRC     = 'data/raw/usa-county-result.10Feb26.csv'
DATA    = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
METLIST = 'ward_sem_clean2_k120/ward_sem_metrics.csv'
PROD    = 'full_w1.0/metric_x_death_cc_1.0_0.csv'
YEARS   = list(range(2020, 2025))
YCOLS   = [f'asedx_p_{y}' for y in YEARS]
BASE    = ['2017', '2018', '2019']
MOD, STRONG = 0.30, 0.45


def screen(X, Y, w):
    """Weighted Pearson CC, per-(variable, year) valid sets. Returns p x 5."""
    out = np.full((X.shape[1], Y.shape[1]), np.nan)
    for k in range(Y.shape[1]):
        yk = Y[:, k]
        ok = np.isfinite(yk) & np.isfinite(w) & (w > 0)
        Xo, yo, wo = X[ok], yk[ok], w[ok]
        good = np.isfinite(Xo)
        Xf = np.where(good, Xo, 0.0)
        wm = wo[:, None] * good
        W = wm.sum(axis=0)
        mx = (wm * Xf).sum(axis=0) / W
        vx = (wm * Xf ** 2).sum(axis=0) / W - mx ** 2
        my = (wm * yo[:, None]).sum(axis=0) / W
        vy = (wm * yo[:, None] ** 2).sum(axis=0) / W - my ** 2
        cov = (wm * Xf * yo[:, None]).sum(axis=0) / W - mx * my
        den = np.sqrt(np.maximum(vx, 0) * np.maximum(vy, 0))
        out[:, k] = np.where(den > 0, cov / den, np.nan)
    return out


def summarise(CC, label):
    m = np.nanmax(np.abs(CC), axis=1)
    m = m[np.isfinite(m)]
    return dict(label=label, n_valid=int(m.size), gt030=int((m > MOD).sum()),
                gt045=int((m > STRONG).sum()), max_absCC=round(float(m.max()), 4),
                median=round(float(np.median(m)), 4))


def main():
    # ---------- 1. how much was suppressed ----------
    d = pd.read_csv(SRC, dtype={'fips': str, 'year': str})
    d['deaths'] = pd.to_numeric(d.deaths, errors='coerce')
    single = d[d.year.isin([str(y) for y in range(2017, 2025)])]

    rep = {}
    print('=' * 78)
    print('1. SUPPRESSION BURDEN  (cells CDC WONDER would not release directly)')
    print('=' * 78)
    tot = len(single)
    z = int((single.deaths == 0).sum())
    s19 = int(((single.deaths >= 1) & (single.deaths <= 9)).sum())
    print(f'  county-year-agegroup cells, 2017-2024      : {tot:,}')
    print(f'  count = 0     (no row returned by WONDER)  : {z:,}  ({100*z/tot:.2f}%)')
    print(f'  count 1-9     (suppressed by WONDER)       : {s19:,}  ({100*s19/tot:.2f}%)')
    print(f'  total requiring reconstruction             : {z+s19:,}  ({100*(z+s19)/tot:.2f}%)')
    rep['cells_total'] = tot
    rep['cells_zero'] = z
    rep['cells_1_9'] = s19

    print('\n  by age group:')
    for g in ['all', '0-64', '65+']:
        s = single[single.age_group == g]
        n = int(((s.deaths >= 0) & (s.deaths <= 9)).sum())
        print(f'    {g:6s} {n:5,} of {len(s):,} cells  ({100*n/len(s):.2f}%)')

    a = single[single.age_group == 'all'].copy()
    print('\n  all-age series, county-years needing reconstruction, by year:')
    for y in [str(v) for v in range(2017, 2025)]:
        s = a[a.year == y]
        n = int((s.deaths <= 9).sum())
        print(f'    {y}: {n:3d} of {len(s):,}  ({100*n/len(s):.2f}%)')

    # ---------- 2. validation against national totals ----------
    print('\n' + '=' * 78)
    print('2. VALIDATION: county sums vs published NCHS national all-cause deaths')
    print('=' * 78)
    pub = {'2017': 2813503, '2018': 2839205, '2019': 2854838, '2020': 3383729,
           '2021': 3464231, '2022': 3279857, '2023': 3090964, '2024': 3072666}
    val = []
    for y, p in pub.items():
        s = int(a[a.year == y].deaths.sum())
        val.append(dict(year=y, county_sum=s, published=p, diff=s - p,
                        pct=round(100 * (s - p) / p, 4)))
        print(f'  {y}  county sum {s:>10,}   published {p:>10,}   diff {s-p:>6,}  ({100*(s-p)/p:+.3f}%)')
    rep['validation'] = val
    print('  NOTE: 2021, 2022, 2023 and 2024 verified against NCHS Data Briefs 456, 492,')
    print('  521 and 548. 2017-2020 not yet re-verified against the source publications.')

    # ---------- 3. which counties depend on a reconstructed value ----------
    piv = a.pivot(index='fips', columns='year', values='deaths')
    base_bad = (piv[BASE] <= 9).any(axis=1)            # baseline 2017-2019 affected
    out_bad = (piv[[str(y) for y in YEARS]] <= 9).any(axis=1)
    any_bad = base_bad | out_bad
    print('\n' + '=' * 78)
    print('3. COUNTIES WHOSE OUTCOME DEPENDS ON A RECONSTRUCTED VALUE')
    print('=' * 78)
    print(f'  baseline (2017-2019) affected           : {int(base_bad.sum()):3d} counties')
    print(f'  any outcome year (2020-2024) affected   : {int(out_bad.sum()):3d} counties')
    print(f'  either                                  : {int(any_bad.sum()):3d} counties '
          f'({100*any_bad.mean():.2f}% of 3,139)')
    affected = set(piv.index[any_bad])
    rep['counties_affected'] = int(any_bad.sum())

    # ---------- 4. sensitivity: re-run the screen without them ----------
    mets = list(pd.read_csv(METLIST)['metric'])
    need = set(mets + YCOLS + ['population_2019', 'fips'])
    df = pd.read_csv(DATA, usecols=lambda c: c in need, low_memory=False)
    mets = [m for m in mets if m in df.columns]
    df['fips'] = df['fips'].astype(str).str.zfill(5)
    X = df[mets].apply(pd.to_numeric, errors='coerce').values.astype(float)
    Y = df[YCOLS].values.astype(float)
    w = df['population_2019'].values.astype(float)
    X[~np.isfinite(X)] = np.nan
    Y[~np.isfinite(Y)] = np.nan

    print('\n' + '=' * 78)
    print('4. SENSITIVITY: the 2,745-variable screen with affected counties removed')
    print('=' * 78)
    prod = pd.read_csv(PROD).set_index('metric').loc[mets, YCOLS].values
    base = summarise(screen(X, Y, w), 'all 3,139 counties (as published)')
    print(f'  reproduction check, max |diff| vs production file: '
          f'{np.nanmax(np.abs(screen(X, Y, w) - prod)):.2e}')

    keep = ~df['fips'].isin(affected).values
    rows = [base,
            summarise(screen(X[keep], Y[keep], w[keep]),
                      f'excluding {int((~keep).sum())} reconstruction-dependent counties'),
            summarise(screen(X[df["fips"].isin(affected).values],
                             Y[df["fips"].isin(affected).values],
                             w[df["fips"].isin(affected).values]),
                      f'ONLY the {int((~keep).sum())} affected counties (n=50: unstable, context only)')]
    t = pd.DataFrame(rows)
    print()
    print(t.to_string(index=False))
    rep['sensitivity'] = rows

    wt = w[~keep].sum() / w.sum()
    print(f'\n  share of total analysis weight carried by affected counties: {100*wt:.4f}%')
    rep['weight_share_affected'] = float(wt)

    pd.Series(sorted(affected)).to_csv('suppression/affected_counties.csv',
                                       index=False, header=['fips'])
    with open('suppression/suppression_summary.json', 'w') as f:
        json.dump(rep, f, indent=2)
    t.to_csv('suppression/sensitivity_table.csv', index=False)
    print('\nSaved suppression/suppression_summary.json, sensitivity_table.csv, '
          'affected_counties.csv')


if __name__ == '__main__':
    main()
