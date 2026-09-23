#!/usr/bin/env python3
"""
geography_and_map_v1.py

Frontiers Reviewer 2, points 4 and 5: describe where the advantaged and
disadvantaged counties are, and put the result on a map.

The advantage index is built only from variables the screen already identified,
so it introduces no new analyst choice. We take every variable reaching
|CC| > 0.45 in a socioeconomic or demographic super-cluster, standardize it
across counties, flip the sign of the positively correlated ones so that a high
score always means lower excess death, and average. The index is then reported
in population-weighted quintiles.

Census region, division and the 2013 rural-urban continuum code come from the
AHRF variables already in the predictor set (f04439, f04440, f0002013). They
were rescaled to 0-9999 along with everything else, so they are mapped back to
their original integer levels here.

County boundaries: data/raw/geojson-counties-fips.json, the public Plotly
county file keyed on 5-digit FIPS. Drawn with matplotlib alone, in an Albers
equal-area projection, so no geospatial packages are needed.

Usage:
    python3 code/geography_and_map_v1.py
"""
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import TwoSlopeNorm

DATA    = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
METLIST = 'ward_sem_clean2_k120/ward_sem_metrics.csv'
ASSIGN  = 'ward_sem_clean2_k120/sem_sc_assignments.csv'
PROD    = 'full_w1.0/metric_x_death_cc_1.0_0.csv'
GEO     = 'data/raw/geojson-counties-fips.json'
DEATHS  = 'data/raw/usa-county-result.10Feb26.csv'
OUTDIR  = 'geography'
YEARS   = list(range(2020, 2025))
YCOLS   = [f'asedx_p_{y}' for y in YEARS]
WCOL    = 'population_2019'

# Super-clusters 1, 2, 3, 5, 8 are the socioeconomic and demographic family;
# 4, 6, 7, 9, 10, 11 are the health-system family. Same split as Table 1.
SOCIO_SC = [1, 2, 3, 5, 8]

REGION = {1: 'Northeast', 2: 'Midwest', 3: 'South', 4: 'West'}
DIVISION = {1: 'New England', 2: 'Middle Atlantic', 3: 'East North Central',
            4: 'West North Central', 5: 'South Atlantic', 6: 'East South Central',
            7: 'West South Central', 8: 'Mountain', 9: 'Pacific'}
STATE = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO',
    '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI',
    '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY',
    '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN',
    '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
    '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH',
    '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD',
    '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA',
    '54': 'WV', '55': 'WI', '56': 'WY'}


def decode(col, nlevels):
    """Undo the 0-9999 rescaling of an integer code variable."""
    return np.rint(col / 9999.0 * nlevels).astype('float')


def wmean(v, w):
    m = np.isfinite(v) & np.isfinite(w)
    return float(np.sum(v[m] * w[m]) / np.sum(w[m])) if m.any() else np.nan


def albers(lon, lat):
    """Albers equal-area conic, USA standard parallels 29.5 and 45.5 N."""
    lon0, lat0, p1, p2 = -96.0, 37.5, 29.5, 45.5
    d = np.pi / 180.0
    lon, lat = lon * d, lat * d
    lon0, lat0, p1, p2 = lon0 * d, lat0 * d, p1 * d, p2 * d
    n = 0.5 * (np.sin(p1) + np.sin(p2))
    C = np.cos(p1) ** 2 + 2 * n * np.sin(p1)
    rho = np.sqrt(C - 2 * n * np.sin(lat)) / n
    rho0 = np.sqrt(C - 2 * n * np.sin(lat0)) / n
    th = n * (lon - lon0)
    return rho * np.sin(th), rho0 - rho * np.cos(th)


