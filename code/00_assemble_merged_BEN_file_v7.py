#!/usr/bin/env python3
"""
00_assemble_merged_BEN_file_v7.py
==================================
Assemble BEN_MERGED_MEASURES_imputed_20s.csv from 7 source files,
merging on 'fips'.

Changes from v6:
  - Removed all use of old_columns.txt / EXISTING_OUTPUT reference file.
  - Step 6a replaced with self-contained column selection logic:
      AHRF f-codes:
        * Keep all 6-char undated f-codes (32 total).
        * For each 8-char base code with multiple year versions:
            - Exclude year=2020 from multi-year series (not temporal 2020).
            - Exception: geographic/admin codes ending in 20 are kept.
            - Select the latest year using calendar-year sort
              (suffixes 30-99 treated as 1930-1999, 00-29 as 2000-2029).
      UA_County columns:
        * Keep only all-caps column names (e.g. POP_URB, ALAND_COU, AREA_SQMI)
          plus 7 known mixed-case identifiers (Urban_Influence_Code_*,
          Rural-urban_Continuum_Code_*, ALAND_Mi2_*).
        * Drop all other UA_County columns (e.g. Stabr_check, Area_name_check).
      All other ancillary sources dropped entirely:
        Poverty, SVI, Vaccination, Causes, Deaths_PHT.
      Primary non-metric columns dropped (age_group_*, Stabr_BEN etc).
      Primary death/mortality measure columns kept (deaths_*, ased_*, etc).

Author: Claude (for Michael Levitt)
Date:   2026-04-26
"""

import sys
import os
import sys
import re
import pandas as pd
import numpy as np
from collections import OrderedDict, defaultdict

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


# ============================================================
# Configuration
# ============================================================
RAW_DIR = "./data/raw"

PRIMARY_FILE = os.path.join(RAW_DIR, "usa-county-result.10Feb26.csv")

ANCILLARY_FILES = OrderedDict([
    ("Causes",      os.path.join(RAW_DIR, "county_causes_pivoted.csv")),
    ("UA_County",   os.path.join(RAW_DIR, "2020_UA_COUNTY_fips.4_Corrected.MOD.csv")),
    ("Poverty",     os.path.join(RAW_DIR, "Poverty_Counties_fips.MOD.csv")),
    ("SVI",         os.path.join(RAW_DIR, "SVI_2018_US_county.MOD.csv")),
    ("Vaccination", os.path.join(RAW_DIR, "Simplified_Monthly_Averages_by_County_with_fips.MOD.csv")),
    ("AHRF",        os.path.join(RAW_DIR, "AHRF2020.fips.csv")),
    ("Deaths_PHT",  os.path.join(RAW_DIR, "fips_US_Counties_Dy20_Dy21_Dy22_Dy23_Dyal_PHT.fix.MOD.csv")),
])

OUTPUT_FILE = os.environ.get(
    "BEN_OUTPUT", "BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NEW.csv")

# Geographic/admin f-codes that end in '20' but are NOT temporal 2020 data.
# These are kept even in multi-year series.
AHRF_GEO_CODES = {
    "f1389120",  # Core_Based_Statistical_Area_Code
    "f1389220",  # Core_Based_Statistical_Area_Name
    "f1406720",  # Core_Based_Statistical_Area_Indicator_Code
    "f1419520",  # Core_Based_Statistical_Area_County_Status
    "f1419320",  # Metropolitan_Division_Code
    "f1419420",  # Metropolitan_Division_Name
    "f1389320",  # Combined_Statistical_Area_Code
    "f1389420",  # Combined_Statistical_Area_Name
    "f0978720",  # Health_Professions_Shortage_Area_Code_Primary_Care
    "f0979220",  # Health_Professions_Shortage_Area_Code_Dentists
    "f1249220",  # Health_Professions_Shortage_Area_Code_Mental_Health
}

# AHRF string identifier columns (kept as strings, not converted to numeric)
AHRF_STRING_COLS = {
    "f00001", "f00003", "f00004", "f00005", "f00006", "f00007",
    "f00008", "f12424", "f00010", "f04437", "f00011", "f00012",
    "f04439", "f04448", "f04440", "f04449", "f00023", "f13156",
}


