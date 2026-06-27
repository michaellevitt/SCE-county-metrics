#!/usr/bin/env python3
"""
semantic_cluster_metrics_v2.py

Cluster all metrics in BEN_MERGED_MEASURES_explain_extended.csv by the
semantic content of their 'explain' field, entirely independent of any
correlation data.

Pipeline:
  1. Embed each 'explain' string with a sentence-transformer model
  2. Optionally reduce dimensions with UMAP (skip with --umap-dims 0)
  3. Ward linkage on cosine distance
  4. Adaptive cut via silhouette peak OR --n-clusters
  5. Name each cluster by the explain text nearest to its centroid (semantic medoid)
  6. Outputs: per-metric CSV, cluster summary CSV, elbow PNG, silhouette PNG,
              dendrogram PNG, size histogram PNG

Recommended models (in order of preference):
  all-mpnet-base-v2          Best general purpose, 768-dim, ~420MB (DEFAULT)
  pritamdeka/S-PubMedBert-MS-MARCO  Biomedical text, 768-dim, ~420MB
  all-MiniLM-L6-v2           Fast/small fallback, 384-dim, ~90MB

Usage (recommended - no UMAP, best model):
  python3 semantic_cluster_metrics_v2.py \\
    --explain BEN_MERGED_MEASURES_explain_extended.csv \\
    --output-dir ward_sem_v2/ \\
    --embeddings-cache embeddings_mpnet.npy \\
    --model all-mpnet-base-v2 \\
    --umap-dims 0 \\
    --silhouette-ks 40,60,80,100,120,150,200,280

Usage (with UMAP, lower memory):
  python3 semantic_cluster_metrics_v2.py \\
    --explain BEN_MERGED_MEASURES_explain_extended.csv \\
    --output-dir ward_sem_v2/ \\
    --embeddings-cache embeddings_mpnet.npy \\
    --model all-mpnet-base-v2 \\
    --umap-dims 50 \\
    --silhouette-ks 40,60,80,100,120,150,200,280
"""

import argparse
import os
import sys
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import pdist
from sklearn.metrics import silhouette_score

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



def log(msg, level=1, tee=False):
    ts = datetime.now().strftime("%H:%M:%S")
    indent = "  " * (level - 1)
    formatted = f"[{ts}] {indent}{msg}"
    print(formatted, flush=True)
    if tee:
        print(formatted, flush=True, file=sys.stderr)


def load_explain(path):
    df = pd.read_csv(path)
    required = {'metric', 'explain'}
    missing = required - set(df.columns)
    if missing:
        log(f"ERROR: explain file missing columns: {missing}", tee=True)
        sys.exit(1)
    before = len(df)
    df = df[df['explain'].notna() & (df['explain'].str.strip() != '')].copy()
    df['explain'] = df['explain'].str.strip()
    log(f"Loaded {before} rows; {len(df)} have non-empty explain text")
    return df.reset_index(drop=True)


# --- Boilerplate stripping for --clean-names -------------------------------
# Removes age bands, sex, practice-role suffixes and count/percent/population
# prefixes so the embedding keys on the metric SUBJECT rather than shared
# surface tokens.  e.g. 'Pulmonary_Diseases_35_44=2018' -> 'Pulmonary_Diseases'
_CN_AGE  = r'(_<_?\d+|_\d+_\d+|_\d+_\+|_>_?\d+|_\d+\+)'
_CN_ROLE = [r'_Patient_Care_Hospital_Full_Time_Staff', r'_Patient_Care_Hospital_Residents?',
            r'_Patient_Care_Office_Based', r'_Total_Patient_Care', r'_Other_Professional_Activ\w*',
            r'_Administrat\w*', r'_Teaching', r'_Research', r'_Total', r'_Other', r'_Male', r'_Female']
