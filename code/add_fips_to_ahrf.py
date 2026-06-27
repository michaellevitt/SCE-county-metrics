#!/usr/bin/env python3
"""
add_fips_to_ahrf.py
-------------------
Turn a raw AHRF CSV (as produced by AHRF_SAS7BDAT_to_CSV.v2.2_progress.py from
the HRSA SAS download) into the `data/raw/AHRF2020.fips.csv` layout this pipeline
expects: the same AHRF f-code columns, plus a 5-digit county `fips` key inserted
as the second column.

The pipeline merges every source on `fips`. In the AHRF SAS schema:
    f00011 = FIPS State Code (2 digits)
    f00012 = FIPS County Code (3 digits)
so  fips = f00011.zfill(2) + f00012.zfill(3)   (verified: 100% match to the
original AHRF2020.fips.csv).

Usage:
    python code/add_fips_to_ahrf.py --in ahrf_2019-2020_raw.csv \
                                    --out data/raw/AHRF2020.fips.csv
"""
import argparse
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True,
                    help="raw AHRF CSV from AHRF_SAS7BDAT_to_CSV (f-code columns)")
    ap.add_argument("--out", default="data/raw/AHRF2020.fips.csv",
                    help="output CSV (default: data/raw/AHRF2020.fips.csv)")
    args = ap.parse_args()

    # read as strings to preserve leading zeros in the FIPS codes
    df = pd.read_csv(args.inp, dtype=str)
    for col in ("f00011", "f00012"):
        if col not in df.columns:
            raise SystemExit(f"ERROR: expected AHRF column {col} not found in {args.inp}")

    fips = df["f00011"].str.strip().str.zfill(2) + df["f00012"].str.strip().str.zfill(3)

    # f00002 is the raw 5-digit FIPS code -- redundant with the named `fips`
    # column below, and the original AHRF2020.fips.csv dropped it. Drop it so a
    # fresh build matches (otherwise it would survive as an extra predictor).
    df = df.drop(columns=["f00002"], errors="ignore")

    df.insert(1, "fips", fips)            # second column, matching the original layout

    df.to_csv(args.out, index=False)
    print(f"wrote {args.out}: {df.shape[0]} rows x {df.shape[1]} cols "
          f"({df['fips'].nunique()} unique fips)")


if __name__ == "__main__":
    main()
