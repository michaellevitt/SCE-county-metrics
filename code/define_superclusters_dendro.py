#!/usr/bin/env python3
"""
Define super-clusters by cutting the cluster-label cosine dendrogram into K groups.

The 120 cluster-label embeddings are clustered (Ward linkage on cosine distance);
cutting at K gives contiguous, balanced super-clusters. Groups are renumbered in
dendrogram-leaf order (SC1 = topmost branch). Curated names are applied for the
standard K=11 cut; other K values get provisional "SCxx" names.

Writes:
  sem_sc_assignments.csv  (sem100, sc_id, sc_name)
  sem_sc_names.csv        (sc_id, sc_name, sc_name_short)

Usage:
  python3 define_superclusters_dendro.py \
    --sem-metrics ward_sem_clean2_k120/ward_sem_metrics.csv \
    --embeddings  ward_sem_clean2_k120/sc_label_embeddings.npy \
    --k 11 \
    --out-assign  ward_sem_clean2_k120/sem_sc_assignments.csv \
    --out-names   ward_sem_clean2_k120/sem_sc_names.csv
"""
import argparse, numpy as np, pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import squareform

# Curated names for the standard K=11 Ward cut (renumbered top->bottom).
NAMES_K11 = {
    1:  "Race, Ethnicity and Population by Age",
    2:  "Geography, Environment and Housing",
    3:  "Socioeconomic, Insurance and Demographic Characteristics",
    4:  "Vital Statistics and Total Physician Counts",
    5:  "Poverty, Insurance Coverage and Public Programs",
    6:  "Primary Care, Generalist and Diagnostic Physicians",
    7:  "Surgical, Procedural and Specialty Physicians",
    8:  "Commuting and Industry Employment",
    9:  "Aggregate Physician and Facility Totals",
    10: "Hospital Telehealth and Advanced Imaging Services",
    11: "Hospital Capacity and Nursing and Allied Staffing",
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sem-metrics', required=True)
    ap.add_argument('--embeddings',  required=True, help='cluster-label embeddings (sc_label_embeddings.npy)')
    ap.add_argument('--k', type=int, default=11)
    ap.add_argument('--out-assign', required=True)
    ap.add_argument('--out-names',  required=True)
    a = ap.parse_args()

    cids = sorted(pd.read_csv(a.sem_metrics)['semantic_cluster_id'].unique())
    emb  = np.load(a.embeddings)
    if emb.shape[0] != len(cids):
        raise SystemExit(f'embeddings rows {emb.shape[0]} != #clusters {len(cids)}')
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    Z = linkage(squareform(1 - emb @ emb.T, checks=False), 'ward')
    leaves = dendrogram(Z, no_plot=True)['leaves']
    fc = fcluster(Z, a.k, 'maxclust')
    # renumber super-clusters in dendrogram-leaf order (SC1 = top)
    seen = {}
    for li in leaves:
        g = fc[li]
        if g not in seen:
            seen[g] = len(seen) + 1
    new_sc = {cids[li]: seen[fc[li]] for li in leaves}

    names = NAMES_K11 if a.k == 11 else {}
    def nm(s): return names.get(s, f'SC{s:02d}')

    assign = pd.DataFrame({'sem100': cids, 'sc_id': [new_sc[c] for c in cids]})
    assign['sc_name'] = assign['sc_id'].map(nm)
    assign.sort_values(['sc_id', 'sem100']).to_csv(a.out_assign, index=False)

    K = sorted(set(new_sc.values()))
    pd.DataFrame({'sc_id': K, 'sc_name': [nm(s) for s in K],
                  'sc_name_short': [nm(s) for s in K]}).to_csv(a.out_names, index=False)
    print(f'Wrote {a.out_assign} and {a.out_names} (Ward cut K={a.k}, {len(K)} super-clusters)')

if __name__ == '__main__':
    main()
