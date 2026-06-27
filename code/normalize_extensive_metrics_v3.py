#!/usr/bin/env python3
"""
normalize_extensive_metrics.py  v3 -- WITH VERIFICATION + PRE-PANDEMIC CAUSE AVERAGES

Reads the input CSV (--input) and an optional NEW2 file (--new2) containing
cause-specific excess death columns (pattern: YYYY_CauseName_AGEGROUP).

Main steps (same as v2):
  Normalizes EXTENSIVE metrics by population_2019, then rescales to max=9999.
  INTENSIVE columns get max-9999 rescaling but NO population division.
  LAND, META, OTHER columns are untouched.

NEW in v3:
  If --new2 is provided, compute 2017-2019 average per cause x age group and
  append as new INTENSIVE columns named {Cause}_asedx_p_17-19_{AGEGROUP}.
  inf values in cause columns are set to 0 (genuine zero excess death rate)
  before averaging. NaN values (truly missing) are excluded from nanmean.
  If all three years are NaN the result is NaN, imputed with column mean.
  New columns are rescaled to 0-9999 (INTENSIVE treatment, no pop division).

Arguments:
  --input FILE           Input CSV path (default: hardcoded INPUT_FILE)
  --output FILE          Output CSV path (default: hardcoded OUTPUT_FILE)
  --new2 FILE            NEW2 CSV or CSV.GZ with cause columns (optional)
  --classification FILE  Classification CSV (default: hardcoded CLASSIFICATION_FILE)

VERIFICATION CHECKS:
  1. Population column sanity
  2. Column matching between classification and data
  3. Pre-normalization correlation with population
  4. Post-normalization correlation with population (THE KEY CHECK)
  5. Value distribution sanity (max, negatives, NaN)
  6. Hand-check sample metrics
  7. Unclassified columns truly untouched
  8. NEW: Pre-pandemic cause column summary (counts, NaN, inf->0 replacements)
"""

import pandas as pd
import numpy as np
import re
import sys
import os
import sys
import argparse

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


# ================================================================
# CONFIGURATION DEFAULTS
# ================================================================
DEFAULT_INPUT_FILE  = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NEW.csv'
DEFAULT_OUTPUT_FILE = 'BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv'
DEFAULT_CLASSIFICATION_FILE = 'hub_members_extensive_intensive.csv'
POP_COLUMN = 'population_2019'
MAX_VAL = 9999
CAUSE_PATTERN = re.compile(r'^(\d{4})_(.+)_(ALL|GE65|LT65)$')
PRE_YEARS = ('2017', '2018', '2019')

# ================================================================
# ARGUMENT PARSING
# ================================================================
parser = argparse.ArgumentParser(description='Normalize extensive metrics v3')
parser.add_argument('--input',          default=DEFAULT_INPUT_FILE)
parser.add_argument('--output',         default=DEFAULT_OUTPUT_FILE)
parser.add_argument('--new2',           default=None, help='NEW2 file with cause columns')
parser.add_argument('--classification', default=DEFAULT_CLASSIFICATION_FILE)
parser.add_argument('--explain',        default='data/BEN_MERGED_MEASURES_explain_extended_2745.csv',
                    help='metric->explain CSV; used to fallback-classify f-code columns absent '
                         'from the classification file (rate/share/median -> INTENSIVE, else EXTENSIVE)')
parser.add_argument('--peryear-pop',     default=None,
                    help='OPTIONAL: county population-by-year CSV (first col = fips, cols pop_YYYY). '
                         'When given WITH --metric-year, each EXTENSIVE metric is divided by the '
                         "population of its OWN year instead of the single '" + POP_COLUMN + "' column.")
parser.add_argument('--metric-year',     default=None,
                    help='OPTIONAL: metric->pop_year map CSV (cols: metric, pop_year). Required '
                         'with --peryear-pop. Any EXTENSIVE f-code absent from the map falls back '
                         "to its f-code year suffix; if that pop year is unavailable, to " + POP_COLUMN + ".")
args = parser.parse_args()

INPUT_FILE          = args.input
OUTPUT_FILE         = args.output
CLASSIFICATION_FILE = args.classification
EXPLAIN_FILE        = args.explain
NEW2_FILE           = args.new2

