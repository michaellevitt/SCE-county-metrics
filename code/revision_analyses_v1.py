#!/usr/bin/env python3
"""
revision_analyses_v1.py

Three of the four outstanding Frontiers revision analyses:
  A. super-cluster x data-year crosstab                    (Reviewer 1, major comment 4)
  B. sensitivity excluding predictors with data year 2020  (Reviewer 1, major comment 4)
  C. how many clusters the 472 variables span              (Reviewer 1, minor comment 11)

Data year is parsed from the explain string exactly as code/make_master_excel_v12.py does.
"""
import re, json
import numpy as np
import pandas as pd

WM   = 'ward_sem_clean2_k120/ward_sem_metrics.csv'      # metric -> cluster_id (k=120)
SA   = 'ward_sem_clean2_k120/sem_sc_assignments.csv'    # cluster -> super-cluster (current)
SL   = 'ward_sem_clean2_k120/sem100_labels.csv'         # cluster -> label
EXPL = 'data/BEN_MERGED_MEASURES_explain_extended_2745.csv'
CC   = 'full_w1.0/metric_x_death_cc_1.0_0.csv'
YCOLS = [f'asedx_p_{y}' for y in range(2020, 2025)]
MOD, STRONG = 0.30, 0.45


def get_year(expl):
    m = re.search(r'=(\d{4})', str(expl))
    if m:
        y = int(m.group(1))
        return y if 1960 <= y <= 2024 else np.nan
    return np.nan


