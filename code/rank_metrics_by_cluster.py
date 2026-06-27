#!/usr/bin/env python3
"""
Rank the metrics within each SEM cluster by max|CC| over a year range (descending),
and emit:
  --out-ordered : every metric, with rank_in_cluster, max_abs_cc, centroid_distance
  --out-top     : one row per cluster (rank 1 = the highest-|CC| representative)

Both are ordered by super-cluster, then cluster, then within-cluster max|CC|.

Usage:
  python3 rank_metrics_by_cluster.py \
    --sem-metrics ward_sem_clean2_k120/ward_sem_metrics.csv \
    --death-cc    full_w1.0/metric_x_death_cc_1.0_0.csv \
    --sem100-labels ward_sem_clean2_k120/sem100_labels.csv \
    --sc-assignments ward_sem_clean2_k120/sem_sc_assignments.csv \
    --years 2020-2024 \
    --out-ordered ward_sem_clean2_k120/metrics_by_cluster_ordered_w1.0.tsv \
    --out-top     ward_sem_clean2_k120/top_metric_per_cluster_2020_2024_w1.0.tsv
"""
import argparse, numpy as np, pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sem-metrics', required=True)
    ap.add_argument('--death-cc',    required=True)
    ap.add_argument('--sem100-labels', required=True)
    ap.add_argument('--sc-assignments', required=True)
    ap.add_argument('--years', default='2020-2024', help='inclusive year range, e.g. 2020-2024')
    ap.add_argument('--out-ordered', required=True)
    ap.add_argument('--out-top', required=True)
    ap.add_argument('--out-top-csv', default=None,
                    help='optional comma-separated copy of the per-cluster top-metric table')
    a = ap.parse_args()

    y0, y1 = (int(x) for x in a.years.split('-'))
    ycols = [f'asedx_p_{y}' for y in range(y0, y1 + 1)]

    cc = pd.read_csv(a.death_cc, usecols=['metric'] + ycols)
    for c in ycols:
        cc[c] = pd.to_numeric(cc[c], errors='coerce')
    av = cc[ycols].abs()
    cc['max_abs_cc'] = av.max(axis=1).round(4)
    # signed CC and year at the max |CC| (skip metrics with no valid CC in range)
    by = pd.Series(pd.NA, index=cc.index, dtype='object')
    cb = pd.Series(np.nan, index=cc.index, dtype='float64')
    valid = av.notna().any(axis=1)
    if valid.any():
        bcol = av.loc[valid].idxmax(axis=1)
        by.loc[valid] = bcol.str.replace('asedx_p_', '', regex=False)
        cb.loc[valid] = [cc.at[i, col] for i, col in bcol.items()]
    cc['best_year'] = by
    cc['cc_at_best'] = cb.round(4)

    m = pd.read_csv(a.sem_metrics)[['metric', 'explain', 'semantic_cluster_id', 'centroid_distance']]
    m = m.rename(columns={'semantic_cluster_id': 'cluster'})
    m['explain'] = m['explain'].map(lambda s: str(s).split('=')[0].strip())
    m['centroid_distance'] = m['centroid_distance'].round(4)
    lab = pd.read_csv(a.sem100_labels)[['cluster_id', 'label_proposed']].rename(
        columns={'cluster_id': 'cluster', 'label_proposed': 'cluster_label'})
    sc = pd.read_csv(a.sc_assignments)[['sem100', 'sc_id', 'sc_name']].rename(columns={'sem100': 'cluster'})

    t = (m.merge(cc[['metric', 'max_abs_cc', 'best_year', 'cc_at_best']], on='metric', how='left')
           .merge(lab, on='cluster', how='left').merge(sc, on='cluster', how='left'))
    t = t.sort_values(['sc_id', 'cluster', 'max_abs_cc'], ascending=[True, True, False])
    t['rank_in_cluster'] = t.groupby('cluster').cumcount() + 1

    ordered = t[['sc_id', 'sc_name', 'cluster', 'cluster_label', 'rank_in_cluster',
                 'metric', 'explain', 'max_abs_cc', 'centroid_distance']]
    ordered.to_csv(a.out_ordered, sep='\t', index=False)

    top = (t[t['rank_in_cluster'] == 1]
           [['sc_id', 'sc_name', 'cluster', 'cluster_label', 'metric', 'explain',
             'cc_at_best', 'best_year', 'max_abs_cc']])
    top.to_csv(a.out_top, sep='\t', index=False)
    if a.out_top_csv:
        top.to_csv(a.out_top_csv, index=False)   # comma-separated (pandas quotes fields with commas)
    print(f'Wrote {a.out_ordered} ({len(ordered)} rows) and {a.out_top} ({len(top)} clusters)'
          + (f' + CSV {a.out_top_csv}' if a.out_top_csv else ''))

if __name__ == '__main__':
    main()