# ================================================================
# Load classification
# ================================================================
print("=" * 70)
print("STEP 1: Loading classifications")
print("=" * 70)
classif = pd.read_csv(CLASSIFICATION_FILE)
extensive_set = set(classif.loc[classif['classification'] == 'EXTENSIVE', 'metric'])
intensive_set = set(classif.loc[classif['classification'] == 'INTENSIVE', 'metric'])
land_set      = set(classif.loc[classif['classification'] == 'LAND', 'metric'])
meta_set      = set(classif.loc[classif['classification'] == 'META', 'metric'])

print(f"  EXTENSIVE: {len(extensive_set)}")
print(f"  INTENSIVE: {len(intensive_set)}")
print(f"  LAND:      {len(land_set)}")
print(f"  META:      {len(meta_set)}")

# ================================================================
# Load data
# ================================================================
print(f"\n{'=' * 70}")
print("STEP 2: Loading data")
print("=" * 70)
df = pd.read_csv(INPUT_FILE, low_memory=False)
print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} columns")

if POP_COLUMN not in df.columns:
    print(f"FATAL: '{POP_COLUMN}' not found in columns")
    sys.exit(1)

pop = pd.to_numeric(df[POP_COLUMN], errors='coerce')

# ================================================================
# OPTIONAL: per-year population (clean own-year re-normalization)
# ================================================================
PERYEAR_ACTIVE = bool(args.peryear_pop and args.metric_year)
peryear_div = {}        # year(int) -> aligned pop Series (index = df rows), fallback-filled
metric_pop_year = {}    # metric -> int year
if args.peryear_pop and not args.metric_year:
    print("FATAL: --peryear-pop requires --metric-year"); sys.exit(1)
if PERYEAR_ACTIVE:
    print(f"\n{'=' * 70}")
    print("PER-YEAR NORMALIZATION ENABLED (own-year county population)")
    print("=" * 70)
    _popyr = pd.read_csv(args.peryear_pop)
    _fipscol = _popyr.columns[0]
    _popyr[_fipscol] = pd.to_numeric(_popyr[_fipscol], errors='coerce')
    _popyr = _popyr.set_index(_fipscol)
    _fips = pd.to_numeric(df['fips'], errors='coerce')
    for _c in _popyr.columns:
        m = re.match(r'pop_(\d{4})$', str(_c))
        if not m:
            continue
        y = int(m.group(1))
        # align to df row order by fips; per-county fallback to population_2019 where missing/<=0
        s = _fips.map(_popyr[_c]).astype(float)
        s = s.where(s > 0, other=pop.values)
        peryear_div[y] = pd.Series(s.values, index=df.index)
    print(f"  Loaded population for years: {sorted(peryear_div)}")
    _my = pd.read_csv(args.metric_year)
    metric_pop_year = {str(r['metric']): int(r['pop_year']) for _, r in _my.iterrows()
                       if pd.notna(r['pop_year'])}
    print(f"  Metric->year map: {len(metric_pop_year)} metrics")

# ================================================================
# CHECK 1: Population column sanity
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 1: Population column sanity")
print("=" * 70)
print(f"  N rows:         {len(pop)}")
print(f"  NaN count:      {pop.isna().sum()}")
print(f"  Zero count:     {(pop == 0).sum()}")
print(f"  Negative count: {(pop < 0).sum()}")
print(f"  Min:            {pop.min():.0f}")
print(f"  Median:         {pop.median():.0f}")
print(f"  Max:            {pop.max():.0f}")

bad_pop = pop.isna() | (pop <= 0)
if bad_pop.sum() > 0:
    print(f"  WARNING: {bad_pop.sum()} counties with bad population -- "
          f"these will get NaN for extensive metrics")
    bad_fips = df.loc[bad_pop, 'fips'].tolist()
    print(f"  FIPS: {bad_fips[:10]}{'...' if len(bad_fips)>10 else ''}")

# ================================================================
# CHECK 2: Column matching
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 2: Column matching between classification and data")
print("=" * 70)

all_cols = set(df.columns)

