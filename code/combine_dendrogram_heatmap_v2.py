import sys
import os
# combine_dendrogram_heatmap.py
# Combines a medoid dendrogram PNG and heatmap PNG side by side with matched
# Y-axis height, and draws super-cluster boundary lines on the heatmap.
#
# Requires the pre-computed files from precompute_medoid_linkage.py and
# plot_medoid_dendrogram.py PLUS the original Z_med.npy and medoid_list.json
# so we can recompute the leaf order and super-cluster assignments.
#
# Usage:
#   python3 combine_dendrogram_heatmap.py \
#     --z-med        cc_medoid_out/Z_med_cc.npy \
#     --medoid-list  cc_medoid_out/medoid_list_cc.json \
#     --reps-csv     cc_medoid_out/xde100_reps_cc.csv \
#     --cc-matrix    full_cc_ase0_p=0.0_25.1.csv \
#     --extended-explain BEN_MERGED_MEASURES_explain_extended.csv \
#     --death-cc     metric_x_death_cc_0_0_25_1.csv \
#     --nsuper       12 \
#     --linthresh    0.5 \
#     --out          combined_ling.png
#
# All arguments mirror plot_medoid_dendrogram.py so the same call works for
# both CC and linguistic outputs.

import argparse
import json
import time

import matplotlib

def _tee(path):
    _p = str(path)
    try:
        msg = 'Saved ' + os.path.relpath(_p)
    except ValueError:
        msg = 'Saved ' + _p
    print(msg)
    print(msg, file=sys.stderr, flush=True)

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, fcluster


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def clean_desc(desc, maxlen=55):
    if not isinstance(desc, str):
        return str(desc)
    if '=' in desc:
        desc = desc[:desc.index('=')]
    desc = desc.strip().rstrip('_').rstrip('-').strip()
    return desc[:maxlen] + '...' if len(desc) > maxlen else desc


def build_node_colors(Z, n, super_labels, palette):
    node_color = {}
    for i in range(n):
        node_color[i] = palette[(super_labels[i] - 1) % len(palette)]
    for step, row in enumerate(Z):
        node_id = n + step
        l, r = int(row[0]), int(row[1])
        lc = node_color.get(l, '#555555')
        rc = node_color.get(r, '#555555')
        node_color[node_id] = lc if lc == rc else '#555555'
    return node_color


PALETTE = [
    '#E41A1C', '#377EB8', '#4DAF4A', '#FF7F00', '#984EA3',
    '#A65628', '#F781BF', '#999999', '#1B9E77', '#D95F02',
    '#7570B3', '#E7298A',
]

def swivel_to_ward_order(Z, n, ward_ids):
    """
    Rotate dendrogram branches so leaves appear in ascending Ward ID order
    as much as possible, by swiveling each merge node so the subtree with
    the lower minimum Ward ID comes first (top).
    Returns a reordered copy of Z.
    """
    import copy
    Z2 = Z.copy()
    # For each node, compute the minimum Ward ID in its subtree
    min_ward = {}
    for i in range(n):
        min_ward[i] = ward_ids[i]
    for step in range(len(Z2)):
        node_id = n + step
        l, r = int(Z2[step, 0]), int(Z2[step, 1])
        lmin = min_ward.get(l, 0)
        rmin = min_ward.get(r, 0)
        # Swivel: put lower Ward ID subtree first (left = top in left orientation)
        if lmin > rmin:
            Z2[step, 0], Z2[step, 1] = Z2[step, 1], Z2[step, 0]
            lmin, rmin = rmin, lmin
        min_ward[node_id] = lmin
    return Z2

LP_ORDER = [
    'LP_asedx_p_2020',     'LP_asedx_p_2020_GE65', 'LP_asedx_p_2020_LT65',
    'LP_asedx_p_2021',     'LP_asedx_p_2021_GE65', 'LP_asedx_p_2021_LT65',
    'LP_asedx_p_2022',     'LP_asedx_p_2022_GE65', 'LP_asedx_p_2022_LT65',
    'LP_asedx_p_2023',     'LP_asedx_p_2023_GE65', 'LP_asedx_p_2023_LT65',
    'LP_asedx_p_2024',     'LP_asedx_p_2024_GE65', 'LP_asedx_p_2024_LT65',
]