# ============================================================
# Helper: year sort key
# ============================================================

def year_sort_key(fcode):
    """
    Convert 2-char year suffix of an 8-char f-code to a sortable integer.
    Suffixes 00-29  -> 2000-2029 (recent data)
    Suffixes 30-99  -> 1930-1999 (old vintages)
    This ensures 18, 19 sort higher than 90, 95, 96.
    """
    yr = int(fcode[-2:])
    return 2000 + yr if yr <= 29 else 1900 + yr


# Optional AHRF vintage cutoff (opt-in via env var AHRF_YEAR_CUTOFF).
# When set, only f-code versions with calendar year <= cutoff are eligible
# (geo identifier codes are exempt). Default None preserves original behaviour.
_yc = os.environ.get("AHRF_YEAR_CUTOFF")
YEAR_CUTOFF = int(_yc) if _yc else None


# ============================================================
# Helper: select AHRF f-codes to keep
# ============================================================

def select_ahrf_fcodes(all_fcodes):
    """
    Given the list of all AHRF f-code column names present in the merged df,
    return the subset to keep, applying:
      1. All 6-char undated codes: keep all.
      2. 8-char dated codes: group by base (first 6 chars).
         - Single-year: keep as-is (including 2020-only).
         - Multi-year:  exclude year=2020 unless geo-exempt; keep latest by
                        calendar year (using year_sort_key).
    """
    code_6   = [c for c in all_fcodes if len(c) == 6]
    code_8   = [c for c in all_fcodes if len(c) == 8]
    code_oth = [c for c in all_fcodes if len(c) not in (6, 8)]

    if code_oth:
        print("  NOTE: %d f-codes with unexpected length (kept as-is): %s"
              % (len(code_oth), code_oth[:10]))

    base_groups = defaultdict(list)
    for c in code_8:
        base_groups[c[:6]].append(c)

    kept_8    = []
    dropped_8 = []
    single_year_2020 = []

    for base, codes in base_groups.items():
        geo_in_group = [c for c in codes if c in AHRF_GEO_CODES]

        if YEAR_CUTOFF is not None:
            codes = [c for c in codes
                     if year_sort_key(c) <= YEAR_CUTOFF or c in AHRF_GEO_CODES]
            if not codes:
                continue  # no version at/before cutoff -- drop this base entirely

        if len(codes) == 1:
            c = codes[0]
            kept_8.append(c)
            if c[-2:] == "20" and c not in AHRF_GEO_CODES:
                single_year_2020.append(c)
        else:
            # Multi-year: candidates exclude year=2020 non-geo
            candidates = [c for c in codes
                          if year_sort_key(c) != 2020 or c in AHRF_GEO_CODES]
            for g in geo_in_group:
                if g not in candidates:
                    candidates.append(g)

            if not candidates:
                # All were 2020 non-geo: keep them (only option)
                for c in codes:
                    kept_8.append(c)
                    single_year_2020.append(c)
            else:
                best = max(candidates, key=year_sort_key)
                kept_8.append(best)
                dropped_8.extend([c for c in codes if c != best])

    print("  AHRF f-code selection:")
    print("    6-char undated:         %4d  (all kept)" % len(code_6))
    print("    8-char dated (input):   %4d" % len(code_8))
    print("    8-char dated (kept):    %4d" % len(kept_8))
    print("    8-char dated (dropped): %4d" % len(dropped_8))
    if single_year_2020:
        print("    Single-year 2020 kept:  %4d" % len(single_year_2020))
        for c in sorted(single_year_2020):
            print("      %s" % c)

    # Year distribution of kept 8-char
    yr_dist = defaultdict(int)
    for c in kept_8:
        yr_dist[c[-2:]] += 1
    yr_summary = "  ".join("%s:%d" % (yr, yr_dist[yr])
                            for yr in sorted(yr_dist, key=lambda y: year_sort_key("f00000"+y)))
    print("    Year distribution of kept: %s" % yr_summary)

    return set(code_6 + kept_8 + code_oth)