# Fallback: classify f-code columns absent from the classification file so they are not
# silently left raw (unnormalized). Rate/share/ratio/median/average/index/per-capita
# language -> INTENSIVE; otherwise EXTENSIVE (population-scaling count).
import os, re as _re
_explain = {}
if EXPLAIN_FILE and os.path.exists(EXPLAIN_FILE):
    _ex = pd.read_csv(EXPLAIN_FILE)
    _ecol = 'explain' if 'explain' in _ex.columns else _ex.columns[1]
    _explain = dict(zip(_ex['metric'].astype(str), _ex[_ecol].astype(str)))
_INT_KW = [r'percent', r'pct', r'\brate\b', r'density', r'per[_ ]?capita', r'ratio',
           r'median', r'average', r'\bmean\b', r'%', r'_per_', r'\bper\b', r'\bindex\b']
_already = extensive_set | intensive_set | land_set | meta_set
_fb_ext, _fb_int = [], []
for _col in df.columns:
    if _col in _already or not _re.fullmatch(r'f\d{7}', str(_col)):
        continue
    _el = _explain.get(_col, '').lower()
    if any(_re.search(kw, _el) for kw in _INT_KW):
        intensive_set.add(_col); _fb_int.append(_col)
    else:
        extensive_set.add(_col); _fb_ext.append(_col)
print(f"  Fallback-classified absent f-codes: {len(_fb_ext)} EXTENSIVE + {len(_fb_int)} INTENSIVE")

ext_cols = sorted(all_cols & extensive_set)
int_cols = sorted(all_cols & intensive_set)
lnd_cols = sorted(all_cols & land_set)
met_cols = sorted(all_cols & meta_set)

# Only normalize metrics whose names start with f followed by a digit (f-codes)
_fcode = re.compile(r'^f\d')
ext_skip = [c for c in ext_cols if not _fcode.match(c)]
int_skip = [c for c in int_cols if not _fcode.match(c)]
ext_cols = [c for c in ext_cols if _fcode.match(c)]
int_cols = [c for c in int_cols if _fcode.match(c)]
if ext_skip or int_skip:
    print(f"  Skipping {len(ext_skip)} EXTENSIVE + {len(int_skip)} INTENSIVE "
          f"non-f-code columns (not normalized)")
    if ext_skip:
        print(f"    EXTENSIVE skipped: {ext_skip[:10]}{'...' if len(ext_skip)>10 else ''}")
    if int_skip:
        print(f"    INTENSIVE skipped: {int_skip[:10]}{'...' if len(int_skip)>10 else ''}")
classified = set(ext_cols) | set(int_cols) | set(lnd_cols) | set(met_cols)
other_cols = sorted(all_cols - classified)

ext_missing = extensive_set - all_cols
int_missing = intensive_set - all_cols
print(f"  EXTENSIVE in data:  {len(ext_cols)}/{len(extensive_set)} "
      f"(missing: {len(ext_missing)})")
print(f"  INTENSIVE in data:  {len(int_cols)}/{len(intensive_set)} "
      f"(missing: {len(int_missing)})")
print(f"  LAND in data:       {len(lnd_cols)}/{len(land_set)}")
print(f"  META in data:       {len(met_cols)}/{len(meta_set)}")
print(f"  Other/unclassified: {len(other_cols)}")

if ext_missing:
    print(f"\n  Extensive NOT in data (first 10): {sorted(ext_missing)[:10]}")
if int_missing:
    print(f"  Intensive NOT in data (first 10): {sorted(int_missing)[:10]}")

# ================================================================
# CHECK 3: Pre-normalization correlation with population
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 3: Pre-normalization correlation with population")
print("=" * 70)

ext_sample = ext_cols[:20]
int_sample = int_cols[:20]

pre_ext_corrs = []
for col in ext_sample:
    vals = pd.to_numeric(df[col], errors='coerce')
    r = vals.corr(pop)
    pre_ext_corrs.append((col, r))

pre_int_corrs = []
for col in int_sample:
    vals = pd.to_numeric(df[col], errors='coerce')
    r = vals.corr(pop)
    pre_int_corrs.append((col, r))

ext_r_mean = np.nanmean([r for _, r in pre_ext_corrs])
int_r_mean = np.nanmean([r for _, r in pre_int_corrs])

