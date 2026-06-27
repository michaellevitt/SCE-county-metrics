#!/usr/bin/env python3
"""
sem_supercluster.py
====================================
Derive 12 SEM super-clusters from the 100 SEM cluster medoid explain texts.
Input:  ward_sem_metrics.csv (from semantic_cluster_metrics_v2.py)
Method: embed medoid explain texts -> Ward on cosine distance -> k=N cut
This is entirely independent of XDE clustering and CC/excess-death data.
run Ward linkage on cosine distances, cut at k=N to get
semantically coherent super-clusters.

Writes:
  sem_sc_assignments.csv  -- sem100 -> sc_id mapping
  sem_sc_names.csv        -- sc_id -> sc_name (auto-generated, then overridden by --manual-names)
  sc_dendrogram_labels.png        -- dendrogram of 12 SCs
  sc_label_heatmap.png            -- 100x100 cosine similarity heatmap

Usage:
  python3 code/cluster_labels_to_superclusters.py \
    --labels ward_xde_2745/xde100_labels.csv \
    --n-super 11 \
    --model all-mpnet-base-v2 \
    --out-dir ward_xde_2745/ \
    >& cluster_labels_to_superclusters.log
"""

import argparse
import os
import sys
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import pdist, squareform

def _tee(path):
    """Print 'Saved <relpath>' to stdout and stderr."""
    _p = str(path)
    try:
        _rel = os.path.relpath(_p)
    except ValueError:
        _rel = _p
    msg = 'Saved ' + _rel
    print(msg)
    print(msg, file=sys.stderr, flush=True)



def log(msg):
    import time
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def embed_labels(labels, model_name, cache_path=None):
    """Embed cluster label strings using sentence-transformers."""
    if cache_path and os.path.exists(cache_path):
        emb = np.load(cache_path)
        log(f"  Loaded cached embeddings: {emb.shape}")
        if emb.shape[0] == len(labels):
            return emb
        log(f"  Cache size mismatch ({emb.shape[0]} vs {len(labels)}) -- recomputing")

    log(f"  Loading model: {model_name}")
    from sentence_transformers import SentenceTransformer
    import numpy as _np2
    _np2.random.seed(42)
    try:
        import torch as _torch
        _torch.manual_seed(42)
    except ImportError:
        pass
    model = SentenceTransformer(model_name)
    log(f"  Embedding {len(labels)} labels...")
    emb = model.encode(labels, show_progress_bar=True,
                       batch_size=32, normalize_embeddings=True)
    if cache_path:
        np.save(cache_path, emb)
        log(f"  Saved embeddings cache: {cache_path}")
    return emb


