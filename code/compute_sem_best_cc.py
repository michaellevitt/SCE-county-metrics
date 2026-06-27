#!/usr/bin/env python3
"""compute_sem_best_cc.py
Add best_cc per SEM cluster to ward_sem_reps.csv using the CC file.
Called at Step 03b after CC file is available.

Usage (single line):
  python3 code/compute_sem_best_cc.py --sem-metrics ward_sem_2745/ward_sem_metrics.csv --cc-file metric_x_death_cc_0.0_25.1.csv --reps ward_sem_2745/ward_sem_reps.csv
"""
import argparse, os, sys
import numpy as np
import pandas as pd

def _tee(path):
    try:
        msg = 'Saved ' + os.path.relpath(path)
    except ValueError:
        msg = 'Saved ' + path
    print(msg)
    print(msg, file=sys.stderr, flush=True)

def main():
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sem-metrics', required=True,
                   help='ward_sem_metrics.csv')
    p.add_argument('--cc-file',     required=True,
                   help='metric_x_death_cc_*.csv')
    p.add_argument('--reps',        required=True,
                   help='ward_sem_reps.csv to update')
    args = p.parse_args()

    print(f'Loading {args.sem_metrics}...')
    sem = pd.read_csv(args.sem_metrics)
    cl_col = next(c for c in sem.columns if c in ('cluster_id','semantic_cluster_id'))

    print(f'Loading {args.cc_file}...')
    cc = pd.read_csv(args.cc_file, index_col='metric')
    asedx = [c for c in cc.columns
              if c.startswith('asedx_p_') and 'GE65' not in c and 'LT65' not in c]

    best_cc_map = {}
    for cid, grp in sem.groupby(cl_col):
        members = [m for m in grp['metric'] if m in cc.index]
        if members and asedx:
            sub = cc.loc[members, asedx].apply(pd.to_numeric, errors='coerce')
            abs_max = sub.abs().max(axis=1)
            best_m  = abs_max.idxmax()
            best_col = sub.loc[best_m].abs().idxmax()
            best_cc_map[int(cid)] = round(float(sub.loc[best_m, best_col]), 4)
        else:
            best_cc_map[int(cid)] = float('nan')

    reps = pd.read_csv(args.reps)
    id_col = next(c for c in reps.columns
                  if c in ('sem100','cluster_id','semantic_cluster_id'))
    reps['best_cc'] = reps[id_col].astype(int).map(best_cc_map)
    reps.to_csv(args.reps, index=False)
    _tee(args.reps)
    print(f'Updated {len(reps)} cluster best_cc values.')

if __name__ == '__main__':
    main()