print(f"  EXTENSIVE mean corr with pop (first 20): {ext_r_mean:+.3f}")
print(f"    Expected: high (>0.3) since these are raw counts")
for col, r in pre_ext_corrs[:5]:
    desc = classif.loc[classif['metric']==col, 'description'].values
    d = desc[0][:40] if len(desc) > 0 else '?'
    print(f"      {col:20s} r={r:+.3f}  {d}")

print(f"  INTENSIVE mean corr with pop (first 20): {int_r_mean:+.3f}")
print(f"    Expected: low (<0.3) since these are rates/percentages")
for col, r in pre_int_corrs[:5]:
    desc = classif.loc[classif['metric']==col, 'description'].values
    d = desc[0][:40] if len(desc) > 0 else '?'
    print(f"      {col:20s} r={r:+.3f}  {d}")

if abs(ext_r_mean) < 0.2:
    print(f"\n  *** WARNING: EXTENSIVE mean corr with pop is LOW ({ext_r_mean:.3f})")
    print(f"      Possible misclassification!")
if abs(int_r_mean) > 0.5:
    print(f"\n  *** WARNING: INTENSIVE mean corr with pop is HIGH ({int_r_mean:.3f})")
    print(f"      Possible misclassification!")

# Save pre-normalization snapshots
pre_snap = {}
check_ext = ext_cols[:5]
check_int = int_cols[:5]
for col in check_ext:
    pre_snap[col] = pd.to_numeric(df[col], errors='coerce').head(5).tolist()
pre_raw_int = {}
for col in check_int:
    pre_raw_int[col] = pd.to_numeric(df[col], errors='coerce').head(5).tolist()

# ================================================================
# STEP 3: Normalize EXTENSIVE by population
# ================================================================
print(f"\n{'=' * 70}")
print("STEP 3: Normalizing EXTENSIVE columns by population"
      + (" (PER-YEAR / own-year)" if PERYEAR_ACTIVE else ""))
print("=" * 70)

def _fcode_year(metric):
    m = re.match(r'^f\d{5}(\d{2})$', str(metric))
    if not m:
        return None
    yy = int(m.group(1))
    return 2000 + yy if yy <= 24 else 1900 + yy

_yr_used = {}   # year -> count of columns; tracks what got applied
_fallback_2019 = 0
for i, col in enumerate(ext_cols):
    vals = pd.to_numeric(df[col], errors='coerce')
    if PERYEAR_ACTIVE:
        y = metric_pop_year.get(col)
        if y is None:
            y = _fcode_year(col)
        div = peryear_div.get(y)
        if div is None:
            div = pop                      # final fallback: population_2019
            _fallback_2019 += 1
            y = 'pop2019'
        df[col] = vals / div
        _yr_used[y] = _yr_used.get(y, 0) + 1
    else:
        df[col] = vals / pop
    if (i+1) % 500 == 0:
        print(f"  ... {i+1}/{len(ext_cols)}")

print(f"  Done: {len(ext_cols)} columns divided by population")
if PERYEAR_ACTIVE:
    print(f"  Per-year divisor usage (year: n_columns): "
          f"{dict(sorted(_yr_used.items(), key=lambda kv: str(kv[0])))}")
    print(f"  Columns falling back to {POP_COLUMN}: {_fallback_2019}")

# ================================================================
# STEP 4: Rescale to 0-9999
# ================================================================
print(f"\n{'=' * 70}")
print("STEP 4: Rescaling to 0-{0}".format(MAX_VAL))
print("=" * 70)

all_zero_ext = []
all_zero_int = []

for col in ext_cols:
    vals = df[col].astype(float)
    col_max = vals.max()
    if col_max > 0 and not np.isnan(col_max):
        df[col] = (vals / col_max * MAX_VAL).round(0).astype('Int64')
    else:
        df[col] = 0
        all_zero_ext.append(col)

for col in int_cols:
    vals = pd.to_numeric(df[col], errors='coerce')
    col_max = vals.max()
    if col_max > 0 and not np.isnan(col_max):
        df[col] = (vals / col_max * MAX_VAL).round(0).astype('Int64')
    elif col_max is not None and not np.isnan(col_max) and col_max < 0:
        col_min = vals.min()
        if col_min != col_max:
            df[col] = ((vals - col_min) / (col_max - col_min) * MAX_VAL).round(0).astype('Int64')
    else:
        df[col] = 0
        all_zero_int.append(col)

