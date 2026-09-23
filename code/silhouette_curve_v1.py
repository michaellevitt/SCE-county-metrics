#!/usr/bin/env python3
"""
silhouette_curve_v1.py

Silhouette coefficient against number of clusters k, for the cleaned-name
sentence-transformer embeddings. Answers Frontiers Reviewer 1, major comment 6:
"the reported silhouette coefficient of 0.42 ... does not demonstrate that 120 is
the optimal number of clusters".

Reproduces the pipeline exactly (code/semantic_cluster_metrics_v2.py):
row-normalise, euclidean pdist, Ward linkage, fcluster maxclust, euclidean silhouette.
"""
import numpy as np, pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist
from sklearn.metrics import silhouette_score
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

E = np.load('ward_sem_clean2_k120/embeddings_normed.npy').astype(np.float64)
E = E / np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-10)
print('embeddings', E.shape)
Z = linkage(pdist(E, metric='euclidean'), method='ward')

ks = [2,3,5,8,10,15,20,30,40,50,60,70,80,90,100,110,120,130,140,150,175,200,
      225,250,275,300,350,400,450,500,550,600,700,800,900,1000]
rows = []
for k in ks:
    lab = fcluster(Z, k, criterion='maxclust')
    if len(set(lab)) < 2:
        continue
    s = silhouette_score(E, lab, metric='euclidean')
    rows.append((k, len(set(lab)), s))
    print(f'  k={k:5d}  clusters={len(set(lab)):5d}  silhouette={s:.4f}')
df = pd.DataFrame(rows, columns=['k', 'n_clusters', 'silhouette'])
df.to_csv('revision_analyses/D_silhouette_curve.csv', index=False)

# published values, for the cross-check
pub = pd.read_csv('ward_sem_clean2_k120/silhouette_scores.csv')
m = df.merge(pub, on='k', suffixes=('_mine', '_published'))
print('\ncross-check against ward_sem_clean2_k120/silhouette_scores.csv:')
print(m[['k', 'silhouette_mine', 'silhouette_published']].to_string(index=False))
print('max |difference|: %.2e' % (m.silhouette_mine - m.silhouette_published).abs().max())

# merge-height gaps: the dendrogram's own view of where to cut
n = len(Z) + 1
gap = [(k, Z[n-k, 2] - Z[n-k-1, 2]) for k in range(2, 400)]
g = pd.DataFrame(gap, columns=['k', 'merge_gap']).sort_values('merge_gap', ascending=False)
print('\nlargest dendrogram merge-height gaps (the "elbow" candidates):')
print(g.head(10).to_string(index=False))
g.to_csv('revision_analyses/D_merge_gaps.csv', index=False)

fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
a = ax[0]
a.plot(df.k, df.silhouette, '-o', ms=3.5, color='#4C72B0')
a.axvline(120, color='#C44E52', lw=2)
a.annotate('k = 120\nchosen\n(0.423)', xy=(120, 0.423), xytext=(175, 0.33),
           color='#C44E52', fontsize=9,
           arrowprops=dict(arrowstyle='->', color='#C44E52'))
a.set_xscale('log'); a.set_xlabel('number of clusters k (log scale)')
a.set_ylabel('silhouette coefficient')
a.set_title('A  Silhouette rises monotonically: it cannot select k',
            loc='left', fontsize=10.5, weight='bold')
b = ax[1]
gg = pd.DataFrame(gap, columns=['k', 'merge_gap'])
b.plot(gg.k.values, gg.merge_gap.values, color='#55A868', lw=1)
b.set_yscale('log')
b.axvline(120, color='#C44E52', lw=2)
b.text(128, b.get_ylim()[1]*0.8, 'k = 120', color='#C44E52', fontsize=9)
b.set_xlim(2, 300); b.set_xlabel('number of clusters k')
b.set_ylabel('gap between successive merge heights')
b.set_title('B  Dendrogram merge gaps', loc='left', fontsize=10.5, weight='bold')
fig.suptitle('Choice of k for the semantic clustering of 2,745 variable names', fontsize=11)
fig.tight_layout()
fig.savefig('revision_analyses/FigS_silhouette_vs_k.png', dpi=200)
print('\nSaved revision_analyses/FigS_silhouette_vs_k.png')
