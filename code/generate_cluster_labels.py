# generate_cluster_labels.py
# Uses Claude API to generate short descriptive labels for each cluster
# by reading ALL member explain texts (not just the medoid).
#
# Works for both CC and linguistic XDE clusterings.
# On second pass: supply --existing-labels to show Claude the current label
# and ask it to improve.
#
# Usage (first pass):
#   python3 generate_cluster_labels.py \
#     --assignments  xde100_assignments_ling.csv \
#     --reps-csv     xde100_reps_ling.csv \
#     --extended-explain BEN_MERGED_MEASURES_explain_extended.csv \
#     --out          xde100_labels_ling.csv \
#     --tag          ling
#
# Usage (second pass / improve existing):
#   python3 generate_cluster_labels.py \
#     --assignments  xde100_assignments_ling.csv \
#     --reps-csv     xde100_reps_ling.csv \
#     --extended-explain BEN_MERGED_MEASURES_explain_extended.csv \
#     --existing-labels xde100_labels_ling.csv \
#     --out          xde100_labels_ling_v2.csv \
#     --tag          ling
#
# Output CSV columns:
#   cluster_id, cluster_size, medoid, medoid_explain,
#   label_proposed, label_existing (if --existing-labels supplied),
#   member_explains (semicolon-separated, truncated)

import argparse
import json
import os
import sys
import sys
import time

import numpy as np
import pandas as pd
import requests

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



def log(msg):
    formatted = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(formatted, flush=True)
    print(formatted, flush=True, file=sys.stderr)


