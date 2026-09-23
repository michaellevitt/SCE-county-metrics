#!/usr/bin/env python3
"""Population-weighted Spearman CC, matching the method behind Table S8:
weighted-ECDF ranks (population-weighted) then weighted Pearson."""
import numpy as np, pandas as pd, re

DATA='BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
YC=[f'asedx_p_{y}' for y in range(2020,2025)]

def wrank(v,w):
    o=np.argsort(v,kind='mergesort'); vs,ws=v[o],w[o]
    cum=np.concatenate([[0.0],np.cumsum(ws)])[:-1]
    r=cum+0.5*ws
    # average ranks within ties
    out=np.empty_like(r); i=0
    while i<len(vs):
        j=i
        while j+1<len(vs) and vs[j+1]==vs[i]: j+=1
        out[i:j+1]=r[i:j+1].mean(); i=j+1
    res=np.empty_like(out); res[o]=out
    return res/w.sum()

def wpearson(x,y,w):
    wn=w/w.sum(); mx=wn@x; my=wn@y
    cx,cy=x-mx,y-my
    vx=wn@(cx*cx); vy=wn@(cy*cy)
    d=np.sqrt(vx*vy)
    return (wn@(cx*cy))/d if d>0 else np.nan

def main():
    mets=list(pd.read_csv('ward_sem_clean2_k120/ward_sem_metrics.csv')['metric'])
    need=set(mets+YC+['population_2019'])
    df=pd.read_csv(DATA,usecols=lambda c:c in need,low_memory=False)
    mets=[m for m in mets if m in df.columns]
    X=df[mets].apply(pd.to_numeric,errors='coerce').values.astype(float)
    Y=df[YC].values.astype(float); w=df['population_2019'].values.astype(float)
    X[~np.isfinite(X)]=np.nan; Y[~np.isfinite(Y)]=np.nan
    out=np.full((len(mets),5),np.nan)
    for k in range(5):
        yk=Y[:,k]
        base=np.isfinite(yk)&np.isfinite(w)&(w>0)
        for j in range(len(mets)):
            v=base&np.isfinite(X[:,j])
            if v.sum()<30: continue
            xs,ys,ws=X[v,j],yk[v],w[v]
            if xs.min()==xs.max() or ys.min()==ys.max(): continue
            out[j,k]=wpearson(wrank(xs,ws),wrank(ys,ws),ws)
        print(f'  year {2020+k} done',flush=True)
    r=pd.DataFrame(out,columns=YC); r.insert(0,'metric',mets)
    r.to_csv('full_w1.0/metric_x_death_spearman_1.0_0.csv',index=False)
    print('saved full_w1.0/metric_x_death_spearman_1.0_0.csv')

if __name__=='__main__': main()
