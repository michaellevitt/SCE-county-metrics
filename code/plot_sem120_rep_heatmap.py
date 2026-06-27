#!/usr/bin/env python3
"""
120x120 cluster-representative CC heatmap for the SEM k120 clustering.

Each of the 120 semantic clusters is represented by the metric with the
HIGHEST |CC| (not the centroid/medoid). The heatmap is the metric x metric
correlation (from the full CC matrix) between those 120 representatives,
ordered by super-cluster then semantic cluster, with super-cluster boundary
lines. Colour scale saturates at +-cc-threshold (default 0.5).

Usage:
  python3 plot_sem120_rep_heatmap.py \
    --top  ward_sem_clean2_k120/top_metric_per_cluster_2020_2024_w1.0.tsv \
    --cc-matrix full_w1.0/full_cc_ase0_p=1.0_0.csv \
    --cc-threshold 0.5 \
    --out  ward_sem_clean2_k120/sem120_rep_heatmap_w1.0.png
"""
import argparse, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--top', required=True, help='top_metric_per_cluster tsv (highest-|CC| metric per cluster)')
    ap.add_argument('--metric', choices=['cc','cosine'], default='cc',
                    help='cc = metric x metric death-CC; cosine = name-embedding cosine similarity')
    ap.add_argument('--cc-matrix', default=None, help='square metric x metric CC matrix CSV (for --metric cc)')
    ap.add_argument('--embeddings', default=None, help='embeddings_normed.npy (for --metric cosine)')
    ap.add_argument('--sem-metrics', default=None, help='ward_sem_metrics.csv giving embedding row order (cosine)')
    ap.add_argument('--cc-threshold', type=float, default=0.5)
    ap.add_argument('--abs', action='store_true', help='(cc mode) plot |CC| 0..t white->red instead of signed')
    ap.add_argument('--out', required=True)
    a=ap.parse_args()

    top=pd.read_csv(a.top, sep='\t')
    # order: super-cluster then semantic cluster
    top=top.sort_values(['sc_id','cluster']).reset_index(drop=True)
    reps=top['metric'].tolist(); n=len(reps)
    print(f'{n} cluster representatives (highest-|CC| metric per cluster)')

    cmap=mcolors.LinearSegmentedColormap.from_list('bwr_custom',
        [(0.0,'#2166AC'),(0.5,'#FFFFFF'),(1.0,'#B2182B')])

    if a.metric=='cc':
        cc=pd.read_csv(a.cc_matrix, index_col=0)
        miss=[m for m in reps if m not in cc.index]
        if miss: raise SystemExit(f'reps missing from CC matrix: {miss[:5]}')
        M=cc.loc[reps, reps].to_numpy(dtype=float); np.fill_diagonal(M, 1.0)
        t=abs(a.cc_threshold)
        if a.abs:
            M=np.abs(M)
            cmap=mcolors.LinearSegmentedColormap.from_list('wr',[(0.0,'#FFFFFF'),(1.0,'#B2182B')])
            imkw=dict(vmin=0.0, vmax=t); cbticks=[0,t]
            cblabel='|CC|'; what='pairwise |CC|'; scale_note=f'colour saturates at |CC|={t}'
        else:
            imkw=dict(vmin=-t, vmax=t); cbticks=[-t,0,t]
            cblabel='Correlation coefficient (CC)'; what='pairwise death-CC'
            scale_note=f'colour saturates at |CC|={t}'
    else:  # cosine of name embeddings between representatives
        E=np.load(a.embeddings)
        wm=pd.read_csv(a.sem_metrics)['metric'].tolist()
        idx={m:i for i,m in enumerate(wm)}
        miss=[m for m in reps if m not in idx]
        if miss: raise SystemExit(f'reps missing from embeddings: {miss[:5]}')
        Er=E[[idx[m] for m in reps]]            # rows already L2-normalised
        M=Er@Er.T; np.fill_diagonal(M, 1.0)
        off=M[~np.eye(n,dtype=bool)]
        vc=round(float(np.median(off)),3); vmx=round(float(np.percentile(off,95)),3)
        imkw=dict(norm=mcolors.TwoSlopeNorm(vmin=0.0, vcenter=vc, vmax=vmx))
        cbticks=[0,vc,vmx]; cblabel='Cosine similarity (name embedding)'
        what='pairwise semantic cosine'
        scale_note=f'white = median cosine {vc}; red ≥ {vmx} (95th pct)'

    fig,ax=plt.subplots(figsize=(30,30))
    im=ax.imshow(M, cmap=cmap, interpolation='none', aspect='equal', **imkw)

    # super-cluster boundaries
    sc=top['sc_id'].to_numpy()
    bnds=[i for i in range(1,n) if sc[i]!=sc[i-1]]
    for bpos in bnds:
        ax.axhline(bpos-0.5, color='k', lw=1.2); ax.axvline(bpos-0.5, color='k', lw=1.2)

    # (4) super-cluster NAMES along the right edge, centred on each band
    starts=[0]+bnds; ends=bnds+[n]
    for s,e in zip(starts,ends):
        ax.text(n-0.3, (s+e)/2-0.5, f"SC{int(sc[s])}  {top['sc_name'].iloc[s]}",
                va='center', ha='left', fontsize=11, fontweight='bold')

    # (1)(3) full, untruncated cluster labels on left y-axis at 2x font (8.4pt)
    ylab=[f"C{int(r.cluster)}  {r.cluster_label}" for r in top.itertuples()]
    ax.set_yticks(range(n)); ax.set_yticklabels(ylab, fontsize=12.6)
    # (2) colour a label red when its representative has |CC| > 0.3
    redmask=(top['max_abs_cc']>0.3).tolist()
    for lab_obj,isred in zip(ax.get_yticklabels(), redmask):
        lab_obj.set_color('#C00000' if isred else 'black')
    # (5) no cluster numbers on the x-axis
    ax.set_xticks([])
    ax.set_xlim(-0.5, n-0.5)

    ax.set_title(f'120 SEM-cluster representatives (highest-|CC| variable each) — {what}\n'
                 f'ordered by super-cluster then cluster; red label = representative |CC| > 0.3; '
                 f'{scale_note}', fontsize=13)
    cb=fig.colorbar(im, ax=ax, orientation='horizontal', fraction=0.035, pad=0.03, ticks=cbticks)
    cb.set_label(cblabel, fontsize=11)
    fig.savefig(a.out, dpi=150, bbox_inches='tight')
    print('Saved', a.out)

if __name__=='__main__':
    main()