def clean_metric_name(s):
    import re
    s = str(s).split('=')[0].strip()
    s = re.sub(r'^[#%]+_?', '', s)
    s = re.sub(r'^(Population|Percent|Per)_', '', s)
    # Dominant 'Hospital_with_' prefix collapses ~166 distinct services into one
    # giant block; strip it so they key on the service (Oncology, Cardiac, ...).
    # NOTE: '16+_Workers_' is intentionally NOT stripped -- it is only a ~24-metric
    # cluster and removing it fragments a coherent commuting group.
    s = re.sub(r'^Hospital_with_', '', s)
    for _ in range(4):
        s = re.sub(_CN_AGE + r'$', '', s)
        for r in _CN_ROLE:
            s = re.sub(r + r'$', '', s)
    return s.strip('_ ') or str(s)


def embed_texts(texts, model_name, cache_path=None):
    if cache_path and os.path.exists(cache_path):
        log(f"Loading cached embeddings from {cache_path}")
        emb = np.load(cache_path)
        if emb.shape[0] == len(texts):
            log(f"  Cache hit: shape={emb.shape}")
            return emb
        log(f"  Cache shape mismatch ({emb.shape[0]} vs {len(texts)}), recomputing")

    log(f"Loading model: {model_name}")
    log(f"  (First run downloads model; subsequent runs use local cache)", 2)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    log(f"Embedding {len(texts)} texts (batch_size=64)...")
    emb = model.encode(
        texts,
        show_progress_bar=True,
        batch_size=64,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    log(f"  Embeddings shape: {emb.shape}")
    if cache_path:
        np.save(cache_path, emb)
        log(f"  Saved embeddings cache: {cache_path}")
    return emb


def reduce_umap(emb, n_components, n_neighbors, random_state=42):
    log(f"UMAP: {emb.shape[1]}-dim -> {n_components}-dim  (n_neighbors={n_neighbors})")
    import umap
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        metric='cosine',
        random_state=random_state,
        low_memory=False,
        verbose=False,
    )
    reduced = reducer.fit_transform(emb)
    log(f"  UMAP done: {reduced.shape}")
    return reduced


def normalize_rows(X):
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-10, norms)
    return X / norms


def compute_linkage(X, label='embeddings'):
    log(f"Ward linkage on {label} ({X.shape[0]} x {X.shape[1]})...")
    normed = normalize_rows(X)
    # Symmetrize: compute condensed distance, Ward linkage
    dist = pdist(normed, metric='euclidean')
    log(f"  Distance vector length: {len(dist)}")
    Z = linkage(dist, method='ward')
    log(f"  Linkage matrix: {Z.shape}")
    return Z, normed


def find_elbow_k(Z, max_k=500):
    n = len(Z) + 1
    gaps = []
    for k in range(2, min(max_k, n)):
        d_k   = Z[n - k - 1, 2]
        d_kp1 = Z[n - k,     2]
        gaps.append((d_kp1 - d_k, k))
    gaps.sort(reverse=True)
    # Skip k=2 and k=3 which are almost always the largest gaps (top-level split)
    filtered = [(g, k) for g, k in gaps if k > 3]
    best_k = filtered[0][1] if filtered else gaps[0][1]
    log(f"Elbow (k>3): best k={best_k} (gap={filtered[0][0]:.4f}); "
        f"top 5: {[k for _, k in filtered[:5]]}")
    return best_k


def compute_silhouette_range(normed, Z, ks):
    log(f"Silhouette scores for k in {ks} (full dataset, n={normed.shape[0]})...")
    scores = []
    for k in ks:
        labels = fcluster(Z, k, criterion='maxclust')
        if len(set(labels)) < 2:
            scores.append(np.nan)
            log(f"  k={k:4d}  silhouette=n/a (too few clusters)", 2)
            continue
        try:
            s = silhouette_score(normed, labels, metric='euclidean')
        except Exception as e:
            s = np.nan
            log(f"  k={k:4d}  silhouette=ERROR {e}", 2)
        scores.append(s)
        log(f"  k={k:4d}  silhouette={s:.4f}", 2)
    return scores


def find_silhouette_peak(ks, scores):
    valid = [(k, s) for k, s in zip(ks, scores) if not np.isnan(s)]
    if not valid:
        return None
    best_k, best_s = max(valid, key=lambda x: x[1])
    log(f"Silhouette peak: k={best_k} (score={best_s:.4f})")
    return best_k


