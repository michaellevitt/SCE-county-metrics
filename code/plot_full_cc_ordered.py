#!/usr/bin/env python3
"""
Complete metric x metric CC heatmap (SIGNED, not |CC|), with metrics ordered by
super-cluster -> semantic cluster -> within-cluster max|CC| (descending), i.e. the
order in metrics_by_cluster_ordered_*.tsv.

Thick black lines = super-cluster boundaries; thin grey lines = cluster boundaries.
Colour: diverging blue/white/red, symmetric about 0, saturating at +-cc-threshold.

Usage:
  python3 plot_full_cc_ordered.py \
    --order ward_sem_clean2_k120/metrics_by_cluster_ordered_w1.0.tsv \
    --cc-matrix full_w1.0/full_cc_ase0_p=1.0_0.csv \
    --cc-threshold 0.5 \
    --out ward_sem_clean2_k120/full_cc_heatmap_ordered_w1.0.png
"""
import argparse, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--order', required=True)
    ap.add_argument('--cc-matrix', required=True)
    ap.add_argument('--cc-threshold', type=float, default=0.5)
    ap.add_argument('--abs', action='store_true', help='plot |CC| (0..t, white->red) instead of signed CC')
    ap.add_argument('--out', required=True)
    a=ap.parse_args()

    od=pd.read_csv(a.order, sep='\t')          # already in desired order
    cc=pd.read_csv(a.cc_matrix, index_col=0)
    od=od[od['metric'].isin(cc.index)].reset_index(drop=True)
    n=len(od); print(f'{n} metrics ordered (signed CC)')
    metrics=od['metric'].tolist()
    M=cc.loc[metrics, metrics].to_numpy(dtype=float)
    np.fill_diagonal(M, 1.0)

    t=abs(a.cc_threshold)
    if a.abs:
        M=np.abs(M)
        cmap=mcolors.LinearSegmentedColormap.from_list('wr',[(0.0,'#FFFFFF'),(1.0,'#B2182B')])
        imkw=dict(vmin=0.0, vmax=t); cbticks=[0,t]; cblabel='|CC|'
    else:
        cmap=mcolors.LinearSegmentedColormap.from_list('bwr_custom',
            [(0.0,'#2166AC'),(0.5,'#FFFFFF'),(1.0,'#B2182B')])
        imkw=dict(vmin=-t, vmax=t); cbticks=[-t,0,t]; cblabel='Correlation coefficient (CC, signed)'

    fig,ax=plt.subplots(figsize=(26,26))
    im=ax.imshow(M, cmap=cmap, interpolation='none', aspect='equal', **imkw)

    sc=od['sc_id'].to_numpy(); cl=od['cluster'].to_numpy()
    cl_bnds=[i for i in range(1,n) if cl[i]!=cl[i-1]]
    sc_bnds=[i for i in range(1,n) if sc[i]!=sc[i-1]]
    for b in cl_bnds:
        ax.axhline(b-0.5, color='#888888', lw=0.3); ax.axvline(b-0.5, color='#888888', lw=0.3)
    for b in sc_bnds:
        ax.axhline(b-0.5, color='black', lw=1.4); ax.axvline(b-0.5, color='black', lw=1.4)

    # super-cluster names at band centres on the right
    starts=[0]+sc_bnds; ends=sc_bnds+[n]
    for s,e in zip(starts,ends):
        ax.text(n+6, (s+e)/2-0.5, f"SC{int(sc[s])}  {od['sc_name'].iloc[s]}",
                va='center', ha='left', fontsize=11, fontweight='bold')
    ax.set_xticks([]); ax.set_yticks([]); ax.set_xlim(-0.5,n-0.5); ax.set_ylim(n-0.5,-0.5)
    ax.set_title(f'Complete metric x metric {"|CC|" if a.abs else "CC (signed)"} — {n} metrics\n'
                 f'ordered by super-cluster, cluster, then within-cluster max|CC|; '
                 f'thick=super-cluster, thin=cluster; colour saturates at |CC|={t}', fontsize=14)
    cb=fig.colorbar(im, ax=ax, orientation='horizontal', fraction=0.03, pad=0.02, ticks=cbticks)
    cb.set_label(cblabel, fontsize=12)
    fig.savefig(a.out, dpi=140, bbox_inches='tight')
    print('Saved', a.out)

if __name__=='__main__':
    main()