print(f"  EXTENSIVE all-zero columns: {len(all_zero_ext)}")
if all_zero_ext:
    print(f"    {all_zero_ext[:10]}{'...' if len(all_zero_ext)>10 else ''}")
print(f"  INTENSIVE all-zero columns: {len(all_zero_int)}")
if all_zero_int:
    print(f"    {all_zero_int[:10]}{'...' if len(all_zero_int)>10 else ''}")

# ================================================================
# STEP 5b: Pre-pandemic cause averages (NEW2 file, if provided)
# ================================================================
new_cause_cols = []   # track names added, for CHECK 5 and FINAL SUMMARY

if NEW2_FILE:
    print(f"\n{'=' * 70}")
    print("STEP 5b: Computing pre-pandemic cause averages from NEW2 file")
    print("=" * 70)
    print(f"  Loading: {NEW2_FILE}")
    new2 = pd.read_csv(NEW2_FILE, low_memory=False)
    print(f"  Shape: {new2.shape[0]} rows x {new2.shape[1]} cols")

    # Normalize fips for join
    if 'fips' not in df.columns or 'fips' not in new2.columns:
        print("  ERROR: fips column missing in input or NEW2 file -- skipping cause averages")
    else:
        df['fips']   = df['fips'].astype(str).str.zfill(5)
        new2['fips'] = new2['fips'].astype(str).str.zfill(5)

        # Find all cause columns in NEW2
        all_cause_cols = [c for c in new2.columns if CAUSE_PATTERN.match(c)]
        print(f"  Found {len(all_cause_cols)} cause-specific columns in NEW2")

        # Get unique (cause, age) pairs present in pre-pandemic years
        pairs = sorted(set(
            (CAUSE_PATTERN.match(c).group(2), CAUSE_PATTERN.match(c).group(3))
            for c in all_cause_cols
            if CAUSE_PATTERN.match(c).group(1) in PRE_YEARS
        ))
        print(f"  Cause x age pairs: {len(pairs)}")

        # Build fips-indexed lookup from new2 for fast access
        new2_indexed = new2.set_index('fips')

        n_inf_replaced = 0
        n_all_nan = 0

        for cause, age in pairs:
            # Column names for the three pre-pandemic years
            yr_cols = [f"{yr}_{cause}_{age}" for yr in PRE_YEARS]
            yr_cols_present = [c for c in yr_cols if c in new2_indexed.columns]

            if not yr_cols_present:
                print(f"  WARNING: no pre-pandemic columns found for {cause} {age} -- skipping")
                continue

            # Extract values aligned to df fips order
            arrays = []
            for yc in yr_cols_present:
                col_vals = new2_indexed[yc].reindex(df['fips'].values).values.astype(np.float64)
                # inf -> 0 (zero baseline = genuine zero excess death rate)
                n_inf = int(np.isinf(col_vals).sum())
                if n_inf > 0:
                    col_vals = np.where(np.isinf(col_vals), 0.0, col_vals)
                    n_inf_replaced += n_inf
                arrays.append(col_vals)

            # nanmean across up to 3 years
            stacked = np.vstack(arrays)           # shape (n_years, n_counties)
            avg = np.nanmean(stacked, axis=0)     # NaN if all years NaN for that county

            n_county_allnan = int(np.isnan(avg).sum())
            n_all_nan += n_county_allnan

            # Impute remaining NaN with column mean (consistent with upstream imputation)
            col_mean = np.nanmean(avg)
            if np.isnan(col_mean):
                col_mean = 0.0
            avg = np.where(np.isnan(avg), col_mean, avg)

            # Build output column name: {Cause}_asedx_p_17-19_{AGE}
            safe_cause = cause.replace(' ', '_')
            out_col = f"{safe_cause}_asedx_p_17-19_{age}"

            # Rescale to 0-9999 (INTENSIVE treatment)
            col_max = float(np.nanmax(avg))
            if col_max > 0:
                scaled = np.round(avg / col_max * MAX_VAL).astype(int)
            else:
                scaled = np.zeros(len(avg), dtype=int)

            df[out_col] = scaled
            new_cause_cols.append(out_col)

        print(f"  inf->0 replacements across all cause/year columns: {n_inf_replaced}")
        print(f"  County-cause-age cells with all-NaN years (imputed with col mean): {n_all_nan}")
        print(f"  New columns added: {len(new_cause_cols)}")
        for c in new_cause_cols:
            vals = df[c]
            print(f"    {c:45s}  max={vals.max()}  NaN={vals.isna().sum()}")