# ============================================================
# Helper functions (unchanged from v6)
# ============================================================

def normalize_fips(series):
    """Convert fips to zero-padded 5-digit string."""
    def fix_one(v):
        if pd.isna(v):
            return None
        s = str(v).strip().strip('"').strip("'")
        if "." in s:
            try:
                s = str(int(float(s)))
            except ValueError:
                pass
        try:
            return s.zfill(5)
        except Exception:
            return None
    return series.apply(fix_one)


def load_csv_robust(filepath, label):
    """Load a CSV with robust error handling."""
    print("=" * 70)
    print("Loading: %s  [%s]" % (label, filepath))
    print("=" * 70)

    if not os.path.isfile(filepath):
        print("  *** ERROR: File not found: %s" % filepath)
        return None

    df = None
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(filepath, dtype=str,
                             na_values=["", "NA", "N/A", ".", " "],
                             keep_default_na=True, low_memory=False,
                             encoding=enc)
            print("  Encoding used: %s" % enc)
            break
        except UnicodeDecodeError:
            print("  Encoding %s failed, trying next..." % enc)
            continue
        except Exception as e:
            print("  *** ERROR reading %s: %s" % (filepath, e))
            return None
    if df is None:
        print("  *** ERROR: All encodings failed for %s" % filepath)
        return None

    nrow, ncol = df.shape
    print("  Loaded: %d rows x %d columns" % (nrow, ncol))

    fips_col = None
    for c in df.columns:
        if c.strip().strip('"').lower() == "fips":
            fips_col = c
            break

    if fips_col is None:
        print("  *** ERROR: No 'fips' column found. Columns: %s"
              % list(df.columns[:10]))
        return None

    if fips_col != "fips":
        print("  Renaming column '%s' -> 'fips'" % fips_col)
        df = df.rename(columns={fips_col: "fips"})

    df.columns = [c.strip().strip('"') for c in df.columns]
    df["fips"] = normalize_fips(df["fips"])
    n_null_fips = df["fips"].isna().sum()
    if n_null_fips > 0:
        print("  WARNING: %d rows have null/invalid fips -- dropping"
              % n_null_fips)
        df = df.dropna(subset=["fips"])

    n_unique = df["fips"].nunique()
    print("  Unique fips values: %d" % n_unique)
    if n_unique < len(df):
        print("  NOTE: %d duplicate fips rows" % (len(df) - n_unique))
    print("  First 5 fips: %s" % list(df["fips"].head()))
    print()
    return df


def convert_numeric_columns(df, exclude_cols=None):
    """Try to convert columns to numeric where possible."""
    if exclude_cols is None:
        exclude_cols = set()
    else:
        exclude_cols = set(exclude_cols)

    converted = []
    for col in df.columns:
        if col in exclude_cols:
            continue
        num = pd.to_numeric(df[col], errors="coerce")
        n_orig = df[col].notna().sum()
        n_num  = num.notna().sum()
        if n_orig > 0 and n_num >= 0.5 * n_orig:
            if n_orig - n_num > 20:
                continue
            df[col] = num
            converted.append(col)
    return df, converted


# ============================================================
# Pivot primary file (unchanged from v6)
# ============================================================

