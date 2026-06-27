import sys
# plot_full_heatmap.py
# Plot full NxN CC heatmap for all metrics ordered by cluster then dendrogram leaf order.
# Thin black lines at 100 cluster boundaries, thick lines at super-cluster boundaries.
#
# Usage:
#   python3 plot_full_heatmap.py \
#     --cc-matrix        full_cc_ase0_p=0.0_25.1.csv \
#     --assignments      ling_medoid_out/xde100_assignments_ling.csv \
#     --z-med            ling_medoid_out/Z_med_ling.npy \
#     --medoid-list      ling_medoid_out/medoid_list_ling.json \
#     --reps-csv         ling_medoid_out/xde100_reps_ling.csv \
#     --nsuper           12 \
#     --out              ling_medoid_out/full_heatmap.png

import os
import argparse
import json
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster

def _tee(path):
    _p = str(path)
    _dir = os.path.dirname(os.path.abspath(_p))
    _fname = os.path.basename(_p)
    msg = 'Saved ' + _fname + '  [' + _dir + ']'
    print(msg)
    print(msg, file=sys.stderr, flush=True)



def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='Full NxN CC heatmap ordered by SEM cluster.')
    parser.add_argument('--cc-matrix',   required=True)
    parser.add_argument('--assignments', required=True,
                        help='ward{k}_assignments_ling.csv')
    parser.add_argument('--z-med',       required=True,
                        help='Z_med_ling.npy')
    parser.add_argument('--medoid-list', required=True,
                        help='medoid_list_ling.json')
    parser.add_argument('--reps-csv',    required=True,
                        help='ward{k}_reps_ling.csv')
    parser.add_argument('--labels-csv', default=None,
                        help='xde100_labels_ling_v1.csv; provides linguistic label per cluster')
    parser.add_argument('--sem-labels', default=None,
                        help='sem100_labels.csv -- SEM cluster labels')
    parser.add_argument('--no-super-lines', action='store_true',
                        help='Omit thick super-cluster boundary lines on heatmap')
    parser.add_argument('--sc-assignments', default=None,
                        help='sem_sc_assignments.csv')
    parser.add_argument('--nsuper',  type=int, default=12,
                        help='Number of super-clusters (default 12)')
    parser.add_argument('--dpi',     type=int, default=150)
    parser.add_argument('--out',     default='full_heatmap.png')
    args = parser.parse_args()

    # ---- Load linkage + medoid list ----
    log("Loading linkage and medoid list...")
    Z_med = np.load(args.z_med)
    with open(args.medoid_list) as f:
        medoid_list = json.load(f)
    n = len(medoid_list)

    # ---- Reps: medoid -> XDE cluster ID ----
    reps     = pd.read_csv(args.reps_csv)
    ward_col = [c for c in reps.columns if c.startswith('Ward')][0]
    medoid_to_ward = dict(zip(reps['medoid'], reps[ward_col]))

    # ---- Super-cluster labels ----
    # Always use dendrogram cut for SC boundaries (guarantees contiguous blocks)
    super_labels = fcluster(Z_med, t=args.nsuper, criterion='maxclust')
    log(f'  Using k={args.nsuper} dendrogram cut for SC boundaries')

    # ---- Dendrogram leaf order ----
    from scipy.cluster.hierarchy import dendrogram
    log("Computing dendrogram leaf order...")
    dn = dendrogram(Z_med, no_plot=True)
    leaf_order = dn['leaves']
    ward_leaf_order = [medoid_to_ward.get(medoid_list[i], 0) for i in leaf_order]
    super_leaf_order = [int(super_labels[i]) for i in leaf_order]

    # ---- Load assignments ----
    log("Loading metric assignments...")
    assign_df = pd.read_csv(args.assignments)
    ward_col_a = [c for c in assign_df.columns if c.startswith('Ward')][0]

    # Sort metrics by dendrogram cluster position
    ward_to_pos = {wid: pos for pos, wid in enumerate(ward_leaf_order)}
    assign_df['dend_pos'] = assign_df[ward_col_a].map(ward_to_pos)
    assign_df = assign_df.sort_values('dend_pos', ascending=True).reset_index(drop=True)
    metric_order   = assign_df['metric'].tolist()
    cluster_order  = assign_df[ward_col_a].tolist()
    log(f"  {len(metric_order)} metrics ordered (reversed)")

    # ---- Load full CC matrix ----
    log(f"Loading CC matrix from {args.cc_matrix} ...")
    full_cc_df = pd.read_csv(args.cc_matrix, index_col=0)

    # Remove death measure rows/cols
    non_death = [m for m in metric_order if m in full_cc_df.index
                 and not str(m).startswith('asedx_p_')]
    missing = [m for m in metric_order if m not in full_cc_df.index]
    if missing:
        log(f"  WARNING: {len(missing)} metrics not in CC matrix")

    # Build paired (metric, cluster) list in same order -- single pass
    paired = [(m, cluster_order[i])
              for i, m in enumerate(metric_order)
              if m in full_cc_df.index and not str(m).startswith('asedx_p_')]
    non_death     = [m for m, c in paired]
    avail_clusters = [c for m, c in paired]

    cc_sub = full_cc_df.loc[non_death, non_death].values.astype(float)
    np.fill_diagonal(cc_sub, 1.0)
    cc_sub = np.where(np.isfinite(cc_sub), cc_sub, 0.0)
    n_plot = len(non_death)
    log(f"  CC submatrix: {cc_sub.shape}")

    # ---- Compute boundary positions ----
    ward_to_super = {medoid_to_ward.get(medoid_list[i], 0): int(super_labels[i])
                     for i in range(n)}

    cluster_bounds = []
    super_bounds   = []
    prev_c = avail_clusters[0]
    prev_s = ward_to_super.get(prev_c, 0)
    for i in range(1, len(avail_clusters)):
        c = avail_clusters[i]
        s = ward_to_super.get(c, 0)
        if c != prev_c:
            cluster_bounds.append(i - 0.5)
        if s != prev_s:
            super_bounds.append(i - 0.5)
        prev_c, prev_s = c, s
    log(f"  {len(cluster_bounds)} cluster boundaries, {len(super_bounds)} super-cluster boundaries")

    # ---- Build cluster label map ----
    cluster_label_map = {int(r[ward_col]): f"W{int(r[ward_col])}" for _, r in reps.iterrows()}
    if args.labels_csv and os.path.exists(args.labels_csv):
        lbl_df = pd.read_csv(args.labels_csv)
        if 'metric' in lbl_df.columns and 'cluster_id' in lbl_df.columns:
            # SEM metrics file: map XDE Ward via medoid -> SEM cluster -> label
            sem_lbl = {}
            if args.sem_labels and os.path.exists(args.sem_labels):
                _sl = pd.read_csv(args.sem_labels)
                _sc = 'label_proposed_v2' if 'label_proposed_v2' in _sl.columns \
                      else 'label_proposed' if 'label_proposed' in _sl.columns \
                      else _sl.columns[-1]
                sem_lbl = dict(zip(_sl['cluster_id'].astype(int), _sl[_sc]))
            m2sem = dict(zip(lbl_df['metric'], lbl_df['cluster_id'].astype(int)))
            for _, r in reps.iterrows():
                wid = int(r[ward_col])
                sem_cid = m2sem.get(r['medoid'])
                if sem_cid is not None:
                    lbl = sem_lbl.get(sem_cid, f'SEM-{sem_cid}')
                    cluster_label_map[wid] = f"W{wid}: {lbl}"
            log(f"  Mapped {len(cluster_label_map)} XDE clusters to SEM labels")
        else:
            lbl_col = 'label_proposed_v2' if 'label_proposed_v2' in lbl_df.columns else 'label_proposed'
            for _, r in lbl_df.iterrows():
                cid = int(r['cluster_id'])
                cluster_label_map[cid] = f"W{cid}: {r[lbl_col]}"
            log(f"  Loaded {len(lbl_df)} labels")

    # ---- Plot ----
    log("Plotting heatmap...")
    side_in = max(14, min(28, n_plot / 100))
    fig, ax = plt.subplots(figsize=(side_in + 1.2, side_in), dpi=args.dpi)

    cmap = mcolors.LinearSegmentedColormap.from_list(
        'bwr_custom',
        [(0.0, '#2166AC'), (0.5, '#FFFFFF'), (1.0, '#B2182B')]
    )
    im = ax.imshow(cc_sub, aspect='equal', cmap=cmap,
                   vmin=-1.0, vmax=1.0, interpolation='none')

    # Thin cluster boundary lines
    for b in cluster_bounds:
        ax.axhline(b, color='black', lw=0.4, zorder=4, alpha=0.7)
        ax.axvline(b, color='black', lw=0.4, zorder=4, alpha=0.7)

    # Thick super-cluster boundary lines (optional)
    if not args.no_super_lines:
        for b in super_bounds:
            ax.axhline(b, color='black', lw=2.0, zorder=5)
            ax.axvline(b, color='black', lw=2.0, zorder=5)

    ax.set_xticks([])

    # Y-axis labels: one per 25 metrics, using linguistic_label of the metric
    # Load linguistic labels from extended explain if available, else use cluster position
    tick_positions = list(range(0, n_plot, 25))
    tick_labels = []
    for pos in tick_positions:
        m = non_death[pos]
        c = avail_clusters[pos]
        # Use cluster label from reps if available
        lbl = cluster_label_map.get(c, f'C{c}')
        tick_labels.append(lbl)

    ax.set_yticks(tick_positions)
    ax.set_yticklabels(tick_labels, fontsize=14)
    ax.yaxis.set_tick_params(pad=2, length=2)

    ax.set_xlabel(f'All metrics (n={n_plot}, cluster order)', fontsize=12)
    ax.set_ylabel(f'All metrics (n={n_plot}, cluster order)', fontsize=12)
    ax.set_title(
        f'Full metric CC matrix  |  n={n_plot}  |  100-cluster linguistic order\n'
        f'Thin lines = 100 cluster boundaries   '
        f'Thick lines = {args.nsuper} super-cluster boundaries',
        fontsize=12)

    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label('Correlation coefficient (CC)', fontsize=10)
    cb.ax.tick_params(labelsize=9)

    plt.tight_layout()
    fig.text(0.5, 0.995, os.path.basename(args.out), ha='center', va='top',
             fontsize=7, color='#888888', fontfamily='monospace',
             transform=fig.transFigure)
    fig.savefig(args.out, dpi=args.dpi, bbox_inches='tight', facecolor='white')
    _tee(args.out)
    try:
        _r_args_out = os.path.relpath(args.out)
    except ValueError:
        _r_args_out = args.out
    plt.close()
    log(f"Saved: {args.out}")
    log("Done.")


if __name__ == '__main__':
    main()