def call_claude(prompt, model="claude-sonnet-4-20250514", max_tokens=200):
    """Call Claude API and return response text."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Run: setenv ANTHROPIC_API_KEY sk-ant-...")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "system": (
            "You are a concise scientific labeller for epidemiological research. "
            "You produce short, precise, noun-phrase labels (4-8 words) that "
            "describe the content of a group of health metrics. "
            "Labels must be in plain English with no jargon abbreviations. "
            "Respond with ONLY the label text -- no explanation, no punctuation at end, "
            "no quotes, no numbering."
        ),
    }
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"].strip()


def build_prompt_first_pass(cluster_id, cluster_size, medoid_explain,
                             member_explains, tag):
    member_block = "\n".join(f"  - {e}" for e in member_explains)
    return (
        f"I have a cluster of {cluster_size} health/demographic metrics "
        f"from a US county-level dataset ({tag} clustering).\n\n"
        f"The central metric (medoid), given only as a reference point, is:\n  {medoid_explain}\n\n"
        f"All {len(member_explains)} member metric descriptions:\n{member_block}\n\n"
        f"Write a single short label (4-8 words) that best describes "
        f"what this cluster of metrics measures as a group. "
        f"Base the label on the FULL set of members above, not just the medoid. "
        f"Be specific -- avoid vague terms like 'health metrics' or 'population data'. "
        f"Capture the dominant theme. If the cluster spans multiple sub-themes, "
        f"name the dominant one."
    )


def build_prompt_second_pass(cluster_id, cluster_size, medoid_explain,
                              member_explains, existing_label, tag):
    member_block = "\n".join(f"  - {e}" for e in member_explains)
    return (
        f"I have a cluster of {cluster_size} health/demographic metrics "
        f"from a US county-level dataset ({tag} clustering).\n\n"
        f"The central metric (medoid), given only as a reference point, is:\n  {medoid_explain}\n\n"
        f"All {len(member_explains)} member metric descriptions:\n{member_block}\n\n"
        f"The current label for this cluster is:\n  \"{existing_label}\"\n\n"
        f"Improve this label if needed, judging it against the FULL set of members "
        f"above rather than the medoid alone. "
        f"It should be 4-8 words, specific, "
        f"in plain English with no abbreviations. "
        f"If the current label is already good, return it unchanged. "
        f"If it is vague, too long, uses abbreviations, or misses the main theme, "
        f"write a better one. "
        f"Respond with ONLY the label text."
    )


def clean_explain(s):
    if not isinstance(s, str):
        return str(s)
    if '=' in s:
        s = s[:s.index('=')]
    return s.strip().rstrip('_').rstrip('-').strip()


def main():
    parser = argparse.ArgumentParser(
        description='Generate cluster labels via Claude API from member explain texts.')
    parser.add_argument('--cluster-col',      default=None,
                        help='Column name for cluster ID in assignments CSV (auto-detected if not set)')
    parser.add_argument('--assignments',      required=True,
                        help='ward{k}_assignments_{label}.csv')
    parser.add_argument('--reps-csv',         required=True,
                        help='ward{k}_reps_{label}.csv')
    parser.add_argument('--extended-explain', required=True,
                        help='BEN_MERGED_MEASURES_explain_extended.csv')
    parser.add_argument('--out',              required=True,
                        help='Output CSV path')
    parser.add_argument('--tag',              default='',
                        help='Short tag describing clustering type, e.g. "ling" or "cc"')
    parser.add_argument('--existing-labels',  default=None,
                        help='CSV from a previous run; triggers second-pass improvement')
    parser.add_argument('--delay',  type=float, default=0.5,
                        help='Seconds to wait between API calls (default 0.5)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from --out if it exists; skip already-done clusters')
    args = parser.parse_args()

    # ---- Load data ----
    log("Loading data...")
    assign = pd.read_csv(args.assignments)
    reps   = pd.read_csv(args.reps_csv)
    ext    = pd.read_csv(args.extended_explain)

    if args.cluster_col:
        ward_col = args.cluster_col
    else:
        ward_col = next((c for c in assign.columns if c.startswith('Ward')
                        or c in ('cluster_id','semantic_cluster','cluster',
                                 'semantic_cluster_id')), None)
    if ward_col is None:
        sys.exit(f'ERROR: cannot find cluster ID column in assignments CSV. '
                 f'Columns: {list(assign.columns)}. Use --cluster-col to specify.')
    explain  = dict(zip(ext['metric'], ext['explain'].fillna('')))

    reps_col = next((c for c in reps.columns if c.startswith('Ward')
                    or c in ('cluster_id','semantic_cluster','cluster',
                             'semantic_cluster_id')), None)
    if reps_col is None:
        sys.exit('ERROR: cannot find cluster ID column in reps CSV')
    medoid_col = 'medoid' if 'medoid' in reps.columns else \
                 'medoid_metric' if 'medoid_metric' in reps.columns else None
    if medoid_col is None:
        sys.exit(f'ERROR: no medoid column in reps CSV. Columns: {list(reps.columns)}')
    size_col = 'cluster_size' if 'cluster_size' in reps.columns else \
               'size' if 'size' in reps.columns else None
    medoid_map     = dict(zip(reps[reps_col], reps[medoid_col]))
    cluster_sizes  = dict(zip(reps[reps_col], reps[size_col])) if size_col else {}

    # Build member explain lists per cluster
    cluster_members = {}
    for _, row in assign.iterrows():
        cid = row[ward_col]
        m   = row['metric']
        cluster_members.setdefault(cid, []).append(m)

    cluster_ids = sorted(cluster_members.keys())
    log(f"  {len(cluster_ids)} clusters to label")
    log(f"  Estimated time: ~{len(cluster_ids)*0.5/60:.0f}-{len(cluster_ids)*1.5/60:.0f} min at 0.5-1.5s per cluster")

    # Load existing labels if second pass
    existing = {}
    if args.existing_labels and os.path.exists(args.existing_labels):
        ex_df = pd.read_csv(args.existing_labels)
        if 'label_proposed' in ex_df.columns:
            existing = dict(zip(ex_df['cluster_id'], ex_df['label_proposed']))
        log(f"  Loaded {len(existing)} existing labels for second pass")

    # Load already-done results if resuming
    done = {}
    if args.resume and os.path.exists(args.out):
        done_df = pd.read_csv(args.out)
        done = dict(zip(done_df['cluster_id'], done_df['label_proposed']))
        log(f"  Resuming: {len(done)} clusters already done")

    # ---- Main loop ----
    rows = []
    for i, cid in enumerate(cluster_ids):
        members       = cluster_members[cid]
        medoid        = medoid_map.get(cid, members[0])
        medoid_explain = clean_explain(explain.get(medoid, medoid))
        size           = cluster_sizes.get(cid, len(members))
        member_explains = [clean_explain(explain.get(m, m)) for m in members]
        # De-duplicate while preserving order: every DISTINCT member description
        # is shown to the model (no truncation), identical strings add nothing.
        _seen = set()
        member_explains = [e for e in member_explains
                           if not (e in _seen or _seen.add(e))]

        # Resume: skip if already done
        if cid in done:
            ex_lbl = existing.get(cid, '')
            rows.append({
                'cluster_id':      cid,
                'cluster_size':    size,
                'medoid':          medoid,
                'medoid_explain':  medoid_explain,
                'label_existing':  ex_lbl,
                'label_proposed':  done[cid],
                'member_explains': '; '.join(member_explains[:20]),
            })
            continue

        # Build prompt
        ex_lbl = existing.get(cid, '')
        if ex_lbl:
            prompt = build_prompt_second_pass(
                cid, size, medoid_explain, member_explains, ex_lbl, args.tag)
            mode = 'improve'
        else:
            prompt = build_prompt_first_pass(
                cid, size, medoid_explain, member_explains, args.tag)
            mode = 'new'

        # Call API
        try:
            label = call_claude(prompt)
            log(f"  [{i+1:3d}/{len(cluster_ids)}] C{cid:3d} ({size:3d} members) "
                f"[{mode}] -> {label}")
        except Exception as e:
            label = ex_lbl if ex_lbl else medoid_explain[:60]
            log(f"  [{i+1:3d}/{len(cluster_ids)}] C{cid:3d} ERROR: {e} -> fallback: {label}")

        rows.append({
            'cluster_id':      cid,
            'cluster_size':    size,
            'medoid':          medoid,
            'medoid_explain':  medoid_explain,
            'label_existing':  ex_lbl,
            'label_proposed':  label,
            'member_explains': '; '.join(member_explains[:20]),
        })

        # Save incrementally every 10 clusters
        if (i + 1) % 10 == 0:
            pd.DataFrame(rows).to_csv(args.out, index=False)
            log(f"  [checkpoint] Saved {len(rows)} rows to {args.out}")

        time.sleep(args.delay)

    # Final save
    out_df = pd.DataFrame(rows)
    out_df.to_csv(args.out, index=False)
    _tee(args.out)
    log(f"\nDone. {len(out_df)} clusters labelled -> {args.out}")

    # Print summary
    print("\nFINAL LABELS:")
    print(f"{'C':>4} {'n':>4}  {'label'}")
    print("-" * 80)
    for _, r in out_df.iterrows():
        print(f"C{int(r['cluster_id']):>3} {int(r['cluster_size']):>4}  {r['label_proposed']}")


if __name__ == '__main__':
    main()