def polygons(feat):
    g = feat['geometry']
    if g is None:
        return []
    cs = g['coordinates']
    rings = cs if g['type'] == 'Polygon' else [r for poly in cs for r in poly]
    out = []
    for r in rings:
        a = np.asarray(r, dtype=float)
        if a.ndim == 2 and a.shape[0] >= 3:
            out.append(a[:, :2])
    return out


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    mets = list(pd.read_csv(METLIST)['metric'])
    sem = pd.read_csv(METLIST)[['metric', 'semantic_cluster_id']]
    assign = pd.read_csv(ASSIGN)
    sem = sem.merge(assign, left_on='semantic_cluster_id', right_on='sem100', how='left')

    cc = pd.read_csv(PROD)
    V = cc[YCOLS].values
    ab = np.abs(V)
    with np.errstate(all='ignore'):
        idx = np.nanargmax(np.where(np.isfinite(ab), ab, -1), axis=1)
    cc = cc.assign(maxabs=ab[np.arange(len(cc)), idx],
                   signed=V[np.arange(len(cc)), idx])
    sem = sem.merge(cc[['metric', 'maxabs', 'signed']], on='metric', how='left')

    strong = sem[(sem.maxabs > 0.45) & sem.sc_id.isin(SOCIO_SC)]
    print('advantage index built from %d strong-band socioeconomic and '
          'demographic variables' % len(strong))
    print('  of which %d are negatively and %d positively correlated'
          % ((strong.signed < 0).sum(), (strong.signed > 0).sum()))

    need = set(mets + YCOLS + [WCOL, 'fips', 'POPPCT_RUR',
                               'f04439', 'f04440', 'f0002013', 'f00011'])
    df = pd.read_csv(DATA, usecols=lambda c: c in need, low_memory=False)
    df['fips5'] = df['fips'].astype(str).str.zfill(5)
    w = df[WCOL].values.astype(float)

    Z = df[list(strong.metric)].apply(pd.to_numeric, errors='coerce').values.astype(float)
    mu = np.nanmean(Z, axis=0)
    sd = np.nanstd(Z, axis=0)
    sd[sd == 0] = np.nan
    Zs = (Z - mu) / sd
    Zs *= -np.sign(strong.signed.values)[None, :]       # high score = advantaged
    df['advantage'] = np.nanmean(Zs, axis=1)

    df['region'] = decode(df['f04439'].values, 4)
    df['division'] = decode(df['f04440'].values, 9)
    df['rucc'] = decode(df['f0002013'].values, 9)
    df['state'] = df['fips5'].str[:2].map(STATE)
    df['metro'] = np.where(df['rucc'] <= 3, 'Metropolitan', 'Non-metropolitan')
    df['xd2020_21'] = df[['asedx_p_2020', 'asedx_p_2021']].mean(axis=1)

    # CDC disclosure rule: do not publish a county aggregate, or a rate computed
    # from it, whose numerator is 9 deaths or fewer. The mapped measure pools
    # 2020 and 2021, so the test is on the pooled count.
    src = pd.read_csv(DEATHS, dtype={'fips': str}, low_memory=False)
    src = src[src.age_group == 'all']
    src['fips5'] = src['fips'].astype(str).str.zfill(5)
    pooled = (src[src.year.astype(str).isin(['2020', '2021'])]
              .groupby('fips5')['deaths'].sum())
    df['deaths_2020_21'] = df['fips5'].map(pooled)
    df['disclosable'] = df['deaths_2020_21'] > 9
    n_sup = int((~df['disclosable']).sum())
    print('disclosure mask: %d counties have 9 or fewer pooled 2020-2021 deaths '
          'and are not mapped' % n_sup)

    # population-weighted quintiles of the advantage index
    o = np.argsort(df['advantage'].values)
    cw = np.cumsum(w[o]) / w.sum()
    q = np.empty(len(df), dtype=int)
    q[o] = np.clip((cw * 5).astype(int), 0, 4)
    df['quintile'] = q + 1
    lab = {1: 'Q1 most disadvantaged', 2: 'Q2', 3: 'Q3', 4: 'Q4',
           5: 'Q5 most advantaged'}

    rows = []
    for k in range(1, 6):
        s = df[df.quintile == k]
        ws = s[WCOL].values
        rows.append(dict(
            quintile=lab[k], counties=len(s),
            population_m=round(ws.sum() / 1e6, 1),
            excess_2020_21=round(wmean(s['xd2020_21'].values, ws), 4),
            excess_2020=round(wmean(s['asedx_p_2020'].values, ws), 4),
            excess_2021=round(wmean(s['asedx_p_2021'].values, ws), 4),
            excess_2022_24=round(wmean(s[['asedx_p_2022', 'asedx_p_2023',
                                          'asedx_p_2024']].mean(axis=1).values, ws), 4),
            pct_rural=round(wmean(s['POPPCT_RUR'].values, ws), 1),
            pct_nonmetro_counties=round(100 * (s['rucc'] > 3).mean(), 1),
            top_region=REGION.get(s.groupby('region')[WCOL].sum().idxmax(), '?'),
        ))
    qt = pd.DataFrame(rows)
    print('\nExcess death by population-weighted quintile of the advantage index')
    print(qt.to_string(index=False))
    qt.to_csv(f'{OUTDIR}/quintile_table.csv', index=False)

    # regional and division composition of the extreme quintiles
    comp = []
    for name, col, dec in [('Census region', 'region', REGION),
                           ('Census division', 'division', DIVISION)]:
        for code, cname in dec.items():
            s = df[df[col] == code]
            if not len(s):
                continue
            comp.append(dict(
                grouping=name, area=cname, counties=len(s),
                population_m=round(s[WCOL].sum() / 1e6, 1),
                excess_2020_21=round(wmean(s['xd2020_21'].values, s[WCOL].values), 4),
                mean_advantage=round(wmean(s['advantage'].values, s[WCOL].values), 3),
                pct_in_Q1=round(100 * wmean((s.quintile == 1).values.astype(float),
                                            s[WCOL].values), 1)))
    ct = pd.DataFrame(comp)
    print('\nBy Census region and division')
    print(ct.to_string(index=False))
    ct.to_csv(f'{OUTDIR}/region_division_table.csv', index=False)

    # metropolitan split and the rural-urban continuum
    mt = []
    for name, sub in [('Metropolitan (continuum 1-3)', df[df.rucc <= 3]),
                      ('Non-metropolitan (continuum 4-9)', df[df.rucc > 3])]:
        mt.append(dict(group=name, counties=len(sub),
                       population_m=round(sub[WCOL].sum() / 1e6, 1),
                       excess_2020_21=round(wmean(sub['xd2020_21'].values,
                                                  sub[WCOL].values), 4),
                       mean_advantage=round(wmean(sub['advantage'].values,
                                                  sub[WCOL].values), 3)))
    mtt = pd.DataFrame(mt)
    print('\nMetropolitan split')
    print(mtt.to_string(index=False))
    mtt.to_csv(f'{OUTDIR}/metro_table.csv', index=False)

    # state extremes
    st = df.groupby('state').apply(
        lambda s: pd.Series(dict(
            counties=len(s), population_m=round(s[WCOL].sum() / 1e6, 1),
            excess_2020_21=round(wmean(s['xd2020_21'].values, s[WCOL].values), 4),
            mean_advantage=round(wmean(s['advantage'].values, s[WCOL].values), 3))),
        include_groups=False).sort_values('excess_2020_21', ascending=False)
    st.to_csv(f'{OUTDIR}/state_table.csv')
    print('\nHighest and lowest states by 2020-2021 excess death')
    print(pd.concat([st.head(8), st.tail(8)]).to_string())

    # correlation between the index and the outcome, for the caption
    for y in YEARS:
        v = df[f'asedx_p_{y}'].values
        m = np.isfinite(v) & np.isfinite(df['advantage'].values)
        a, b, ww = df['advantage'].values[m], v[m], w[m]
        ma, mb = np.average(a, weights=ww), np.average(b, weights=ww)
        r = (np.average((a - ma) * (b - mb), weights=ww)
             / np.sqrt(np.average((a - ma) ** 2, weights=ww)
                       * np.average((b - mb) ** 2, weights=ww)))
        print('  advantage index vs excess death %d: weighted CC %+.3f' % (y, r))

    # ------------------------------ the map ------------------------------
    # Alaska and Hawaii are moved and rescaled into the conventional inset
    # positions below the southwest, so the lower 48 are not reduced to a strip.
    # Territories are not in the analysis set and are not drawn.
    gj = json.load(open(GEO))
    verts, order = [], []
    for ft in gj['features']:
        fid = str(ft.get('id', '')).zfill(5)
        st = fid[:2]
        if st not in STATE:
            continue
        for ring in polygons(ft):
            x, y = albers(ring[:, 0], ring[:, 1])
            if st == '02':
                x, y = 0.36 * (x + 0.62) - 0.31, 0.36 * (y - 0.47) - 0.22
            elif st == '15':
                x, y = x + 0.63, y - 0.09
            verts.append(np.column_stack([x, y]))
            order.append(fid)
    order = np.asarray(order)
    print('\nmap: %d rings over %d counties' % (len(verts), len(set(order))))

    fig, axes = plt.subplots(2, 1, figsize=(9.2, 11.0))
    panels = [
        ('A  Excess-death proportion, mean of 2020 and 2021', 'xd2020_21',
         'RdBu_r', TwoSlopeNorm(vmin=-0.10, vcenter=0.20, vmax=0.50),
         'excess deaths as a proportion of the county baseline'),
        ('B  Advantage index, high score = socioeconomically advantaged',
         'advantage', 'BrBG', TwoSlopeNorm(vmin=-2.0, vcenter=0.0, vmax=2.0),
         'standardized index, population-weighted mean zero'),
    ]
    for ax, (title, col, cmap, norm, cbl) in zip(axes, panels):
        vals = df.set_index('fips5')[col]
        if col == 'xd2020_21':
            vals = vals.where(df.set_index('fips5')['disclosable'])
        c = vals.reindex(order).values.astype(float)
        pc = PolyCollection(verts, array=np.ma.masked_invalid(c), cmap=cmap,
                            norm=norm, edgecolors='white', linewidths=0.06)
        pc.set_clim(norm.vmin, norm.vmax)
        ax.add_collection(pc)
        ax.set_xlim(-0.42, 0.62)
        ax.set_ylim(-0.30, 0.31)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(title, fontsize=12, loc='left', pad=4)
        cb = fig.colorbar(pc, ax=ax, orientation='horizontal', fraction=0.030,
                          pad=0.02, shrink=0.55, anchor=(0.5, 1.0))
        cb.set_label(cbl, fontsize=9.5)
        cb.ax.tick_params(labelsize=9)
        n_missing = int(np.isnan(vals.reindex(sorted(set(order))).values).sum())
        note = ('Alaska and Hawaii are insets, not to scale.  '
                'Grey: no value mapped (%d counties).' % n_missing)
        if col == 'xd2020_21':
            note += '\nCounties with 9 or fewer pooled deaths are withheld.'
        ax.text(0.99, 0.02, note, transform=ax.transAxes, ha='right',
                va='bottom', fontsize=8, color='0.35')
    fig.tight_layout()
    for ext, dpi in [('png', 300), ('pdf', None)]:
        fig.savefig(f'{OUTDIR}/figS9_county_maps.{ext}',
                    dpi=dpi, bbox_inches='tight')
    print('wrote %s/figS9_county_maps.png' % OUTDIR)

    df[['fips5', 'state', 'region', 'division', 'rucc', 'POPPCT_RUR',
        WCOL, 'advantage', 'quintile', 'xd2020_21'] + YCOLS].to_csv(
        f'{OUTDIR}/county_advantage_index.csv', index=False)
    strong[['metric', 'signed', 'sc_id', 'sc_name']].to_csv(
        f'{OUTDIR}/advantage_index_components.csv', index=False)
    print('wrote %s/' % OUTDIR)


if __name__ == '__main__':
    main()
