#!/usr/bin/env python3
"""
paper_numbers2.py

Tables S7, S8, S10 and S13, which had no committed generator, computed from the
definitions in their captions. Run inside a pipeline tree after the Pearson,
Spearman and alternative-weight correlation files exist.

Usage:
    python3 code/paper_numbers2.py --out logs/numbers2.json
"""
import argparse
import json

import numpy as np
import pandas as pd

METLIST = 'ward_sem_clean2_k120/ward_sem_metrics.csv'
ASSIGN = 'ward_sem_clean2_k120/sem_sc_assignments.csv'
DATA = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
PEARSON = 'full_w1.0/metric_x_death_cc_1.0_0.csv'
SPEARMAN = 'full_w1.0/metric_x_death_spearman_1.0_0.csv'
WEIGHTS = 'excl/weights/metric_x_death_cc_{p}_0.csv'
YEARS = [2020, 2021, 2022, 2023, 2024]
YC = [f'asedx_p_{y}' for y in YEARS]
MOD, STRONG = 0.30, 0.45


def maxcc(path, mets):
    cc = pd.read_csv(path)
    cc = cc[cc['metric'].isin(mets)].set_index('metric').reindex(mets)
    V = cc[YC].values.astype(float)
    ab = np.abs(V)
    ok = np.isfinite(ab).any(axis=1)
    with np.errstate(all='ignore'):
        idx = np.nanargmax(np.where(np.isfinite(ab), ab, -1), axis=1)
    r = np.arange(len(cc))
    return pd.DataFrame({'maxabs': np.where(ok, ab[r, idx], np.nan),
                         'signed': np.where(ok, V[r, idx], np.nan),
                         'year': np.where(ok, np.array(YEARS)[idx], 0)}, index=mets), V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    meta = pd.read_csv(METLIST).merge(pd.read_csv(ASSIGN)[['sem100', 'sc_id']],
                                      left_on='semantic_cluster_id', right_on='sem100')
    mets = list(meta.metric)
    sc = dict(zip(meta.metric, meta.sc_id))
    ex = dict(zip(meta.metric, meta.explain))
    out = {}

    # ---- Table S7: weighting ----
    df = pd.read_csv(DATA, usecols=['population_2019'], low_memory=False)
    pop = df['population_2019'].values.astype(float)
    pop = pop[np.isfinite(pop) & (pop > 0)]
    s7 = []
    for p in ['0.0', '0.5', '0.75', '1.0']:
        m, _ = maxcc(WEIGHTS.format(p=p), mets)
        v = m.maxabs.dropna()
        w = pop ** float(p)
        s7.append(dict(p=p, n_eff=round(float(w.sum() ** 2 / (w * w).sum()), 1),
                       pct030=round(100 * (v > MOD).mean(), 1),
                       pct045=round(100 * (v > STRONG).mean(), 1),
                       median=round(float(v.median()), 3), max=round(float(v.max()), 3),
                       n_valid=int(len(v))))
    out['table_s7'] = s7

    # ---- Table S8 and S13: Pearson against Spearman ----
    P, _ = maxcc(PEARSON, mets)
    S, SV = maxcc(SPEARMAN, mets)
    s8 = []
    for k in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        ids = [x for x in mets if sc[x] == k]
        pp = P.loc[ids].maxabs.dropna()
        ss = S.loc[ids].maxabs.dropna()
        s8.append(dict(sc=k, n=int(len(pp)),
                       pct_P=round(100 * (pp > MOD).mean(), 1), pct_S=round(100 * (ss > MOD).mean(), 1),
                       strong_P=int((pp > STRONG).sum()), strong_S=int((ss > STRONG).sum()),
                       max_P=round(float(pp.max()), 2), max_S=round(float(ss.max()), 2)))
    out['table_s8'] = s8
    socio = [1, 2, 3, 5, 8]
    out['s8_strong_S_total'] = int(sum(r['strong_S'] for r in s8))
    out['s8_strong_S_socio'] = int(sum(r['strong_S'] for r in s8 if r['sc'] in socio))
    out['s8_strong_P_total'] = int(sum(r['strong_P'] for r in s8))
    out['s8_strong_P_health'] = int(sum(r['strong_P'] for r in s8 if r['sc'] not in socio))
    out['s8_strong_S_health_by_sc'] = {r['sc']: r['strong_S'] for r in s8
                                       if r['sc'] not in socio and r['strong_S']}

    top = P.maxabs.dropna().sort_values(ascending=False).head(20).index
    yi = {y: i for i, y in enumerate(YEARS)}
    s13 = []
    for x in top:
        s_same_year = SV[mets.index(x), yi[int(P.loc[x, 'year'])]]
        s13.append(dict(metric=x, explain=ex[x], sc=int(sc[x]), year=int(P.loc[x, 'year']),
                        pearson=round(float(P.loc[x, 'signed']), 2),
                        spearman_same_year=round(float(s_same_year), 2),
                        spearman_max=round(float(S.loc[x, 'signed']), 2)))
    out['table_s13'] = s13
    out['s13_sign_agrees'] = int(sum(np.sign(r['pearson']) == np.sign(r['spearman_same_year']) for r in s13))
    out['s13_spearman_larger'] = int(sum(abs(r['spearman_same_year']) > abs(r['pearson']) for r in s13))
    out['s13_scs'] = sorted({r['sc'] for r in s13})

    # ---- Table S10: the outcome itself ----
    d = pd.read_csv(DATA, usecols=YC + ['population_2019'], low_memory=False)
    s10 = []
    for y, c in zip(YEARS, YC):
        x = d[c].values.astype(float)
        wt = d['population_2019'].values.astype(float)
        m = np.isfinite(x) & np.isfinite(wt)
        x, wt = x[m], wt[m]
        wm = np.average(x, weights=wt)
        s10.append(dict(year=y, n=int(m.sum()), mean=round(float(x.mean()), 3),
                        wmean=round(float(wm), 3), median=round(float(np.median(x)), 3),
                        sd=round(float(x.std(ddof=1)), 3),
                        wsd=round(float(np.sqrt(np.average((x - wm) ** 2, weights=wt))), 3),
                        iqr=round(float(np.percentile(x, 75) - np.percentile(x, 25)), 3),
                        p5=round(float(np.percentile(x, 5)), 3),
                        p95=round(float(np.percentile(x, 95)), 3)))
    out['table_s10'] = s10

    json.dump(out, open(a.out, 'w'), indent=1)
    print('S7'); print(pd.DataFrame(s7).to_string(index=False))
    print('\nS8'); print(pd.DataFrame(s8).to_string(index=False))
    print('   strong under Spearman %d, of which socio %d; strong under Pearson %d, health %d; '
          'health strong under Spearman by SC %s' % (out['s8_strong_S_total'], out['s8_strong_S_socio'],
          out['s8_strong_P_total'], out['s8_strong_P_health'], out['s8_strong_S_health_by_sc']))
    print('\nS13'); print(pd.DataFrame(s13)[['sc', 'year', 'pearson', 'spearman_same_year',
                                              'spearman_max', 'explain']].to_string(index=False))
    print('   sign agrees %d/20, Spearman larger %d/20, super-clusters %s'
          % (out['s13_sign_agrees'], out['s13_spearman_larger'], out['s13_scs']))
    print('\nS10'); print(pd.DataFrame(s10).to_string(index=False))


if __name__ == '__main__':
    main()