else:
    print("\n  --new2 not provided: skipping pre-pandemic cause averages")

# ================================================================
# CHECK 4: Post-normalization correlation with population
#   THE KEY CHECK: extensive should now be de-correlated from pop
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 4: Post-normalization correlation with population")
print("=" * 70)

post_ext_corrs = []
for col in ext_sample:
    vals = pd.to_numeric(df[col], errors='coerce')
    r = vals.corr(pop)
    post_ext_corrs.append((col, r))

post_int_corrs = []
for col in int_sample:
    vals = pd.to_numeric(df[col], errors='coerce')
    r = vals.corr(pop)
    post_int_corrs.append((col, r))

post_ext_r_mean = np.nanmean([r for _, r in post_ext_corrs])
post_int_r_mean = np.nanmean([r for _, r in post_int_corrs])

print(f"  EXTENSIVE corr with pop:  BEFORE={ext_r_mean:+.3f}  AFTER={post_ext_r_mean:+.3f}")
print(f"    Expected: AFTER should be much closer to 0")
print(f"  INTENSIVE corr with pop:  BEFORE={int_r_mean:+.3f}  AFTER={post_int_r_mean:+.3f}")
print(f"    Expected: AFTER ~ BEFORE (rescaling preserves rank order)")

if abs(post_ext_r_mean) > 0.5:
    print(f"\n  *** WARNING: Extensive STILL strongly correlated with pop!")

print(f"\n  Detail (EXTENSIVE):")
for (col, r_pre), (_, r_post) in zip(pre_ext_corrs[:10], post_ext_corrs[:10]):
    desc = classif.loc[classif['metric']==col, 'description'].values
    d = desc[0][:35] if len(desc) > 0 else '?'
    print(f"    {col:20s} {r_pre:+.3f} -> {r_post:+.3f}  {d}")

# ================================================================
# CHECK 5: Value distribution sanity
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 5: Value distribution sanity")
print("=" * 70)

bad_max = []
for col in ext_cols + int_cols:
    vals = pd.to_numeric(df[col], errors='coerce').dropna()
    if len(vals) == 0:
        continue
    mx = vals.max()
    if mx != 0 and mx != MAX_VAL:
        bad_max.append((col, mx))

if bad_max:
    print(f"  *** {len(bad_max)} columns with max != 0 and != {MAX_VAL}:")
    for col, mx in bad_max[:10]:
        print(f"      {col}: max={mx}")
else:
    print(f"  OK: All non-zero columns have max = {MAX_VAL}")

neg_cols = []
for col in ext_cols + int_cols:
    vals = pd.to_numeric(df[col], errors='coerce').dropna()
    if (vals < 0).any():
        neg_cols.append((col, vals.min()))
if neg_cols:
    print(f"  *** {len(neg_cols)} columns with negative values!")
    for col, mn in neg_cols[:5]:
        print(f"      {col}: min={mn}")
else:
    print(f"  OK: No negative values in rescaled columns")

nan_ext = sum(pd.to_numeric(df[col], errors='coerce').isna().sum() for col in ext_cols)
nan_int = sum(pd.to_numeric(df[col], errors='coerce').isna().sum() for col in int_cols)
print(f"  NaN cells in EXTENSIVE: {nan_ext} across {len(ext_cols)} columns")
print(f"  NaN cells in INTENSIVE: {nan_int} across {len(int_cols)} columns")

# ================================================================
# CHECK 6: Hand-check sample metrics
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 6: Hand-check sample metrics")
print("=" * 70)