def main():
    parser = argparse.ArgumentParser(
        description='Combined dendrogram + heatmap figure with matched Y-axis '
                    'and super-cluster boundary lines.')
    parser.add_argument('--z-med',           required=True)
    parser.add_argument('--medoid-list',     required=True)
    parser.add_argument('--reps-csv',        required=True)
    parser.add_argument('--cc-matrix',       required=True)
    parser.add_argument('--extended-explain',default=None)
    parser.add_argument('--death-cc',        required=True)
    parser.add_argument('--sig-mode', choices=['lp', 'cc'], default='cc',
                        help="Significance definition: 'cc' (|CC|>--cc-sig, default) or 'lp' (legacy)")
    parser.add_argument('--cc-sig', type=float, default=0.3, help='|CC| Significant threshold (cc mode)')
    parser.add_argument('--nsuper',  type=int,   default=12)
    parser.add_argument('--sc-assignments', default=None,
                        help='sem_sc_assignments.csv: Ward100->sc_id')
    parser.add_argument('--linthresh', type=float, default=0.5)
    parser.add_argument('--k400',    action='store_true',
                        help='Use domain/k400 label as primary text')
    parser.add_argument('--labels', default=None,
                        help='sem100_labels.csv -- SEM cluster labels (preferred over XDE labels)')
    parser.add_argument('--sem-labels', default=None,
                        help='sem100_labels.csv -- SEM cluster labels')
    parser.add_argument('--assignments', default=None,
                        help='ward{k}_assignments_ling.csv for full metric heatmap')
    parser.add_argument('--full-heatmap', action='store_true',
                        help='Plot full NxN metric heatmap instead of 100x100 medoid heatmap')
    parser.add_argument('--centroid-heatmap', action='store_true',
                        help='Plot 100x100 cluster centroid heatmap (mean CC within cluster pairs)')
    parser.add_argument('--cc-threshold', type=float, default=None,
                        help='Saturate the heatmap colour scale at +-this CC value: '
                             'CC <= -T full blue, 0 white, CC >= +T full red, smooth '
                             'ramp between (e.g. 0.5).')
    parser.add_argument('--out',     default='combined_figure.png')
    parser.add_argument('--dpi',     type=int, default=130)
    parser.add_argument('--invert-y', action='store_true',
                        help='Invert y-axis so dendrogram reads top-to-bottom in reverse leaf order')
    args = parser.parse_args()

    # ---- Load linkage + medoids ----
    log("Loading linkage and medoid list...")
    Z_med       = np.load(args.z_med)
    with open(args.medoid_list) as f:
        medoid_list = json.load(f)
    n = len(medoid_list)
    log(f"  {n} medoids")

    # ---- Load metadata ----
    log("Loading metadata...")
    explain      = {}
    k400_map     = {}
    domain_map   = {}
    ling_map     = {}
    if args.extended_explain:
        ext = pd.read_csv(args.extended_explain)
        explain    = dict(zip(ext['metric'], ext['explain'].fillna('')))
        k400_map   = dict(zip(ext['metric'], ext['k400_label'].fillna('')))
        if 'domain_label' in ext.columns:
            domain_map = dict(zip(ext['metric'], ext['domain_label'].fillna('')))
        if 'linguistic_label' in ext.columns:
            ling_map = dict(zip(ext['metric'], ext['linguistic_label'].fillna('')))
            log(f"  Loaded {sum(1 for v in ling_map.values() if v)} linguistic labels")

    reps     = pd.read_csv(args.reps_csv)
    ward_col = [c for c in reps.columns if c.startswith('Ward')][0]
    medoid_to_ward = dict(zip(reps['medoid'], reps[ward_col]))
    # Load XDE cluster labels (same source as plot_full_heatmap)
    ward_label_map = {}
    if args.labels and os.path.exists(args.labels):
        _metrics_df = pd.read_csv(args.labels)
        # Load SEM labels if provided separately
        _sem_lbl = {}
        if args.sem_labels and os.path.exists(args.sem_labels):
            _lbl_df  = pd.read_csv(args.sem_labels)
            _lbl_col = 'label_proposed_v2' if 'label_proposed_v2' in _lbl_df.columns \
                       else 'label_proposed' if 'label_proposed' in _lbl_df.columns \
                       else _lbl_df.columns[-1]
            _sem_lbl = dict(zip(_lbl_df['cluster_id'].astype(int), _lbl_df[_lbl_col]))
            log(f'  Loaded {len(_sem_lbl)} SEM labels from {args.sem_labels}')
        # Build XDE Ward -> SEM cluster label via medoid metric
        if 'cluster_id' in _metrics_df.columns and 'metric' in _metrics_df.columns \
                and reps is not None:
            _w_col = [c for c in reps.columns if c.startswith('Ward')][0]
            _m2sem = dict(zip(_metrics_df['metric'], _metrics_df['cluster_id'].astype(int)))
            for _, rr in reps.iterrows():
                wid      = int(rr[_w_col])
                medoid_m = rr['medoid']
                sem_cid  = _m2sem.get(medoid_m)
                if sem_cid is not None:
                    ward_label_map[wid] = _sem_lbl.get(sem_cid, f'SEM-{sem_cid}')
            log(f'  Built {len(ward_label_map)} XDE->SEM label mappings')
    ward_size      = dict(zip(reps[ward_col], reps['cluster_size']))
    best_cc_map    = dict(zip(reps['medoid'], reps['best_cc'])) \
                     if 'best_cc' in reps.columns else {}

    # ---- Death significance + max|CC| ----
    log("Loading death LP data...")
    death    = pd.read_csv(args.death_cc, index_col=0)
    lp_cols  = [c for c in LP_ORDER if c in death.columns]
    if args.sig_mode == 'cc':
        # |CC| bands over the pandemic CC columns (strip 'LP_' from LP_ORDER names)
        pan_cc = [c[3:] for c in lp_cols if c[3:] in death.columns]
        _ac = death[pan_cc].apply(pd.to_numeric, errors='coerce').abs()
        bit_count = (_ac > args.cc_sig).sum(axis=1).to_dict()
        sig_13    = (_ac > args.cc_sig).any(axis=1).to_dict()
    else:
        bit_count = death[lp_cols].apply(
            lambda r: sum(1 for c in lp_cols if r[c] <= -14), axis=1).to_dict()
        # LP significance flag per metric (any LP <= -13)
        sig_13 = death[lp_cols].apply(
            lambda r: any(r[c] <= -13 for c in lp_cols), axis=1).to_dict()

    # CC columns (non-LP)
    cc_cols = [c for c in death.columns
               if c.startswith('asedx_p_') and not c.startswith('LP_')]
    if cc_cols:
        cc_sub = death[cc_cols].apply(pd.to_numeric, errors='coerce')
        abs_cc = cc_sub.abs()
        best_col_idx = abs_cc.values.argmax(axis=1)
        max_signed_cc = {
            m: float(cc_sub.iloc[i, best_col_idx[i]])
            for i, m in enumerate(cc_sub.index)
        }
    else:
        max_signed_cc = {}
    log(f"  max|CC| loaded for {len(max_signed_cc)} metrics")

    # ---- CC matrix ----
    log(f"Loading CC matrix from {args.cc_matrix} ...")
    cc_df     = pd.read_csv(args.cc_matrix, index_col=0)
    med_in_cc = [m for m in medoid_list if m in cc_df.index]
    missing   = [m for m in medoid_list if m not in cc_df.index]
    if missing:
        log(f"  WARNING: {len(missing)} medoids missing from CC matrix")
    cc_sub = pd.DataFrame(0.0, index=medoid_list, columns=medoid_list)
    cc_sub.loc[med_in_cc, med_in_cc] = cc_df.loc[med_in_cc, med_in_cc].values
    cc_matrix = cc_sub.values.astype(float)
    np.fill_diagonal(cc_matrix, 1.0)
    log(f"  CC submatrix: {cc_matrix.shape}")

    # ---- Build labels ----
    labels = []
    for m in medoid_list:
        wid    = medoid_to_ward.get(m, '?')
        sz     = ward_size.get(wid, 1)
        prefix = f"W{wid}(n={sz})  "
        cc_val = best_cc_map.get(m, float('nan'))
        cc_str = f"  {cc_val:+.3f}" if np.isfinite(float(cc_val)) else ""
        # Priority: ward_label_map > linguistic_label > domain_label > explain text
        ward_lbl   = ward_label_map.get(int(wid), '') if wid != '?' else ''
        ling_lbl   = ling_map.get(m, '')
        domain_lbl = domain_map.get(m, '') or k400_map.get(m, '')
        if ward_lbl:
            primary = ward_lbl
        elif ling_lbl:
            primary = ling_lbl
        elif args.k400 and domain_lbl:
            primary = domain_lbl
        else:
            primary = clean_desc(explain.get(m, m))
        # Append max|CC| signed value
        mcc = max_signed_cc.get(m, float('nan'))
        mcc_str = f"  {mcc:+.2f}" if np.isfinite(float(mcc)) else "   n/a"
        label = f"{prefix}{primary}{mcc_str}"
        labels.append(label)

    # Z_plot = Z_med: no swivel -- dendrogram leaf order matches heatmap
    Z_plot = Z_med

    # ---- Super-cluster colours ----
    # Always use dendrogram cut for SC colouring (guarantees contiguous blocks)
    super_labels = fcluster(Z_med, t=args.nsuper, criterion='maxclust')
    log(f'  Using k={args.nsuper} dendrogram cut for SC assignments')
    node_color   = build_node_colors(Z_plot, n, super_labels, PALETTE)

    def link_color_func(link_id):
        return node_color.get(link_id, '#555555')

    # ---- Figure layout ----
    # Dendrogram width ~ 45% of total; heatmap ~ 42%; colorbar ~3%; gap ~10%
    LEAF_FONT   = 6.5 * 1.4
    LEG_FONT    = 8   * 1.4
    XLABEL_FONT = 10  * 1.4
    TICK_FONT   = 8   * 1.4
    BOUNDARY_LW = 2.5

    dend_w  = 18 * 1.4 * 0.30   # inches (30% of original)
    heat_w  = 14                # inches
    gap_w   = 0.3
    total_w = dend_w + heat_w + gap_w + 1.5   # +1.5 for colorbar

    fig_h = max(40, n * 0.13) * 0.40
    fig   = plt.figure(figsize=(total_w, fig_h), dpi=args.dpi)

    # Use gridspec: [dendrogram | gap | heatmap | colorbar]
    gs = gridspec.GridSpec(
        1, 4,
        width_ratios=[dend_w, gap_w, heat_w, 0.4],
        wspace=0.02,
        left=0.01, right=0.99, top=0.97, bottom=0.03,
    )
    ax_dend = fig.add_subplot(gs[0, 0])
    ax_heat = fig.add_subplot(gs[0, 2])
    ax_cb   = fig.add_subplot(gs[0, 3])

    # ---- Dendrogram ----
    log("Plotting dendrogram...")
    dn = dendrogram(
        Z_plot, labels=labels, orientation='left',
        leaf_font_size=LEAF_FONT,
        link_color_func=link_color_func,
        above_threshold_color='#555555',
        ax=ax_dend,
    )
    leaf_order = dn['leaves']

    for line in ax_dend.get_lines():
        line.set_linewidth(line.get_linewidth() * 2.5)

    ax_dend.set_xscale('symlog', linthresh=args.linthresh)
    ax_dend.invert_xaxis()
    ax_dend.yaxis.tick_left()
    ax_dend.yaxis.set_tick_params(pad=6, length=0)
    ax_dend.set_xlabel(
        f'Ward linkage distance  (1 - |CC|)  [symlog scale]',
        fontsize=XLABEL_FONT)
    ax_dend.tick_params(axis='x', labelsize=TICK_FONT)

    # Colour leaf labels
    fig.canvas.draw()
    ylbls = ax_dend.get_yticklabels()
    n_red = 0
    for pos_i, leaf_idx in enumerate(leaf_order):
        m   = medoid_list[leaf_idx]
        col = '#CC0000' if sig_13.get(m, False) else '#000000'
        ylbls[pos_i].set_color(col)
        if col == '#CC0000':
            n_red += 1
    _sigtxt = f"|CC|>{args.cc_sig}" if args.sig_mode == 'cc' else "LP<=-13"
    log(f"  Red labels ({_sigtxt}): {n_red}  Black: {n - n_red}")

    # Invert y-axis if requested
    ax_dend.invert_yaxis()  # match imshow row order (row 0 at top)

    # Legend
    branch_handles = [Patch(facecolor=PALETTE[i % len(PALETTE)],
                            label=f'SC-{i+1}')
                      for i in range(args.nsuper)]
    _notlbl = f'Black: not sig (|CC|<={args.cc_sig})' if args.sig_mode == 'cc' else 'Black: not sig (LP>-13)'
    _siglbl = f'Red: sig (|CC|>{args.cc_sig})'        if args.sig_mode == 'cc' else 'Red: sig (LP<=-13)'
    sig_handles = [
        Line2D([0], [0], color='#000000', lw=2, label=_notlbl),
        Line2D([0], [0], color='#CC0000', lw=2, label=_siglbl),
    ]
    mode_str = 'domain/k400' if args.k400 else 'metric description'
    ax_dend.legend(
        handles=branch_handles + sig_handles,
        loc='lower left', fontsize=LEG_FONT * 0.75,
        framealpha=0.88, ncol=4,
        title=f'{n} medoids | {args.nsuper} super-clusters | {mode_str} | linthresh={args.linthresh}',
        title_fontsize=LEG_FONT * 0.75,
        labelspacing=0.2, handletextpad=0.4,
        borderpad=0.5, columnspacing=1.0,
    )

    # ---- Heatmap ----
    log("Plotting heatmap...")

    cmap = mcolors.LinearSegmentedColormap.from_list(
        'bwr_custom',
        [(0.0, '#2166AC'), (0.5, '#FFFFFF'), (1.0, '#B2182B')]
    )

    # Heatmap colour kwargs. With --cc-threshold T the diverging map SATURATES at
    # +-T: CC <= -T full blue, CC = 0 white, CC >= +T full red, smooth ramp in
    # between (values beyond +-T clamp to full colour). Without it, the map spans
    # the full [-1, 1] range.
    if args.cc_threshold is not None:
        t = abs(args.cc_threshold)
        _imkw = dict(cmap=cmap, vmin=-t, vmax=t, interpolation='none')
        _cb_ticks = [-t, 0.0, t]
    else:
        _imkw = dict(cmap=cmap, vmin=-1.0, vmax=1.0, interpolation='none')
        _cb_ticks = None

    if args.full_heatmap and args.assignments:
        # ---- Full NxN metric heatmap ----
        log(f"  Loading full assignments from {args.assignments}...")
        assign_df = pd.read_csv(args.assignments)
        ward_col_a = [c for c in assign_df.columns if c.startswith('Ward')][0]

        # Use Z_med (unswiveled) for heatmap ordering -- matches plot_full_heatmap.py
        from scipy.cluster.hierarchy import dendrogram as _dn_ref
        _dn_ref_out = _dn_ref(Z_med, no_plot=True)
        ref_leaf_order = _dn_ref_out['leaves']
        ward_leaf_order = [medoid_to_ward.get(medoid_list[i], 0) for i in ref_leaf_order]

        # Sort all metrics by their cluster's position in reference dendrogram leaf order
        ward_to_pos = {wid: pos for pos, wid in enumerate(ward_leaf_order)}
        assign_df['dend_pos'] = assign_df[ward_col_a].map(ward_to_pos)
        assign_df = assign_df.sort_values('dend_pos').reset_index(drop=True)
        metric_order = assign_df['metric'].tolist()
        cluster_order = assign_df[ward_col_a].tolist()
        n_full = len(metric_order)
        log(f"  {n_full} metrics in order")

        # Load full CC matrix
        log(f"  Loading full CC matrix from {args.cc_matrix}...")
        full_cc_df = pd.read_csv(args.cc_matrix, index_col=0)
        # Subset and reorder to metric_order
        available = [m for m in metric_order if m in full_cc_df.index]
        missing_m = [m for m in metric_order if m not in full_cc_df.index]
        if missing_m:
            log(f"  WARNING: {len(missing_m)} metrics not in CC matrix")
        full_cc_sub = full_cc_df.loc[available, available].values.astype(float)
        np.fill_diagonal(full_cc_sub, 1.0)
        full_cc_sub = np.where(np.isfinite(full_cc_sub), full_cc_sub, 0.0)
        n_plot = len(available)
        log(f"  Full CC submatrix: {full_cc_sub.shape}")

        # Cluster boundaries for available metrics
        avail_set = set(available)
        avail_clusters = [cluster_order[i] for i, m in enumerate(metric_order) if m in avail_set]
        cluster_boundaries = []
        super_boundaries   = []
        # Map ward id -> super-cluster
        ward_to_super = {medoid_to_ward.get(medoid_list[i], 0): int(super_labels[i])
                         for i in range(n)}
        prev_c, prev_s = avail_clusters[0], ward_to_super.get(avail_clusters[0], 0)
        for i in range(1, len(avail_clusters)):
            c = avail_clusters[i]
            s = ward_to_super.get(c, 0)
            if c != prev_c:
                cluster_boundaries.append(i - 0.5)
            if s != prev_s:
                super_boundaries.append(i - 0.5)
            prev_c, prev_s = c, s

        im = ax_heat.imshow(
            full_cc_sub, aspect='auto', **_imkw,
        )
        # Thin lines for 100 cluster boundaries
        for b in cluster_boundaries:
            ax_heat.axhline(b, color='black', lw=0.4, zorder=4, alpha=0.6)
            ax_heat.axvline(b, color='black', lw=0.4, zorder=4, alpha=0.6)
        # Thick lines for super-cluster boundaries
        for b in super_boundaries:
            ax_heat.axhline(b, color='black', lw=BOUNDARY_LW, zorder=5)
            ax_heat.axvline(b, color='black', lw=BOUNDARY_LW, zorder=5)
        log(f"  Drew {len(cluster_boundaries)} cluster + {len(super_boundaries)} super-cluster boundaries")

        ax_heat.set_xticks([])
        ax_heat.set_yticks([])
        ax_heat.set_xlabel(f'All metrics (n={n_plot}, cluster order)', fontsize=XLABEL_FONT * 0.8)
        ax_heat.set_ylabel(f'All metrics (n={n_plot}, cluster order)', fontsize=XLABEL_FONT * 0.8)
        ax_heat.set_title(
            f'Full metric CC matrix | n={n_plot} | 100-cluster order\n'
            f'Thin=cluster bounds  Thick={args.nsuper} super-cluster bounds',
            fontsize=XLABEL_FONT * 0.85)

    elif args.centroid_heatmap and args.assignments:
        # ---- 100x100 cluster centroid heatmap ----
        log(f"  Loading full assignments from {args.assignments}...")
        assign_df = pd.read_csv(args.assignments)
        ward_col_a = [c for c in assign_df.columns if c.startswith('Ward')][0]

        # Use Z_med (unswiveled) for centroid heatmap ordering -- matches plot_full_heatmap.py
        from scipy.cluster.hierarchy import dendrogram as _dn_c
        _dn_c_out = _dn_c(Z_med, no_plot=True)
        ward_leaf_order = [medoid_to_ward.get(medoid_list[i], 0) for i in _dn_c_out['leaves']]
        ward_to_pos     = {wid: pos for pos, wid in enumerate(ward_leaf_order)}

        # Load full CC matrix
        log(f"  Loading full CC matrix from {args.cc_matrix}...")
        full_cc_df = pd.read_csv(args.cc_matrix, index_col=0)

        # Build cluster -> metric list (only metrics present in CC matrix)
        cluster_metrics = {}
        for _, row in assign_df.iterrows():
            wid = row[ward_col_a]; m = row['metric']
            if m in full_cc_df.index:
                cluster_metrics.setdefault(wid, []).append(m)

        # Compute 100x100 centroid CC matrix in dendrogram leaf order
        log("  Computing 100x100 cluster centroid CC matrix...")
        n_clusters = len(ward_leaf_order)
        centroid_mat = np.zeros((n_clusters, n_clusters), dtype=float)
        for i, wi in enumerate(ward_leaf_order):
            mi = cluster_metrics.get(wi, [])
            if not mi: continue
            for j, wj in enumerate(ward_leaf_order):
                mj = cluster_metrics.get(wj, [])
                if not mj: continue
                if i == j:
                    centroid_mat[i, j] = 1.0
                else:
                    sub = full_cc_df.loc[mi, mj].values.astype(float)
                    sub = sub[np.isfinite(sub)]
                    centroid_mat[i, j] = float(sub.mean()) if len(sub) else 0.0
        log(f"  Centroid matrix: {centroid_mat.shape}")

        # Super-cluster boundaries in leaf order
        super_ord_cent = [int(super_labels[_dn_c_out['leaves'][i]]) for i in range(n_clusters)]
        ward_to_super_c = {medoid_to_ward.get(medoid_list[i], 0): int(super_labels[i])
                           for i in range(n)}
        boundaries_c = []
        for i in range(1, n_clusters):
            if super_ord_cent[i] != super_ord_cent[i-1]:
                boundaries_c.append(i - 0.5)

        im = ax_heat.imshow(
            centroid_mat, aspect='auto', **_imkw,
        )
        for b in boundaries_c:
            ax_heat.axhline(b, color='black', lw=BOUNDARY_LW, zorder=5)
            ax_heat.axvline(b, color='black', lw=BOUNDARY_LW, zorder=5)
        log(f"  Drew {len(boundaries_c)} super-cluster boundary lines")

        ax_heat.set_xticks([])
        ax_heat.set_yticks([])
        ax_heat.set_xlabel(f'Clusters (n={n_clusters}, dendrogram order)', fontsize=XLABEL_FONT * 0.8)
        ax_heat.set_ylabel(f'Clusters (n={n_clusters}, dendrogram order)', fontsize=XLABEL_FONT * 0.8)
        ax_heat.set_title(
            f'100x100 cluster centroid CC matrix\n'
            f'Mean CC between all metric pairs across cluster pairs',
            fontsize=XLABEL_FONT * 0.85)

    else:
        # ---- Medoid x medoid heatmap (default) ----
        ordered    = list(leaf_order)
        cc_ord     = cc_matrix[np.ix_(ordered, ordered)]
        super_ord  = super_labels[ordered]

        im = ax_heat.imshow(
            cc_ord, aspect='auto', **_imkw,
        )

        boundaries = []
        for i in range(1, len(super_ord)):
            if super_ord[i] != super_ord[i - 1]:
                boundaries.append(i - 0.5)
        for b in boundaries:
            ax_heat.axhline(b, color='black', lw=BOUNDARY_LW, zorder=5)
            ax_heat.axvline(b, color='black', lw=BOUNDARY_LW, zorder=5)
        log(f"  Drew {len(boundaries)} super-cluster boundary lines")

        ax_heat.set_xticks([])
        ax_heat.set_yticks([])
        ax_heat.set_xlabel(f'Medoids (n={n}, dendrogram order)', fontsize=XLABEL_FONT * 0.8)
        ax_heat.set_ylabel(f'Medoids (n={n}, dendrogram order)', fontsize=XLABEL_FONT * 0.8)
        ax_heat.set_title(
            f'Medoid x Medoid CC | {n} medoids | dendrogram order\n'
            f'Black lines = {args.nsuper} super-cluster boundaries',
            fontsize=XLABEL_FONT * 0.85)

    # Colorbar
    cb = fig.colorbar(im, cax=ax_cb, ticks=_cb_ticks)
    cb.set_label('Correlation coefficient (CC)', fontsize=TICK_FONT)
    cb.ax.tick_params(labelsize=TICK_FONT * 0.8)

    # ---- Match Y-axis extent between dendrogram and heatmap ----
    # Both axes span n leaves; force identical ylim so rows align
    dend_ylim = ax_dend.get_ylim()
    n_leaves  = n
    # Dendrogram y goes from 5 to 10*n in steps of 10 (scipy convention)
    # Heatmap y goes from -0.5 to n-0.5
    # We align by setting heatmap ylim to match the fraction of dendrogram
    ax_heat.set_ylim(n_leaves - 0.5, -0.5)   # leaf 0 at top

    log(f"Saving: {args.out}")
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
    log(f"Done. Saved: {args.out}")


if __name__ == '__main__':
    main()
