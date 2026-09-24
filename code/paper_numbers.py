#!/usr/bin/env python3
"""
paper_numbers.py

Every correlation-derived number the manuscript reports, computed from one
metric x death correlation file with the definitions stated in the captions.

Validate by running on the committed file, which must reproduce the published
numbers; then run on a regenerated file to get the new ones.

Usage:
    python3 code/paper_numbers.py --cc full_w1.0/metric_x_death_cc_1.0_0.csv --out numbers.json
"""
import argparse
import json

import numpy as np
import pandas as pd

METLIST = 'ward_sem_clean2_k120/ward_sem_metrics.csv'
ASSIGN = 'ward_sem_clean2_k120/sem_sc_assignments.csv'
SCNAMES = 'ward_sem_clean2_k120/sem_sc_names.csv'
YEARS = [2020, 2021, 2022, 2023, 2024]
MOD, STRONG = 0.30, 0.45
SOCIO_SC = [1, 2, 3, 5, 8]       # socioeconomic and demographic family


def per_variable(cc, suffix=''):
    """Signed CC, |CC| and year at the maximum |CC| over 2020-2024."""
    cols = [f'asedx_p_{y}{suffix}' for y in YEARS]
    V = cc[cols].values.astype(float)
    ab = np.abs(V)
    ok = np.isfinite(ab).any(axis=1)
    with np.errstate(all='ignore'):
        idx = np.nanargmax(np.where(np.isfinite(ab), ab, -1), axis=1)
    r = np.arange(len(cc))
    return pd.DataFrame({
        'metric': cc['metric'].values,
        'maxabs': np.where(ok, ab[r, idx], np.nan),
        'signed': np.where(ok, V[r, idx], np.nan),
        'year': np.where(ok, np.array(YEARS)[idx], 0),
    }), (ab > MOD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cc', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    meta = pd.read_csv(METLIST)
    asg = pd.read_csv(ASSIGN)
    names = pd.read_csv(SCNAMES)
    meta = meta.merge(asg[['sem100', 'sc_id']], left_on='semantic_cluster_id',
                      right_on='sem100', how='left')
    cc = pd.read_csv(a.cc)
    cc = cc[cc['metric'].isin(set(meta['metric']))].reset_index(drop=True)

    out = {}
    pv, above = per_variable(cc)
    d = meta.merge(pv, on='metric', how='left')
    v = d[np.isfinite(d.maxabs)]
    n = len(v)
    out['n_screened'] = int(len(meta))
    out['n_valid'] = int(n)
    out['n_gt030'] = int((v.maxabs > MOD).sum())
    out['n_gt045'] = int((v.maxabs > STRONG).sum())
    out['n_moderate_band'] = out['n_gt030'] - out['n_gt045']
    out['pct_gt030'] = round(100 * out['n_gt030'] / n, 1)
    out['pct_gt045'] = round(100 * out['n_gt045'] / n, 1)
    out['max_abs'] = round(float(v.maxabs.max()), 3)
    out['dist'] = dict(median=round(float(v.maxabs.median()), 3),
                       mean=round(float(v.maxabs.mean()), 3),
                       p90=round(float(v.maxabs.quantile(.90)), 3),
                       p95=round(float(v.maxabs.quantile(.95)), 3))
    per_year = {str(y): int(above[:, k].sum()) for k, y in enumerate(YEARS)}
    out['per_year_gt030'] = per_year
    out['per_year_pct'] = {y: round(100 * c / n, 1) for y, c in per_year.items()}

    # clusters spanned
    s30 = v[v.maxabs > MOD]
    s45 = v[v.maxabs > STRONG]
    out['span'] = dict(clusters_030=int(s30.semantic_cluster_id.nunique()),
                       sc_030=int(s30.sc_id.nunique()),
                       clusters_045=int(s45.semantic_cluster_id.nunique()),
                       sc_045=int(s45.sc_id.nunique()))

    # family contrast
    soc = v[v.sc_id.isin(SOCIO_SC)]
    hs = v[~v.sc_id.isin(SOCIO_SC)]
    out['family'] = dict(socio_pct=round(100 * (soc.maxabs > MOD).mean(), 1),
                         health_pct=round(100 * (hs.maxabs > MOD).mean(), 1),
                         socio_n=int(len(soc)), health_n=int(len(hs)),
                         strong_in_socio=int((soc.maxabs > STRONG).sum()),
                         moderate_band_in_socio=int(((soc.maxabs > MOD) & (soc.maxabs <= STRONG)).sum()),
                         moderate_band_total=out['n_moderate_band'])

    # Table 1
    rows = []
    nm = dict(zip(names.sc_id, names.sc_name))
    for sc, g in v.groupby('sc_id'):
        top = g.loc[g.maxabs.idxmax()]
        rows.append(dict(sc_id=int(sc), sc_name=nm.get(sc, ''), total=int(len(g)),
                         moderate=int(((g.maxabs > MOD) & (g.maxabs <= STRONG)).sum()),
                         strong=int((g.maxabs > STRONG).sum()),
                         pct030=round(100 * (g.maxabs > MOD).mean(), 1),
                         mean_abs=round(float(g.maxabs.mean()), 3),
                         top_metric=top.metric, top_explain=top.explain,
                         top_cc=round(float(top.signed), 2), top_year=int(top.year)))
    t1 = pd.DataFrame(rows).sort_values('pct030', ascending=False)
    out['table1'] = t1.to_dict('records')

    # strongest overall, and within age strata
    def topk(dd, k=3):
        dd = dd[np.isfinite(dd.maxabs)].nlargest(k, 'maxabs')
        return [dict(metric=r.metric, explain=r.explain, cc=round(float(r.signed), 2),
                     year=int(r.year), sc=int(r.sc_id)) for r in dd.itertuples()]
    out['top_all'] = topk(d, 10)
    for suf, lab in [('_GE65', 'ge65'), ('_LT65', 'lt65')]:
        pvs, ab = per_variable(cc, suf)
        ds = meta.merge(pvs, on='metric', how='left')
        vs = ds[np.isfinite(ds.maxabs)]
        out[f'top_{lab}'] = topk(ds, 6)
        out[f'{lab}_gt030'] = int((vs.maxabs > MOD).sum())
        out[f'{lab}_gt045'] = int((vs.maxabs > STRONG).sum())
        out[f'{lab}_max'] = round(float(vs.maxabs.max()), 3)
        out[f'{lab}_per_year'] = {str(y): int(ab[:, j].sum()) for j, y in enumerate(YEARS)}

    out['r2_max'] = round(out['max_abs'] ** 2, 2)
    json.dump(out, open(a.out, 'w'), indent=1, default=str)
    print(json.dumps({k: out[k] for k in ['n_valid', 'n_gt030', 'n_gt045', 'pct_gt030',
                                          'pct_gt045', 'max_abs', 'dist', 'per_year_gt030',
                                          'per_year_pct', 'span', 'family']}, indent=1))
    print(t1[['sc_id', 'total', 'moderate', 'strong', 'pct030', 'mean_abs', 'top_cc',
              'top_year', 'top_metric']].to_string(index=False))


if __name__ == '__main__':
    main()