print(f"\n  EXTENSIVE (raw -> normed, first 3 rows):")
for col in check_ext:
    desc = classif.loc[classif['metric']==col, 'description'].values
    d = desc[0][:50] if len(desc) > 0 else '?'
    pre = [f"{v:.1f}" if v is not None and not np.isnan(v) else 'NaN'
           for v in pre_snap.get(col, [])[:3]]
    post = df[col].head(3).tolist()
    print(f"    {col:20s} {d}")
    print(f"      raw:    {pre}")
    print(f"      normed: {post}")

print(f"\n  INTENSIVE (raw -> normed, rank order should match):")
for col in check_int:
    desc = classif.loc[classif['metric']==col, 'description'].values
    d = desc[0][:50] if len(desc) > 0 else '?'
    pre = pre_raw_int[col][:3]
    post = [float(x) if x is not None and not pd.isna(x) else np.nan 
            for x in df[col].head(3).tolist()]
    pre_rank = pd.Series(pre).rank().tolist()
    post_rank = pd.Series(post).rank().tolist()
    rank_ok = pre_rank == post_rank
    print(f"    {col:20s} {d}")
    print(f"      raw:    {[f'{v:.2f}' for v in pre]}")
    print(f"      normed: {df[col].head(3).tolist()}  rank_preserved={rank_ok}")

# ================================================================
# CHECK 7: Unclassified columns untouched
# ================================================================
print(f"\n{'=' * 70}")
print("CHECK 7: Unclassified columns untouched")
print("=" * 70)
orig_df = pd.read_csv(INPUT_FILE, nrows=3)
untouched_checks = ['fips', 'population_2019', 'asedx_p_2021', 'asedx_p_2020']
for col in untouched_checks:
    if col in df.columns and col in orig_df.columns:
        orig_vals = orig_df[col].tolist()
        now_vals = df[col].head(3).tolist()
        match = orig_vals == now_vals
        print(f"  {col:25s} orig={orig_vals}  now={now_vals}  match={match}")
        if not match:
            print(f"    *** MISMATCH -- unclassified column was modified!")

# ================================================================
# Drop raw cause columns (all YYYY_CauseName_AGEGROUP for all years)
# Only the averaged 17-19 columns should remain
# ================================================================
print(f"\n{'=' * 70}")
print("DROPPING RAW CAUSE COLUMNS")
print("=" * 70)
raw_cause_cols = [c for c in df.columns if CAUSE_PATTERN.match(c) or re.match(r'^\d{4}-\d{4}_', c)]
if raw_cause_cols:
    df.drop(columns=raw_cause_cols, inplace=True)
    print(f"  Dropped {len(raw_cause_cols)} raw cause columns (YYYY_CauseName_AGEGROUP)")
else:
    print(f"  No raw cause columns found to drop")

# ================================================================
# Write output
# ================================================================
print(f"\n{'=' * 70}")
print("WRITING OUTPUT")
print("=" * 70)
df.to_csv(OUTPUT_FILE, index=False)
_tee(OUTPUT_FILE)
print(f"  Written: {OUTPUT_FILE}")
print(f"  Shape:   {df.shape[0]} rows x {df.shape[1]} columns")

# ================================================================
# FINAL SUMMARY
# ================================================================
print(f"\n{'=' * 70}")
print("FINAL SUMMARY")
print("=" * 70)
print(f"  Input:  {INPUT_FILE}")
print(f"  Output: {OUTPUT_FILE}")
print(f"  Population column: {POP_COLUMN}")
print(f"  EXTENSIVE: {len(ext_cols)} cols -- divided by pop, scaled to 0-{MAX_VAL}")
print(f"  INTENSIVE: {len(int_cols)} cols -- scaled to 0-{MAX_VAL} (no pop division)")
print(f"  LAND:      {len(lnd_cols)} cols -- untouched")
print(f"  META:      {len(met_cols)} cols -- untouched")
print(f"  OTHER:     {len(other_cols)} cols -- untouched")
print(f"  NEW cause: {len(new_cause_cols)} cols -- pre-pandemic 17-19 avg, scaled to 0-{MAX_VAL}")
if new_cause_cols:
    print(f"    NEW2 source: {NEW2_FILE}")
print(f"  Pop-corr (extensive): {ext_r_mean:+.3f} -> {post_ext_r_mean:+.3f}")
print(f"  Pop-corr (intensive): {int_r_mean:+.3f} -> {post_int_r_mean:+.3f}")