def name_supercluster(labels_in_sc, n_words=6):
    """Generate a name for a super-cluster from its member cluster labels."""
    from collections import Counter
    import re

    STOP = {'and', 'by', 'of', 'in', 'the', 'with', 'for', 'to', 'a', 'an',
            'at', 'from', 'or', 'other', 'total', 'age', 'gender', 'sex',
            'demographics', 'characteristics', 'distribution', 'status',
            'services', 'activity', 'resources', 'availability', 'patterns'}

    words = []
    for lbl in labels_in_sc:
        for w in re.split(r'[\s\-_]+', lbl.lower()):
            w = re.sub(r'[^a-z]', '', w)
            if w and w not in STOP and len(w) > 3:
                words.append(w)

    counts = Counter(words)
    top = [w for w, _ in counts.most_common(n_words*2)]

    # Build a name from top words, capitalised
    name_words = []
    seen = set()
    for w in top:
        if w not in seen and len(name_words) < n_words:
            name_words.append(w.capitalize())
            seen.add(w)

    return ' '.join(name_words)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sem-clusters', required=True,
                        help='ward_sem_metrics.csv from semantic_cluster_metrics_v2.py')
    parser.add_argument('--n-super',  type=int, default=12,
                        help='Number of super-clusters (default: 12)')
    parser.add_argument('--model',    default='all-mpnet-base-v2',
                        help='Sentence-transformer model name')
    parser.add_argument('--out-dir',  default='.',
                        help='Output directory')
    parser.add_argument('--embeddings-cache', default=None,
                        help='Path to .npy cache for label embeddings')
    parser.add_argument('--manual-assignments', default=None,
                        help='Protected CSV with sem100,sc_id,sc_name -- fully overrides Ward SC assignments')
    parser.add_argument('--manual-names',     default=None,
                        help='Protected CSV with sc_id,sc_name overrides (never overwritten by pipeline)')
    parser.add_argument('--assignments',      default=None,
                        help='ward_sem_metrics.csv (metric->cluster) for explain listing')
    parser.add_argument('--explain',          default=None,
                        help='BEN_MERGED_MEASURES_explain_extended*.csv for metric explains')
    parser.add_argument('--sem100-labels',    default=None,
                        help='sem100_labels.csv -- LLM short labels for heatmap y-axis')
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # ---- Load labels ----
    # ---- Load SEM cluster medoid explain texts ----
    log(f"Loading SEM clusters from {args.sem_clusters}")
    sem_df = pd.read_csv(args.sem_clusters)
    cl_col = next((c for c in ['cluster_id','semantic_cluster_id','semantic_cluster']
                   if c in sem_df.columns), None)
    if cl_col is None:
        cl_col = next((c for c in sem_df.columns if 'cluster' in c.lower()), None)
    if cl_col is None:
        sys.exit('ERROR: no cluster column found in --sem-clusters file')
    ex_col = 'explain' if 'explain' in sem_df.columns else sem_df.columns[-1]
    if 'is_medoid' in sem_df.columns:
        reps = sem_df[sem_df['is_medoid'] == True].copy()
    else:
        reps = sem_df.groupby(cl_col).first().reset_index()
    reps        = reps.sort_values(cl_col).reset_index(drop=True)
    cluster_ids = reps[cl_col].tolist()
    labels      = reps[ex_col].fillna('').tolist()
    n = len(labels)
    log(f"  {n} SEM clusters -- embedding medoid explain texts")

    # ---- Embed ----
    cache = args.embeddings_cache or os.path.join(args.out_dir,
                                                   'label_embeddings.npy')
    # Invalidate cache if labels file is newer than cache
    if cache and os.path.exists(cache) and os.path.exists(args.sem_clusters):
        if os.path.getmtime(args.sem_clusters) > os.path.getmtime(cache):
            log(f'  Input file newer than cache -- deleting stale cache: {cache}')
            os.remove(cache)
    emb = embed_labels(labels, args.model, cache)

    # Use euclidean distance on L2-normalised embeddings for Ward linkage
    # This is monotonically equivalent to cosine distance but avoids the
    # theoretical issue of applying Ward (Euclidean) to non-Euclidean distances
    log("Computing Ward linkage on L2-normed label embeddings...")
    normed   = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    dist_vec = pdist(normed, metric='euclidean')
    Z = linkage(dist_vec, method='ward')
    # Also keep cosine sim matrix for visualisation
    sim_mat  = normed @ normed.T
    sim_mat  = np.clip(sim_mat, -1, 1)
    dist_mat = 1.0 - sim_mat
    np.fill_diagonal(dist_mat, 0.0)

    # ---- Cut at k=n_super ----
    log(f"Cutting dendrogram at k={args.n_super}...")
    sc_labels = fcluster(Z, args.n_super, criterion='maxclust')

    # ---- Build output ----
    # Map cluster_id -> sc_id
    assign_df = pd.DataFrame({
        'sem100':        cluster_ids,
        'sc_id':         sc_labels,
        'cluster_label': labels,
    })

    # ---- Override SC assignments from manual file if provided ----
    if args.manual_assignments and os.path.exists(args.manual_assignments):
        man = pd.read_csv(args.manual_assignments)
        man_map = dict(zip(man['sem100'].astype(int), man['sc_id'].astype(int)))
        assign_df['sc_id'] = assign_df['sem100'].map(man_map).fillna(assign_df['sc_id']).astype(int)
        log(f'  Loaded {len(man_map)} manual SC assignments from {args.manual_assignments}')
        # Override sc_name from manual file if present
        if 'sc_name' in man.columns:
            man_name = man.drop_duplicates('sc_id').set_index('sc_id')['sc_name'].to_dict()
        else:
            man_name = {}
    else:
        man_name = {}

    # Name each super-cluster
    sc_rows = []
    for sc in sorted(assign_df['sc_id'].unique()):
        sub  = assign_df[assign_df['sc_id'] == sc]
        name = man_name.get(sc) or name_supercluster(sub['cluster_label'].tolist())
        n_cl = len(sub)
        log(f"  SC{sc:02d} ({n_cl} clusters): {name}")
        sc_rows.append({'sc_id': sc, 'sc_name': name,
                        'sc_name_short': name,
                        'n_clusters': n_cl,
                        'cluster_labels': ' | '.join(sub['cluster_label'].tolist())})

    sc_summary = pd.DataFrame(sc_rows)

    # ---- Override SC names from manual file if provided ----
    if args.manual_names and os.path.exists(args.manual_names):
        manual_df = pd.read_csv(args.manual_names)
        manual_map = dict(zip(manual_df['sc_id'].astype(int),
                              manual_df['sc_name'].astype(str)))
        for idx, row in sc_summary.iterrows():
            sc_id = int(row['sc_id'])
            if sc_id in manual_map:
                sc_summary.at[idx, 'sc_name']       = manual_map[sc_id]
                sc_summary.at[idx, 'sc_name_short'] = manual_map[sc_id]
                assign_df.loc[assign_df['sc_id']==sc_id, 'sc_name'] = manual_map[sc_id]
        log(f'  Loaded {len(manual_map)} manual SC names from {args.manual_names}')
        for sc_id, name in sorted(manual_map.items()):
            log(f'    SC{sc_id:02d}: {name}')

    # ---- Coherence report + detailed listing ----
    log("Computing within-SC cosine coherence and writing report...")

    # Load per-metric data if available
    metric_explain = {}
    metric_ward    = {}
    if args.assignments and os.path.exists(args.assignments):
        adf = pd.read_csv(args.assignments)
        ward_col_a = [c for c in adf.columns if 'Ward' in c or 'ward' in c][0]
        metric_ward = dict(zip(adf['metric'], adf[ward_col_a].astype(int)))
    if args.explain and os.path.exists(args.explain):
        edf = pd.read_csv(args.explain)
        if 'explain' in edf.columns:
            metric_explain = dict(zip(edf['metric'], edf['explain'].fillna('')))

    # Invert: sem100 -> [metrics]
    ward_to_metrics = {}
    for m, w in metric_ward.items():
        ward_to_metrics.setdefault(int(w), []).append(m)

    # Within-SC cosine coherence
    from collections import Counter
    import re as _re

    STOPWORDS = {'and','or','the','of','by','in','for','with','a','an','at','to',
                 'from','on','is','are','as','its','their','this','that','these',
                 'those','care','services','demographics','population',
                 'characteristics','status','resources','distribution',
                 'availability','providers','workforce','infrastructure',
                 'medical','healthcare','county','hospital','demographic',
                 'staffing','capacity','health','physician','specialty'}

    def top_words(lbls, n=5):
        words = []
        for lbl in lbls:
            words += [w.lower() for w in _re.findall(r'[A-Za-z]+', lbl)
                      if w.lower() not in STOPWORDS and len(w) > 3]
        c = Counter(words)
        return [(w, cnt) for w, cnt in c.most_common(n) if cnt >= 2]

    report_lines = []
    report_lines.append('=' * 80)
    report_lines.append(f'SUPER-CLUSTER COHERENCE REPORT  (k={args.n_super})')
    report_lines.append('=' * 80)

    for sc in sorted(assign_df['sc_id'].unique()):
        sub   = assign_df[assign_df['sc_id'] == sc].copy()
        sub   = sub.sort_values('sem100')
        sc_id = int(sc)
        n_cl  = len(sub)
        sc_nm = sc_summary[sc_summary['sc_id'] == sc].iloc[0]['sc_name']

        # Within-SC mean cosine similarity
        idxs  = [cluster_ids.index(int(w)) for w in sub['sem100'] if int(w) in cluster_ids]
        if len(idxs) >= 2:
            sub_sim = sim_mat[np.ix_(idxs, idxs)]
            np.fill_diagonal(sub_sim, np.nan)
            mean_cos = float(np.nanmean(sub_sim))
            min_cos  = float(np.nanmin(sub_sim))
        else:
            mean_cos = 1.0; min_cos = 1.0

        shared = top_words(sub['cluster_label'].tolist())
        shared_str = ', '.join(f'{w}({c})' for w,c in shared[:4]) if shared else 'no shared words'

        coherence = 'HIGH' if mean_cos > 0.55 else 'MED' if mean_cos > 0.40 else 'LOW'

        report_lines.append('')
        report_lines.append(f'SC{sc_id:02d}  {n_cl} clusters  mean_cos={mean_cos:.3f}  min_cos={min_cos:.3f}  [{coherence}]')
        report_lines.append(f'     Name:   {sc_nm}')
        report_lines.append(f'     Shared: {shared_str}')
        report_lines.append('')

        for _, r in sub.iterrows():
            w = int(r['sem100'])
            lbl = str(r['cluster_label'])
            report_lines.append(f'     W{w:3d}  {lbl}')

            # Top 3 metrics with explain
            metrics = ward_to_metrics.get(w, [])
            if metric_explain and metrics:
                for m in metrics[:3]:
                    ex = metric_explain.get(m, '')
                    report_lines.append(f'           {m}  {ex}')

    # Write report
    report_path = os.path.join(args.out_dir, 'sem_sc_coherence_report.txt')
    with open(report_path, 'w') as _f:
        _f.write('\n'.join(report_lines) + '\n')
    _tee(report_path)
    log(f"  Saved coherence report: {report_path}")

    # Print summary table to stdout
    print("\nSC COHERENCE SUMMARY:")
    print(f"{'SC':>4}  {'n':>3}  {'mean_cos':>9}  {'coherence':>10}  {'shared words':<35}  SC name")
    print("-" * 110)
    for sc in sorted(assign_df['sc_id'].unique()):
        sub   = assign_df[assign_df['sc_id'] == sc]
        sc_nm = sc_summary[sc_summary['sc_id'] == sc].iloc[0]['sc_name']
        idxs  = [cluster_ids.index(int(w)) for w in sub['sem100'] if int(w) in cluster_ids]
        if len(idxs) >= 2:
            sub_sim = sim_mat[np.ix_(idxs, idxs)]
            np.fill_diagonal(sub_sim, np.nan)
            mean_cos = float(np.nanmean(sub_sim))
        else:
            mean_cos = 1.0
        coherence = 'HIGH' if mean_cos > 0.55 else 'MED' if mean_cos > 0.40 else 'LOW'
        shared = top_words(sub['cluster_label'].tolist())
        shared_str = ', '.join(f'{w}({c})' for w,c in shared[:3]) if shared else '-'
        print(f"SC{int(sc):02d}  {len(sub):>3}  {mean_cos:>9.3f}  {coherence:>10}  {shared_str:<35}  {sc_nm}")

    print(f"\nReport written to: {report_path}")
    print(f"  (includes cluster labels and top-3 metrics per cluster)", flush=True)
    print(f"  (includes cluster labels and top-3 metrics per cluster)",
          file=sys.stderr, flush=True)


    # ---- Dendrogram ----
    log("Plotting dendrogram...")
    fig, ax = plt.subplots(figsize=(12, max(8, n * 0.12)))
    sc_color_map = {}
    colors = plt.cm.tab20.colors
    for sc in sorted(assign_df['sc_id'].unique()):
        sc_color_map[sc] = colors[(sc - 1) % len(colors)]

    # Build leaf label -> color mapping
    leaf_labels = [f"W{int(cluster_ids[i]):3d}  {labels[i]}"
                   for i in range(n)]

    dend = dendrogram(Z, ax=ax, orientation='left',
                      labels=leaf_labels,
                      leaf_font_size=7,
                      color_threshold=Z[-(args.n_super-1), 2])
    ax.set_xlabel('Ward linkage distance (cosine)', fontsize=10)
    ax.set_title(f'Super-cluster dendrogram: {n} cluster labels -> {args.n_super} SCs\n'
                 f'(semantic embedding, Ward linkage)', fontsize=11)
    ax.axvline(Z[-(args.n_super-1), 2], color='red', lw=1.5, ls='--',
               alpha=0.7, label=f'k={args.n_super} cut')
    ax.legend(fontsize=9)
    plt.tight_layout()
    dend_path = os.path.join(args.out_dir, 'sc_dendrogram_labels.png')
    fig.savefig(dend_path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close()
    _tee(dend_path)

    # Build SC name map from sc_summary (includes all manual overrides)
    sc_name_map = dict(zip(sc_summary['sc_id'].astype(int), sc_summary['sc_name'].astype(str)))

    # ---- Similarity heatmap (100x100, ordered by SC) ----
    log("Plotting similarity heatmap...")
    sorted_df = assign_df.sort_values(['sc_id', 'sem100']).reset_index(drop=True)
    order = sorted_df.index.tolist()
    sim_ord = sim_mat[np.ix_(sorted_df['sem100'].map(
        {v: i for i, v in enumerate(assign_df['sem100'].tolist())}).tolist(),
        sorted_df['sem100'].map(
        {v: i for i, v in enumerate(assign_df['sem100'].tolist())}).tolist())]

    # SC boundary positions and midpoints
    sc_ord = sorted_df['sc_id'].tolist()
    boundaries = [i for i in range(1, n) if sc_ord[i] != sc_ord[i-1]]
    bdry_ext = [0] + boundaries + [n]
    sc_mids  = [(bdry_ext[i] + bdry_ext[i+1]) / 2.0 for i in range(len(bdry_ext)-1)]
    sc_ids_unique = []
    for b in range(len(bdry_ext)-1):
        sc_ids_unique.append(sc_ord[bdry_ext[b]])

    # Individual cluster labels (short -- first 30 chars)
    clust_labels = [str(r['cluster_label'])[:30]
                    for _, r in sorted_df.iterrows()]
    # SC midpoint labels
    sc_mid_labels = [f"SC{sc:02d}: {sc_name_map.get(sc, '')}"[:38]
                     for sc in sc_ids_unique]

    # Full SC name labels (untruncated)
    sc_mid_labels_full = [f"SC{sc:02d}: {sc_name_map.get(sc, '')}"
                          for sc in sc_ids_unique]
    # Load LLM short labels if available, else fall back to explain text
    short_label_map = {}
    if args.sem100_labels and os.path.exists(args.sem100_labels):
        _sl = pd.read_csv(args.sem100_labels)
        log(f"  sem100_labels cols: {list(_sl.columns)}  rows: {len(_sl)}")
        _id_col = next((c for c in ['sem100','cluster_id','Ward100','cluster'] if c in _sl.columns), _sl.columns[0])
        _lb_col = next((c for c in ['label_proposed','label','cluster_label','short_label','name'] if c in _sl.columns), _sl.columns[-1])
        short_label_map = dict(zip(_sl[_id_col].astype(int), _sl[_lb_col].astype(str)))
        log(f"  Loaded {len(short_label_map)} short labels (id_col={_id_col!r}, lb_col={_lb_col!r})")
    else:
        log(f"  sem100_labels not found: {args.sem100_labels} -- using explain text")
    # Full cluster labels: short LLM label if available, else explain text
    clust_labels_full = [
        short_label_map.get(int(r['sem100']), str(r['cluster_label']))
        for _, r in sorted_df.iterrows()
    ]

    # Figure: square image with label margins
    fig2 = plt.figure(figsize=(24, 20))
    ax2 = fig2.add_axes([0.30, 0.03, 0.52, 0.90])
    im = ax2.imshow(sim_ord, aspect='equal', cmap='RdBu_r',
                    vmin=-0.2, vmax=1.0, interpolation='none')

    # SC boundary lines (thick black)
    for b in boundaries:
        ax2.axhline(b - 0.5, color='black', lw=2.0)
        ax2.axvline(b - 0.5, color='black', lw=2.0)

    # Individual cluster tick labels on left y-axis
    ax2.set_yticks(range(n))
    ax2.set_yticklabels(clust_labels_full, fontsize=8.75, fontweight='bold')
    ax2.tick_params(axis='y', length=2, pad=2)
    ax2.set_xticks([])

    ax2.set_title('Cluster label cosine similarity (100x100)\nordered by super-cluster assignment',
                  fontsize=11, fontweight='bold', pad=8)

    # SC midpoint labels: draw after savefig renders axes, using ax2 data->figure transform
    # Must call draw() first to resolve transforms
    fig2.canvas.draw()
    trans = ax2.transData + fig2.transFigure.inverted()
    for mid, lbl in zip(sc_mids, sc_mid_labels_full):
        # mid is in data coords (row index); convert to figure fraction
        _, fy = trans.transform((0, mid))
        fig2.text(0.83, fy, lbl, va='center', ha='left',
                  fontsize=8.5, fontweight='bold', transform=fig2.transFigure)

    hm_path = os.path.join(args.out_dir, 'sc_label_heatmap.png')
    fig2.savefig(hm_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    _tee(hm_path)

    # ---- Save outputs ----
    assign_path = os.path.join(args.out_dir, 'sem_sc_assignments.csv')
    assign_df.to_csv(assign_path, index=False)
    _tee(assign_path)
    log(f"  Saved: {assign_path}")

    # Write auto-generated names (before manual overrides) for reference
    auto_path = os.path.join(args.out_dir, 'sem_sc_names_auto.csv')
    sc_summary[['sc_id', 'sc_name', 'sc_name_short']].to_csv(auto_path, index=False)
    _tee(auto_path)
    # Apply manual overrides and write final names file
    if args.manual_names and os.path.exists(args.manual_names):
        manual_df2 = pd.read_csv(args.manual_names)
        manual_map2 = dict(zip(manual_df2['sc_id'].astype(int),
                               manual_df2['sc_name'].astype(str)))
        for idx, row in sc_summary.iterrows():
            sc_id = int(row['sc_id'])
            if sc_id in manual_map2:
                sc_summary.at[idx, 'sc_name']       = manual_map2[sc_id]
                sc_summary.at[idx, 'sc_name_short'] = manual_map2[sc_id]
    sc_path = os.path.join(args.out_dir, 'sem_sc_names.csv')
    sc_summary[['sc_id', 'sc_name', 'sc_name_short']].to_csv(sc_path, index=False)
    _tee(sc_path)
    log(f"  Saved: {sc_path}")

    # Full summary with cluster membership
    full_path = os.path.join(args.out_dir, 'sem_sc_summary.csv')
    sc_summary.to_csv(full_path, index=False)
    _tee(full_path)
    log(f"  Saved: {full_path}")

    # Print final assignment table
    print("\nFINAL SUPER-CLUSTER ASSIGNMENTS:")
    print(f"{'SC':>4}  {'n_cl':>5}  {'SC name':50s}  Clusters")
    print("-" * 120)
    for _, r in sc_summary.iterrows():
        sub_wards = assign_df[assign_df['sc_id']==r['sc_id']]['sem100'].tolist()
        ward_str  = ' '.join(f"W{int(w)}" for w in sorted(sub_wards))
        print(f"SC{int(r['sc_id']):02d}  {int(r['n_clusters']):5d}  {r['sc_name']:50s}  {ward_str}")

    log(f"\nDone. Outputs in {args.out_dir}")


if __name__ == '__main__':
    main()