def plot_elbow(Z, out_path, chosen_k):
    n = len(Z) + 1
    ks = list(range(2, min(301, n)))
    dists = [Z[n - k - 1, 2] for k in ks]
    fig, ax = plt.subplots(figsize=(12, 5), dpi=150)
    ax.plot(ks, dists, lw=1.5, color='steelblue')
    ax.axvline(chosen_k, color='red', lw=1.5, ls='--', label=f'Chosen k={chosen_k}')
    ax.set_xlabel('Number of clusters (k)', fontsize=13)
    ax.set_ylabel('Ward merge distance at cut', fontsize=13)
    ax.set_title('Elbow plot: Ward merge distance vs k', fontsize=15)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    log(f"  Saved: {out_path}")


def plot_silhouette(ks, scores, out_path, chosen_k):
    fig, ax = plt.subplots(figsize=(12, 5), dpi=150)
    valid_ks = [k for k, s in zip(ks, scores) if not np.isnan(s)]
    valid_s  = [s for s in scores if not np.isnan(s)]
    ax.plot(valid_ks, valid_s, lw=1.5, color='darkorange', marker='o', ms=6)
    ax.axvline(chosen_k, color='red', lw=1.5, ls='--', label=f'Chosen k={chosen_k}')
    ax.set_xlabel('Number of clusters (k)', fontsize=13)
    ax.set_ylabel('Mean silhouette score (full dataset)', fontsize=13)
    ax.set_title('Silhouette score vs k', fontsize=15)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    log(f"  Saved: {out_path}")


def name_clusters(df, labels, normed, min_cluster_size):
    cluster_info = {}
    for cid in sorted(set(labels)):
        mask = labels == cid
        members = np.where(mask)[0]
        size = len(members)
        centroid = normed[members].mean(axis=0)
        dists = np.linalg.norm(normed[members] - centroid, axis=1)
        medoid_local = np.argmin(dists)
        medoid_idx = members[medoid_local]
        cluster_info[cid] = {
            'label':             df.iloc[medoid_idx]['explain'],
            'medoid_metric':     df.iloc[medoid_idx]['metric'],
            'medoid_explain':    df.iloc[medoid_idx]['explain'],
            'size':              size,
            'is_singleton':      size < min_cluster_size,
            'centroid_dist_mean': float(dists.mean()),
            'centroid_dist_max':  float(dists.max()),
        }
    return cluster_info