def pivot_primary(df):
    """Pivot primary file from long to wide: one row per fips."""
    print("=" * 70)
    print("Pivoting primary file to one row per fips")
    print("=" * 70)

    ag_map = {"all": "", "65+": "_GE65", "0-64": "_LT65"}
    value_cols = [c for c in df.columns
                  if c not in ["fips", "year", "age_group"]]
    years      = sorted(df["year"].unique())
    age_groups = sorted(df["age_group"].unique())

    print("  Value columns: %s" % value_cols)
    print("  Years: %s" % years)
    print("  Age groups: %s" % age_groups)

    for vc in value_cols:
        df[vc] = pd.to_numeric(df[vc], errors="coerce")

    n_fips = df["fips"].nunique()
    print("  Unique fips: %d" % n_fips)
    print("  Expected rows per fips: %d x %d = %d"
          % (len(years), len(age_groups), len(years) * len(age_groups)))

    pieces = []
    for ag_val, ag_suffix in ag_map.items():
        subset = df[df["age_group"] == ag_val].copy()
        if len(subset) == 0:
            print("  WARNING: No rows for age_group='%s'" % ag_val)
            continue
        piv = subset.pivot_table(index="fips", columns="year",
                                 values=value_cols, aggfunc="first")
        new_cols = ["%s_%s%s" % (m, yr, ag_suffix) for m, yr in piv.columns]
        piv.columns = new_cols
        pieces.append(piv)
        print("  age_group='%s' -> %d columns" % (ag_val, len(new_cols)))

    result = pd.concat(pieces, axis=1).reset_index()

    for ag_val, ag_suffix in ag_map.items():
        for yr in years:
            result["age_group_%s%s" % (yr, ag_suffix)] = ag_val

    print("  Pivoted result: %d rows x %d columns" % result.shape)
    print()
    return result


# ============================================================
# Main
# ============================================================

