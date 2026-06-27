#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AHRF_SAS7BDAT_to_CSV.v2.2_progress.py
-------------------------------------
Robust SAS .sas7bdat → CSV converter with live progress and schema inspection.

Fixes vs v2.1
- Handles pyreadstat API differences: some versions don’t support `apply_value_formats`.
- Automatically falls back if argument not accepted.
- Everything else (progress, gzip output, schema inspection) retained.

Usage
-----
# Convert with progress
python AHRF_SAS7BDAT_to_CSV.v2.2_progress.py --sas AHRF2021.sas7bdat --out AHRF2021.csv --chunksize 100000

# Inspect schema
python AHRF_SAS7BDAT_to_CSV.v2.2_progress.py --sas AHRF2021.sas7bdat --inspect
"""

import argparse
import gzip
import io
import sys
import time

def eprint(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    msg_ascii = msg.encode("ascii", errors="ignore").decode("ascii")
    print(msg_ascii, file=sys.stderr, **{k: v for k, v in kwargs.items() if k != 'file'})

def open_out(path):
    if path == "-":
        return sys.stdout
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "wb"), encoding="utf-8", newline="")
    return open(path, "w", encoding="utf-8", newline="")

def write_df(df, out_handle, write_header=False):
    if df is None or df.shape[0] == 0:
        return 0
    df.to_csv(out_handle, index=False, header=write_header)
    return df.shape[0]

def human_time(seconds):
    if seconds is None or seconds <= 0:
        return "unknown"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m > 0:
        return f"{m}m{s:02d}s"
    else:
        return f"{s}s"

def progress_loop(reader, total_rows=None, out_path="-", columns=None, limit=None):
    rows_written = 0
    header_written = False
    t0 = time.time()
    out_handle = open_out(out_path)
    try:
        for df, meta in reader:
            if limit is not None and rows_written >= limit:
                break
            if limit is not None and rows_written + len(df) > limit:
                df = df.iloc[:(limit - rows_written)]
            if columns:
                keep = [c for c in columns if c in df.columns]
                df = df[keep]
            rows_written += write_df(df, out_handle, write_header=(not header_written))
            if not header_written:
                header_written = True

            elapsed = time.time() - t0
            rps = rows_written / elapsed if elapsed > 0 else 0.0
            if total_rows and total_rows > 0:
                pct = 100.0 * rows_written / total_rows
                rem = (total_rows - rows_written) / rps if rps > 0 else None
                eprint(f"Progress: {rows_written} rows ({pct:.2f}%)  rate={rps:,.0f} rows/s  ETA ~ {human_time(rem)}")
            else:
                eprint(f"Progress: {rows_written} rows  rate={rps:,.0f} rows/s")
    finally:
        if out_path != "-":
            out_handle.close()
    return rows_written

def convert_pyreadstat(sas_path, out_path, columns=None, chunksize=100000, limit=None, apply_labels=False):
    import pyreadstat
    # Metadata for row count
    total_rows = None
    try:
        _, meta = pyreadstat.read_sas7bdat(sas_path, row_limit=1)
        total_rows = getattr(meta, "number_rows", None)
        if total_rows:
            eprint("Total rows (from metadata):", total_rows)
    except Exception as ex:
        eprint("Note: could not get metadata row count:", str(ex))

    # Try building chunked reader, with or without apply_value_formats
    reader = None
    try:
        if apply_labels:
            reader = pyreadstat.read_file_in_chunks(
                pyreadstat.read_sas7bdat,
                sas_path,
                usecols=columns,
                chunksize=chunksize,
                apply_value_formats=True
            )
        else:
            reader = pyreadstat.read_file_in_chunks(
                pyreadstat.read_sas7bdat,
                sas_path,
                usecols=columns,
                chunksize=chunksize
            )
    except TypeError:
        eprint("Warning: this pyreadstat version does not accept apply_value_formats; continuing without it.")
        reader = pyreadstat.read_file_in_chunks(
            pyreadstat.read_sas7bdat,
            sas_path,
            usecols=columns,
            chunksize=chunksize
        )

    eprint("Using pyreadstat chunked reader")
    return progress_loop(reader, total_rows=total_rows, out_path=out_path, columns=columns, limit=limit)

def convert_pandas(sas_path, out_path, columns=None, limit=None, encoding=None):
    import pandas as pd
    eprint("Using pandas.read_sas (no chunking). Some SAS compressions are unsupported here.")
    df = pd.read_sas(sas_path, format="sas7bdat", encoding=encoding)
    if columns:
        keep = [c for c in columns if c in df.columns]
        df = df[keep]
    if limit is not None:
        df = df.iloc[:limit]
    out_handle = open_out(out_path)
    try:
        df.to_csv(out_handle, index=False)
    finally:
        if out_path != "-":
            out_handle.close()
    return len(df)

def inspect_schema_pyreadstat(sas_path):
    import pyreadstat
    _, meta = pyreadstat.read_sas7bdat(sas_path, row_limit=0)
    eprint("Variables:", len(meta.column_names))
    for i, (name, label, fmt, typ) in enumerate(zip(meta.column_names, meta.column_labels, meta.column_formats, meta.column_types)):
        if i >= 50:
            eprint("... (truncated)")
            break
        eprint(f"{i+1:03d} {name}  type={typ}  format={fmt}  label={label}")

def main():
    ap = argparse.ArgumentParser(description="Convert SAS .sas7bdat to CSV with live progress and schema inspection.")
    ap.add_argument("--sas", required=True, help="Path to .sas7bdat file")
    ap.add_argument("--out", default="-", help="Path to CSV output or '-' for STDOUT ('.gz' for gzip)")
    ap.add_argument("--columns", nargs="*", default=None, help="Optional list of column names to keep")
    ap.add_argument("--chunksize", type=int, default=100000, help="Rows per chunk (pyreadstat only)")
    ap.add_argument("--limit", type=int, default=None, help="Optional max number of rows to write")
    ap.add_argument("--apply-labels", action="store_true", help="Apply value labels (if supported by pyreadstat)")
    ap.add_argument("--encoding", default=None, help="Encoding hint for pandas fallback")
    ap.add_argument("--engine", choices=["pyreadstat","pandas"], default="pyreadstat", help="Backend to use")
    ap.add_argument("--inspect", action="store_true", help="Print schema and exit (pyreadstat only)")
    args = ap.parse_args()

    if args.inspect:
        try:
            import pyreadstat
            inspect_schema_pyreadstat(args.sas)
            return
        except ImportError:
            eprint("pyreadstat not installed; install it or run without --inspect.")
            return

    if args.engine == "pyreadstat":
        try:
            import pyreadstat
        except ImportError:
            eprint("pyreadstat is required for engine=pyreadstat. Install with:")
            eprint("  pip install pyreadstat")
            sys.exit(2)
        rows = convert_pyreadstat(args.sas, args.out, columns=args.columns,
                                  chunksize=args.chunksize, limit=args.limit,
                                  apply_labels=args.apply_labels)
        eprint("Done. Rows written:", rows)
    else:
        rows = convert_pandas(args.sas, args.out, columns=args.columns,
                              limit=args.limit, encoding=args.encoding)
        eprint("Done. Rows written:", rows)

if __name__ == "__main__":
    main()