def plot_dendrogram(Z, out_path, n_show=200):
    n = len(Z) + 1
    log(f"Truncated dendrogram (p={n_show} of {n} leaves)...")
    fig, ax = plt.subplots(figsize=(16, 10), dpi=120)
    dendrogram(
        Z, ax=ax,
        truncate_mode='lastp', p=n_show,
        leaf_rotation=90, leaf_font_size=7,
        show_contracted=True,
        above_threshold_color='#888888',
    )
    ax.set_title(
        f'Ward Dendrogram of {n} Metrics by Semantic Embedding\n'
        f'(Truncated to top {n_show} nodes)',
        fontsize=14)
    ax.set_xlabel('Metric (cluster size in parentheses)', fontsize=11)
    ax.set_ylabel('Ward merge distance', fontsize=11)
    ax.tick_params(axis='x', labelsize=6)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    log(f"  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Cluster AHRF metrics by semantic content of explain field.",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--explain', required=True,
                        help="Path to BEN_MERGED_MEASURES_explain_extended.csv")
    parser.add_argument('--output-dir', required=True,
                        help="Directory for all outputs")
    parser.add_argument('--n-clusters', type=int, default=None,
                        help="Force k clusters (default: silhouette peak, "
                             "fallback to elbow)")
    parser.add_argument('--umap-dims', type=int, default=0,
                        help="UMAP output dimensions. 0 = skip UMAP entirely "
                             "(recommended when using full model on local machine). "
                             "Default: 0")
    parser.add_argument('--umap-neighbors', type=int, default=15,
                        help="UMAP n_neighbors (only used if --umap-dims > 0, "
                             "default 15)")
    parser.add_argument('--min-cluster-size', type=int, default=2,
                        help="Clusters below this size flagged as singletons "
                             "(default 2)")
    parser.add_argument('--model', default='all-mpnet-base-v2',
                        help="Sentence-transformer model. Options:\n"
                             "  all-mpnet-base-v2 (default, best quality, ~420MB)\n"
                             "  pritamdeka/S-PubMedBert-MS-MARCO (biomedical, ~420MB)\n"
                             "  all-MiniLM-L6-v2 (fast fallback, ~90MB)")
    parser.add_argument('--embeddings-cache', default=None,
                        help="Path to .npy file to save/load embeddings "
                             "(avoids redownloading/recomputing on reruns)")
    parser.add_argument('--clean-names', action='store_true',
                        help="Strip age/sex/practice-role/count boilerplate from metric "
                             "names BEFORE embedding, so clusters key on subject not surface "
                             "tokens. Use a DISTINCT --embeddings-cache and --output-dir.")
    parser.add_argument('--silhouette-ks', default='40,60,80,100,120,150,200,280',
                        help="Comma-separated k values for silhouette evaluation. "
                             "Default: 40,60,80,100,120,150,200,280")
    parser.add_argument('--metrics-list', default=None,
                        help='Text file one metric ID per line -- filter explain to assembled metrics only')
    parser.add_argument('--normed-matrix', default=None,
                   help='Pre-computed L2-normed embeddings .npy -- skip embedding step')
    parser.add_argument('--cc-file', default=None,
                   help='metric_x_death_cc CSV -- compute best_cc per SEM cluster')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    log(f"Model:      {args.model}")
    log(f"UMAP dims:  {args.umap_dims if args.umap_dims > 0 else 'disabled (using raw embeddings)'}")
    log(f"Output dir: {args.output_dir}")

    # Load
    df = load_explain(args.explain)
    if args.metrics_list and os.path.exists(args.metrics_list):
        keep = set(l.strip() for l in open(args.metrics_list) if l.strip())
        before = len(df)
        df = df[df['metric'].isin(keep)].copy().reset_index(drop=True)
        log(f'  Filtered to {len(df)} of {before} metrics via --metrics-list')
    texts = df['explain'].tolist()
    if args.clean_names:
        cleaned = [clean_metric_name(t) for t in texts]
        log(f'  --clean-names ON: embedding stripped subjects '
            f'({len(set(cleaned))} unique of {len(cleaned)}); '
            f'e.g. {texts[0]!r} -> {cleaned[0]!r}')
        texts = cleaned   # NOTE: only the embedding text changes; df['explain'] (used
                          # for labels/medoids downstream) keeps the full original name.
    n = len(texts)

    # Embed (or load pre-computed normed matrix to skip embedding)
    if args.normed_matrix and os.path.exists(args.normed_matrix):
        log(f'Loading pre-computed normed matrix from {args.normed_matrix}')
        X = np.load(args.normed_matrix)
        log(f'  Loaded: {X.shape}')
        linkage_label = f'pre-normed {X.shape[1]}-dim embeddings'
    else:
        emb = embed_texts(texts, args.model, args.embeddings_cache)
        if args.umap_dims > 0:
            X = reduce_umap(emb, args.umap_dims, args.umap_neighbors)
            linkage_label = f'UMAP-{args.umap_dims}d cosine-normed'
        else:
            X = emb
            linkage_label = f'raw {emb.shape[1]}-dim embeddings cosine-normed'
        log(f"Skipping UMAP: using raw {emb.shape[1]}-dim embeddings directly")

    # Linkage
    Z, normed = compute_linkage(X, label=linkage_label)
    normed_path = os.path.join(args.output_dir, 'embeddings_normed.npy')
    np.save(normed_path, normed)
    log(f'  Saved normed matrix: {normed_path} (use --normed-matrix to skip re-embedding)')

    # Silhouette evaluation
    sil_ks = [int(x) for x in args.silhouette_ks.split(',')]
    sil_scores = compute_silhouette_range(normed, Z, sil_ks)
    pd.DataFrame({'k': sil_ks, 'silhouette': sil_scores}).to_csv(
        os.path.join(args.output_dir, 'silhouette_scores.csv'), index=False)

    # Choose k
    if args.n_clusters:
        chosen_k = args.n_clusters
        log(f"Using specified k={chosen_k}")
    else:
        chosen_k = find_silhouette_peak(sil_ks, sil_scores)
        if chosen_k is None:
            log("Silhouette failed, falling back to elbow")
            chosen_k = find_elbow_k(Z)
        else:
            log(f"Using silhouette peak k={chosen_k}")

    # Elbow plot (for reference)
    plot_elbow(Z, os.path.join(args.output_dir, 'elbow.png'), chosen_k)

    # Silhouette plot
    plot_silhouette(sil_ks, sil_scores,
                    os.path.join(args.output_dir, 'silhouette.png'), chosen_k)

    # Cluster assignment
    log(f"Cutting dendrogram at k={chosen_k}...")
    labels = fcluster(Z, chosen_k, criterion='maxclust')

    # Cluster naming
    log("Naming clusters by semantic medoid...")
    cluster_info = name_clusters(df, labels, normed, args.min_cluster_size)
    n_singletons = sum(1 for v in cluster_info.values() if v['is_singleton'])
    sizes = [v['size'] for v in cluster_info.values()]
    log(f"  {chosen_k} clusters: {chosen_k - n_singletons} multi-member, "
        f"{n_singletons} singletons")
    log(f"  Size: min={min(sizes)} max={max(sizes)} "
        f"mean={np.mean(sizes):.1f} median={np.median(sizes):.1f}")

    # Dendrogram
    plot_dendrogram(Z, os.path.join(args.output_dir, 'dendrogram.png'))

    # Per-metric output
    log("Writing per-metric CSV...")
    centroid_dists = np.full(n, np.nan)
    for cid in set(labels):
        mask = labels == cid
        members = np.where(mask)[0]
        centroid = normed[members].mean(axis=0)
        dists = np.linalg.norm(normed[members] - centroid, axis=1)
        centroid_dists[members] = dists

    out_df = df.copy()
    out_df['cluster_id']             = labels
    out_df['semantic_cluster_id']    = labels  # alias for backwards compat
    out_df['semantic_cluster_label'] = [cluster_info[c]['label'] for c in labels]
    out_df['semantic_medoid_metric'] = [cluster_info[c]['medoid_metric'] for c in labels]
    out_df['is_singleton']           = [cluster_info[c]['is_singleton'] for c in labels]
    out_df['centroid_distance']      = np.round(centroid_dists, 4)
    out_df = out_df.sort_values(
        ['semantic_cluster_id', 'centroid_distance']).reset_index(drop=True)

    metrics_csv = os.path.join(args.output_dir, 'ward_sem_metrics.csv')
    out_df.to_csv(metrics_csv, index=False)
    _tee(metrics_csv)
    log(f"  Saved: {metrics_csv} ({len(out_df)} rows)")

    # Cluster summary
    log("Writing cluster summary CSV...")
    summary_rows = []
    for cid in sorted(cluster_info.keys()):
        info = cluster_info[cid]
        mask = labels == cid
        member_metrics = df[mask]['metric'].tolist()
        summary_rows.append({
            'cluster_id':          cid,
            'size':                info['size'],
            'is_singleton':        info['is_singleton'],
            'medoid_metric':       info['medoid_metric'],
            'cluster_label':       info['label'],
            'medoid_explain_full': info['medoid_explain'],
            'centroid_dist_mean':  round(info['centroid_dist_mean'], 4),
            'centroid_dist_max':   round(info['centroid_dist_max'], 4),
            'member_metrics':      '; '.join(member_metrics[:10]) +
                                   (f' ... +{len(member_metrics)-10} more'
                                    if len(member_metrics) > 10 else ''),
        })
    summary_df = pd.DataFrame(summary_rows).sort_values(
        'cluster_id').reset_index(drop=True)
    summary_csv = os.path.join(args.output_dir, 'ward_sem_summary.csv')
    summary_df.to_csv(summary_csv, index=False)
    _tee(summary_csv)
    log(f"  Saved: {summary_csv} ({len(summary_df)} rows)")

    # ---- Save Z_med (medoid-level linkage for dendrogram) ----
    # Build medoid-level distance matrix and linkage
    medoid_metrics = summary_df.sort_values('cluster_id')['medoid_metric'].tolist()
    medoid_indices = [df[df['metric']==m].index[0] for m in medoid_metrics
                      if m in df['metric'].values]
    if len(medoid_indices) >= 2:
        med_emb  = normed[medoid_indices]
        med_dist = pdist(med_emb, metric='euclidean')
        Z_med    = linkage(med_dist, method='ward')
        z_med_path = os.path.join(args.output_dir, 'Z_med_sem100.npy')
        np.save(z_med_path, Z_med)
        _tee(z_med_path)
        medoid_list_path = os.path.join(args.output_dir, 'medoid_list_sem100.json')
        import json as _json
        _json.dump(medoid_metrics, open(medoid_list_path, 'w'))
        _tee(medoid_list_path)
        log(f'  Saved Z_med_sem100.npy and medoid_list_sem100.json')

    # ---- Compute best_cc per SEM cluster from CC file ----
    best_cc_map = {}
    if args.cc_file and os.path.exists(args.cc_file):
        log(f'  Computing best_cc per SEM cluster from {args.cc_file}...')
        cc_df = pd.read_csv(args.cc_file, index_col='metric')
        asedx_cols = [c for c in cc_df.columns
                      if c.startswith('asedx_p_') and 'GE65' not in c and 'LT65' not in c]
        metric_to_cluster = dict(zip(out_df['metric'], out_df['cluster_id']))
        for cid in sorted(cluster_info.keys()):
            members = [m for m in out_df[out_df['cluster_id']==cid]['metric']
                       if m in cc_df.index]
            if members and asedx_cols:
                sub = cc_df.loc[members, asedx_cols].apply(pd.to_numeric, errors='coerce')
                abs_max = sub.abs().max(axis=1)
                best_m  = abs_max.idxmax()
                best_col = sub.loc[best_m].abs().idxmax()
                best_cc_map[cid] = round(float(sub.loc[best_m, best_col]), 4)
            else:
                best_cc_map[cid] = float('nan')

    # ---- Save ward_sem_reps.csv ----
    reps_rows = []
    for _, row in summary_df.iterrows():
        cid = int(row['cluster_id'])
        reps_rows.append({
            'sem100':       cid,
            'medoid':       row['medoid_metric'],
            'cluster_size': int(row['size']),
            'best_cc':      best_cc_map.get(cid, float('nan')),
        })
    reps_df = pd.DataFrame(reps_rows)
    reps_path = os.path.join(args.output_dir, 'ward_sem_reps.csv')
    reps_df.to_csv(reps_path, index=False)
    _tee(reps_path)
    log(f'  Saved ward_sem_reps.csv ({len(reps_df)} rows)')

    # Size histogram
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    ax.hist(sizes, bins=40, color='steelblue', edgecolor='white', lw=0.5)
    ax.set_xlabel('Cluster size (number of variables)', fontsize=13)
    ax.set_ylabel('Number of clusters', fontsize=13)
    ax.set_title(f'Semantic cluster size distribution (k={chosen_k}, '
                 f'model={args.model})', fontsize=13)
    ax.axvline(args.min_cluster_size - 0.5, color='red', ls='--', lw=1.5,
               label=f'Singleton threshold (<{args.min_cluster_size})')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, 'cluster_size_histogram.png'),
                dpi=150, bbox_inches='tight', facecolor='white')
    _tee(os.path.join(args.output_dir, 'cluster_size_histogram.png'))
    plt.close()

    log("")
    log("=" * 60)
    log(f"DONE.")
    log(f"  Model              : {args.model}", 2)
    log(f"  UMAP               : {'disabled' if args.umap_dims == 0 else f'{args.umap_dims}-dim'}", 2)
    log(f"  k chosen           : {chosen_k}", 2)
    log(f"  n_metrics          : {n}", 2)
    log(f"  Multi-member       : {chosen_k - n_singletons}", 2)
    log(f"  Singletons         : {n_singletons}", 2)
    log(f"  Outputs            : {args.output_dir}/", 2)
    log("=" * 60)


if __name__ == '__main__':
    main()