def main():
    wm = pd.read_csv(WM)[['metric', 'cluster_id']]
    sa = pd.read_csv(SA)
    ex = pd.read_csv(EXPL)[['metric', 'explain']]
    cc = pd.read_csv(CC)

    d = wm.merge(sa, left_on='cluster_id', right_on='sem100', how='left')
    d = d.rename(columns={'cluster_id': 'cluster'})
    try:
        sl = pd.read_csv(SL)
        lc = [c for c in sl.columns if 'label' in c.lower()][0]
        kc = [c for c in sl.columns if c != lc][0]
        d = d.merge(sl[[kc, lc]].rename(columns={kc: 'cluster', lc: 'label'}),
                    on='cluster', how='left')
    except Exception:
        d['label'] = d['cluster'].astype(str)
    d = d.merge(ex, on='metric', how='left')
    d['data_year'] = d['explain'].apply(get_year)
    assert d.sc_id.notna().all() and len(d) == 2745
    d = d.merge(cc[['metric'] + YCOLS], on='metric', how='left')
    d['max_abs'] = d[YCOLS].abs().max(axis=1)
    d['has_cc'] = d['max_abs'].notna()
    print(f'variables {len(d)}   with a valid CC {int(d.has_cc.sum())}   '
          f'with a data year {int(d.data_year.notna().sum())}')

    # cross-check against Table S6 of the manuscript
    vc = d.data_year.value_counts().sort_index()
    print(f'\ncheck vs Table S6: variables with data year 2020 = {int(vc.get(2020, 0))} '
          f'(manuscript says 40)')
    print(f'                   median data year = {d.data_year.median():.0f} '
          f'(manuscript says 2018)')

    # ---------------- A. super-cluster x data-year ----------------
    print('\n' + '=' * 78)
    print('A. SUPER-CLUSTER x DATA-YEAR CROSSTAB')
    print('=' * 78)
    ct = pd.crosstab(d.sc_id, d.data_year.astype('Int64'), dropna=False)
    ct['Total'] = ct.sum(axis=1)
    names = d.drop_duplicates('sc_id').set_index('sc_id')['sc_name']
    ct.insert(0, 'Super-cluster', names)
    pd.set_option('display.width', 250)
    print(ct.to_string())
    ct.to_csv('revision_analyses/A_supercluster_x_datayear.csv')

    med = d.groupby(['sc_id']).agg(
        n=('metric', 'size'), median_year=('data_year', 'median'),
        min_year=('data_year', 'min'), max_year=('data_year', 'max'),
        pct_2019_or_later=('data_year', lambda s: 100 * (s >= 2019).mean()))
    med.insert(0, 'Super-cluster', names)
    print('\nsummary by super-cluster:')
    print(med.round(1).to_string())
    med.to_csv('revision_analyses/A_supercluster_year_summary.csv')

    # ---------------- B. drop the 40 variables dated 2020 ----------------
    print('\n' + '=' * 78)
    print('B. SENSITIVITY: EXCLUDING PREDICTORS WITH DATA YEAR 2020')
    print('=' * 78)
    y2020 = d[d.data_year == 2020]
    print(f'  variables dated 2020: {len(y2020)}   with a valid CC: {int(y2020.has_cc.sum())}')
    print(f'  their max |CC|: max {y2020.max_abs.max():.3f}, '
          f'median {y2020.max_abs.median():.3f}, '
          f'number reaching 0.30: {int((y2020.max_abs > MOD).sum())}')
    print('\n  the 2020-dated variables reaching |CC| > 0.30:')
    top = y2020[y2020.max_abs > MOD].sort_values('max_abs', ascending=False)
    for _, r in top.iterrows():
        print(f'    SC{int(r.sc_id):<3} {r.metric:<10} {str(r.explain)[:58]:<58} {r.max_abs:.3f}')

    valid = d[d.has_cc]
    keep = valid[valid.data_year != 2020]
    rows = []
    for lab_, s in [('all 2,745 variables (as published)', valid),
                    (f'excluding the {len(y2020)} variables dated 2020', keep)]:
        rows.append(dict(analysis=lab_, n=len(s), gt030=int((s.max_abs > MOD).sum()),
                         pct030=round(100 * (s.max_abs > MOD).mean(), 2),
                         gt045=int((s.max_abs > STRONG).sum()),
                         max_absCC=round(s.max_abs.max(), 4)))
    tb = pd.DataFrame(rows)
    print()
    print(tb.to_string(index=False))
    tb.to_csv('revision_analyses/B_drop2020_sensitivity.csv', index=False)

    # ---------------- C. how many clusters do the 472 span ----------------
    print('\n' + '=' * 78)
    print('C. HOW MANY CLUSTERS THE 472 VARIABLES SPAN')
    print('=' * 78)
    sel = valid[valid.max_abs > MOD]
    strong = valid[valid.max_abs > STRONG]
    print(f'  variables with max |CC| > 0.30 : {len(sel)}')
    print(f'    distinct semantic clusters (of 120) : {sel.cluster.nunique()}')
    print(f'    distinct super-clusters (of 11)     : {sel.sc_id.nunique()}')
    print(f'  variables with max |CC| > 0.45 : {len(strong)}')
    print(f'    distinct semantic clusters (of 120) : {strong.cluster.nunique()}')
    print(f'    distinct super-clusters (of 11)     : {strong.sc_id.nunique()}')

    per = sel.groupby('cluster').size().sort_values(ascending=False)
    print(f'\n  concentration: the 472 fall into {len(per)} clusters; '
          f'the largest holds {per.iloc[0]}, '
          f'the top 10 hold {per.head(10).sum()} ({100*per.head(10).sum()/len(sel):.0f}%)')
    print(f'  median variables per represented cluster: {per.median():.0f}')
    lab_map = d.drop_duplicates('cluster').set_index('cluster')['label']
    print('\n  the 10 clusters contributing most of the 472:')
    for c, n in per.head(10).items():
        print(f'    {n:3d}  SC{int(sel[sel.cluster==c].sc_id.iloc[0]):<3} {str(lab_map.get(c))[:60]}')
    out = per.rename('n_above_0.30').to_frame()
    out['cluster_label'] = [lab_map.get(c) for c in out.index]
    out['sc_id'] = [int(sel[sel.cluster == c].sc_id.iloc[0]) for c in out.index]
    out.to_csv('revision_analyses/C_clusters_among_472.csv')

    json.dump(dict(
        n_variables=len(d), n_valid_cc=int(d.has_cc.sum()),
        n_year_2020=len(y2020), median_data_year=float(d.data_year.median()),
        drop2020=rows,
        clusters_among_472=dict(n_variables=len(sel), n_clusters=int(sel.cluster.nunique()),
                                n_superclusters=int(sel.sc_id.nunique())),
        clusters_among_77=dict(n_variables=len(strong), n_clusters=int(strong.cluster.nunique()),
                               n_superclusters=int(strong.sc_id.nunique())),
    ), open('revision_analyses/ABC_summary.json', 'w'), indent=2)
    print('\nSaved revision_analyses/A_*, B_*, C_*, ABC_summary.json')


if __name__ == '__main__':
    main()