def main():
    print("#" * 70)
    print("# 00_assemble_merged_BEN_file_v7.py")
    print("# Output: %s" % OUTPUT_FILE)
    print("#" * 70)
    print()

    # ----------------------------------------------------------
    # 1. Load and pivot primary file
    # ----------------------------------------------------------
    primary_raw = load_csv_robust(PRIMARY_FILE, "Primary (usa-county-result)")
    if primary_raw is None:
        print("FATAL: Cannot load primary file. Exiting.")
        sys.exit(1)
    primary = pivot_primary(primary_raw)

    # ----------------------------------------------------------
    # 2. Load ancillary files
    # ----------------------------------------------------------
    ancillary_dfs = OrderedDict()
    for label, fpath in ANCILLARY_FILES.items():
        df = load_csv_robust(fpath, label)
        if df is not None:
            ancillary_dfs[label] = df

    # ----------------------------------------------------------
    # 3. Handle identifier columns
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Handling identifier columns across ancillary files")
    print("=" * 70)

    stabr_renamed = False
    for label, df in ancillary_dfs.items():
        if "Stabr" in df.columns and not stabr_renamed:
            renames = {}
            if "Stabr"     in df.columns: renames["Stabr"]     = "Stabr_BEN"
            if "Area_name" in df.columns: renames["Area_name"] = "Area_name_BEN"
            print("  [%s] Renaming Stabr -> Stabr_BEN, Area_name -> Area_name_BEN"
                  % label)
            ancillary_dfs[label] = df.rename(columns=renames)
            stabr_renamed = True
        elif "Stabr" in df.columns:
            drop = [c for c in ["Stabr", "Area_name"] if c in df.columns]
            if drop:
                print("  [%s] Dropping duplicate Stabr/Area_name columns" % label)
                ancillary_dfs[label] = df.drop(columns=drop)

    # ----------------------------------------------------------
    # 4. Deduplicate ancillary files on fips
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Checking for duplicate fips in ancillary files")
    print("=" * 70)

    for label, df in ancillary_dfs.items():
        dups = df["fips"].duplicated(keep=False)
        n_dup = dups.sum()
        if n_dup > 0:
            print("  [%s] %d duplicate rows across %d fips -> keeping first"
                  % (label, n_dup, df.loc[dups, "fips"].nunique()))
            ancillary_dfs[label] = df.drop_duplicates(subset=["fips"], keep="first")
        else:
            print("  [%s] No duplicates -- OK (%d rows)" % (label, len(df)))

    # ----------------------------------------------------------
    # 5. Check column collisions
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Checking for column name collisions across files")
    print("=" * 70)

    primary_cols = set(primary.columns) - {"fips"}
    all_anc_cols = {}
    n_col = 0
    for label, df in ancillary_dfs.items():
        for col in df.columns:
            if col == "fips":
                continue
            if col in primary_cols:
                n_col += 1
                if n_col <= 20:
                    print("  '%s' in [%s] collides with primary" % (col, label))
            if col in all_anc_cols:
                n_col += 1
                if n_col <= 20:
                    print("  '%s' in [%s] collides with [%s]"
                          % (col, label, all_anc_cols[col]))
            all_anc_cols[col] = label
    if n_col == 0:
        print("  No collisions found")
    elif n_col > 20:
        print("  ... and %d more collisions" % (n_col - 20))

    # ----------------------------------------------------------
    # 6. Merge all files
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Merging files (left join on fips)")
    print("=" * 70)

    merged = primary.copy()
    primary_fips = set(primary["fips"].unique())

    for label, df in ancillary_dfs.items():
        anc_fips = set(df["fips"].unique())
        print("\n  Merging [%s] (%d data columns):" % (label, len(df.columns)-1))
        print("    fips in both:         %5d" % len(primary_fips & anc_fips))
        print("    fips only in primary: %5d" % len(primary_fips - anc_fips))
        print("    fips only in [%s]: %5d" % (label, len(anc_fips - primary_fips)))
        n_before = len(merged)
        merged = merged.merge(df, on="fips", how="left",
                               suffixes=("", "_DUP_%s" % label))
        if len(merged) != n_before:
            print("    *** WARNING: Row count changed %d -> %d"
                  % (n_before, len(merged)))
        else:
            print("    Row count preserved: %d" % len(merged))

    print("\n  Final merged shape: %d rows x %d columns" % merged.shape)

    dup_cols = [c for c in merged.columns if "_DUP_" in c]
    if dup_cols:
        print("  Dropping %d duplicate-suffixed columns" % len(dup_cols))
        merged = merged.drop(columns=dup_cols)
        print("  Shape after dropping dups: %d rows x %d columns" % merged.shape)

    # ----------------------------------------------------------
    # 6a. Select columns to keep from AHRF and UA_County sources
    #
    # From AHRF:     keep only f-code columns (start with 'f' + digit),
    #                selecting latest year per base code, excluding 2020
    #                multi-year series (see select_ahrf_fcodes).
    # From UA_County: keep only all-caps columns (e.g. POP_URB, ALAND_COU)
    #                 plus the known mixed-case UA_County identifiers.
    # All other non-f columns from other ancillary sources (Poverty, SVI,
    # Vaccination, Deaths_PHT, Causes, primary) are kept as-is.
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Selecting columns: AHRF f-codes + UA_County all-caps (v7)")
    print("=" * 70)

    # --- AHRF f-code selection ---
    all_fcodes  = [c for c in merged.columns
                   if re.match(r'^f\d', c) and len(c) in (6, 8)]
    keep_fcodes = select_ahrf_fcodes(all_fcodes)

    drop_fcodes = [c for c in all_fcodes if c not in keep_fcodes]
    if drop_fcodes:
        print("  Dropping %d superseded AHRF f-codes" % len(drop_fcodes))
        merged = merged.drop(columns=drop_fcodes)
    print("  AHRF f-codes retained: %d" % len([c for c in merged.columns
                                                if re.match(r'^f\d', c)]))

    # --- UA_County column selection ---
    UA_MIXED_KEEP = {
        "Urban_Influence_Code_2013",
        "Rural-urban_Continuum_Code_2003",
        "Rural-urban_Continuum_Code_2013",
        "Urban_Influence_Code_2003",
        "ALAND_Mi2_COU",
        "ALAND_Mi2_RUR",
        "ALAND_Mi2_URB",
    }

    def is_all_caps(col):
        """True if column name is all uppercase (ignoring _ and digits)."""
        letters = re.sub(r'[^a-zA-Z]', '', col)
        return len(letters) > 0 and letters == letters.upper()

    if "UA_County" in ancillary_dfs:
        ua_cols = set(ancillary_dfs["UA_County"].columns) - {"fips"}
        ua_drop = [c for c in merged.columns
                   if c in ua_cols
                   and not is_all_caps(c)
                   and c not in UA_MIXED_KEEP]
        if ua_drop:
            print("  Dropping %d non-all-caps UA_County columns:" % len(ua_drop))
            for c in sorted(ua_drop):
                print("    %s" % c)
            merged = merged.drop(columns=ua_drop)
        ua_kept = [c for c in merged.columns
                   if c in ua_cols or c in UA_MIXED_KEEP]
        print("  UA_County columns retained: %d" % len(ua_kept))
    else:
        print("  UA_County not loaded -- skipping UA_County column filter")

    # --- Drop all other ancillary source columns ---
    # Keep only: fips, AHRF f-codes, UA_County all-caps/mixed-keep,
    # primary death/mortality measures, and asmr_bl cause columns.
    # Drop everything from: Poverty, SVI, Vaccination, Causes, Deaths_PHT,
    # and primary non-metric columns (age_group_*, Stabr_BEN, Area_name_BEN etc).

    DROP_SOURCES = {"Poverty", "SVI", "Vaccination", "Causes", "Deaths_PHT"}
    drop_other = []
    for src in DROP_SOURCES:
        if src in ancillary_dfs:
            src_cols = set(ancillary_dfs[src].columns) - {"fips"}
            to_drop  = [c for c in merged.columns if c in src_cols]
            if to_drop:
                print("  Dropping %d columns from [%s]" % (len(to_drop), src))
                drop_other.extend(to_drop)
    if drop_other:
        merged = merged.drop(columns=drop_other)

    # Drop primary non-metric columns: age_group_*, and identifier cols
    # that are not fips, f-codes, or UA_County metrics.
    # Keep from primary: only fips + death/mortality measure columns
    # (deaths_*, population_*, cmr_*, ased_*, asedx_*, le_*, lex_*,
    #  asmr_*, M_POV, M_URB etc -- anything used as a death measure or weight).
    primary_drop_prefixes = ("age_group_",)
    primary_drop_names    = {"Stabr_BEN", "Area_name_BEN", "tokens"}
    pri_drop = [c for c in merged.columns
                if (any(c.startswith(p) for p in primary_drop_prefixes)
                    or c in primary_drop_names)]
    if pri_drop:
        print("  Dropping %d primary non-metric columns (age_group_* etc)"
              % len(pri_drop))
        merged = merged.drop(columns=pri_drop)

    print("  Shape after column selection: %d rows x %d columns" % merged.shape)

    # ----------------------------------------------------------
    # 7. Convert to numeric where appropriate
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Converting columns to numeric types")
    print("=" * 70)

    string_cols = {"fips"}
    for col in merged.columns:
        if col.lower().startswith("age_group"):
            string_cols.add(col)
        if col in AHRF_STRING_COLS:
            string_cols.add(col)

    merged, converted_cols = convert_numeric_columns(merged, exclude_cols=string_cols)
    print("  Converted %d columns to numeric" % len(converted_cols))
    print("  Kept as string: %d columns" % len(string_cols & set(merged.columns)))

    # ----------------------------------------------------------
    # 8. Report missing data BEFORE imputation
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Missing data BEFORE imputation")
    print("=" * 70)

    numeric_cols     = merged.select_dtypes(include=[np.number]).columns.tolist()
    non_numeric_cols = [c for c in merged.columns if c not in numeric_cols]

    total_cells   = merged[numeric_cols].size
    total_missing = merged[numeric_cols].isna().sum().sum()
    print("\n  Total numeric cells: %d" % total_cells)
    print("  Total missing:       %d (%.2f%%)"
          % (total_missing, 100.0 * total_missing / max(total_cells, 1)))

    miss_counts = merged[numeric_cols].isna().sum()
    miss_counts = miss_counts[miss_counts > 0].sort_values(ascending=False)
    nrow = len(merged)
    if len(miss_counts) > 0:
        print("\n  Columns with missing values (%d of %d numeric):"
              % (len(miss_counts), len(numeric_cols)))
        print("  %-55s %8s %8s %7s" % ("Column", "Missing", "Total", "Pct"))
        print("  " + "-" * 82)
        items = list(miss_counts.items())
        show  = items[:100]
        if len(items) > 110:
            show += [("...", "...")]
            show += items[-10:]
        elif len(items) > 100:
            show += items[100:]
        for col, cnt in show:
            if col == "...":
                print("  %-55s %8s %8s %7s" % ("...", "...", "...", "..."))
            else:
                print("  %-55s %8d %8d %6.1f%%"
                      % (col, cnt, nrow, 100.0 * cnt / nrow))
    else:
        print("  No missing numeric values found.")

    # ----------------------------------------------------------
    # 9. Impute missing numeric values with column mean
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Imputing missing numeric values with column mean")
    print("=" * 70)

    impute_count   = 0
    impute_details = []
    for col in numeric_cols:
        n_miss = merged[col].isna().sum()
        if n_miss == 0:
            continue
        n_present = merged[col].notna().sum()
        if n_present == 0:
            print("  %-50s ALL MISSING -- cannot impute" % col)
            continue
        col_mean = merged[col].mean()
        merged[col] = merged[col].fillna(col_mean)
        impute_count += 1
        impute_details.append((col, n_miss, n_present, col_mean))

    print("\n  Imputed %d columns." % impute_count)
    if impute_details:
        print("\n  %-50s %8s %8s %15s"
              % ("Column", "Imputed", "Present", "Mean Used"))
        print("  " + "-" * 85)
        show = impute_details[:100]
        if len(impute_details) > 110:
            show += [None]
            show += impute_details[-10:]
        elif len(impute_details) > 100:
            show += impute_details[100:]
        for item in show:
            if item is None:
                print("  ... (%d more) ..." % (len(impute_details) - 110))
            else:
                col, n_miss, n_present, mean_val = item
                print("  %-50s %8d %8d %15.4f"
                      % (col, n_miss, n_present, mean_val))

    # ----------------------------------------------------------
    # 10. Verify
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Missing data AFTER imputation")
    print("=" * 70)

    remaining = merged[numeric_cols].isna().sum().sum()
    print("  Remaining missing: %d" % remaining)
    if remaining > 0:
        still_miss = merged[numeric_cols].isna().sum()
        for col, cnt in still_miss[still_miss > 0].items():
            print("    %-50s %d missing" % (col, cnt))

    non_num_miss = merged[non_numeric_cols].isna().sum()
    non_num_miss = non_num_miss[non_num_miss > 0]
    if len(non_num_miss) > 0:
        print("\n  Non-numeric missing (NOT imputed):")
        for col, cnt in non_num_miss.items():
            print("    %-50s %d missing" % (col, cnt))

    # ----------------------------------------------------------
    # 11. Sort by population_2019 descending
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Sorting rows")
    print("=" * 70)

    if "population_2019" in merged.columns:
        merged = merged.sort_values("population_2019",
                                     ascending=False, na_position="last")
        merged = merged.reset_index(drop=True)
        print("  Sorted by population_2019 descending")
    else:
        print("  WARNING: population_2019 not found, keeping default order")

    if "Area_name_BEN" in merged.columns:
        merged["Area_name_BEN"] = (merged["Area_name_BEN"]
                                    .astype(str).str.replace(" ", "_"))
        print("  Replaced spaces with underscores in Area_name_BEN")

    # ----------------------------------------------------------
    # 12. Final summary and write
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("Final summary")
    print("=" * 70)
    print("  Rows:        %d" % len(merged))
    print("  Columns:     %d" % len(merged.columns))
    print("  Unique fips: %d" % merged["fips"].nunique())

    # Count f-codes retained
    f_kept = [c for c in merged.columns if re.match(r'^f\d', c)]
    print("  f-codes:     %d" % len(f_kept))

    print("\n  Column listing (first 50 of %d):" % len(merged.columns))
    for i, col in enumerate(merged.columns[:50]):
        print("    (%03d) %-50s %s" % (i, col, merged[col].dtype))
    if len(merged.columns) > 50:
        print("    ... and %d more columns" % (len(merged.columns) - 50))

    print("\n  Writing: %s" % OUTPUT_FILE)
    merged.to_csv(OUTPUT_FILE, index=False)
    _tee(OUTPUT_FILE)
    fsize = os.path.getsize(OUTPUT_FILE)
    print("  Done. File size: %.1f MB" % (fsize / 1e6))
    print()

    return merged


if __name__ == "__main__":
    merged = main()
