import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
#!/usr/bin/env python3
"""
plot_cc_histograms.py

For each death measure, plot a histogram of |CC| values with 0.05-wide bins.
Bars are stacked: significant (LP <= -5) in a darker shade, non-significant lighter.

Usage:
  python plot_cc_histograms.py --input metric_x_death_0_25_cc.csv --output cc_histograms.png
"""

import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib as _mpl
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Glyph.*")
_mpl.rcParams['font.family'] = 'serif'
_mpl.rcParams['font.serif'] = ['Times New Roman', 'Palatino', 'Georgia', 'DejaVu Serif', 'serif']
import argparse

def save_fig(fig, path, dpi=200):
    """Save figure, adding the filename as a small label in the top margin."""
    import matplotlib.pyplot as plt
    fname = os.path.basename(path)
    fig.text(0.5, 0.995, fname, ha='center', va='top',
             fontsize=7, color='#888888', fontfamily='monospace',
             transform=fig.transFigure)
    """Save figure with filename in top margin."""
    fname = os.path.basename(path)
    fig.text(0.5, 0.995, fname, ha='center', va='top',
             fontsize=7, color='#888888', fontfamily='monospace',
             transform=fig.transFigure)
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor='white')
    import matplotlib.pyplot as plt
    plt.close(fig)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="cc_histograms.png")
    p.add_argument("--lp-threshold", type=float, default=-5.0,
                   help="LP threshold for significance (default: -5.0)")
    p.add_argument("--include-baseline", action="store_true", default=False,
                   help="Include pre-pandemic years 2017-2019 (excluded by default)")
    p.add_argument("--transpose", action="store_true", default=False,
                   help="Transpose layout: columns=years, rows=age groups (default: rows=years, cols=age)")
    p.add_argument("--cc-bands", action="store_true", default=True,
                   help="(default) Shade by |CC| bands: not / Significant / Very Significant")
    p.add_argument("--lp-stack", action="store_true", default=False,
                   help="Legacy: stack by LP significance instead of |CC| bands")
    p.add_argument("--cc-sig", type=float, default=0.3,
                   help="Lower |CC| for 'significant' band (default: 0.3)")
    p.add_argument("--cc-strong", type=float, default=0.5,
                   help="Lower |CC| for 'strongly significant' band (default: 0.5)")
    args = p.parse_args()

    df = pd.read_csv(args.input)

    # Identify CC columns (not LP_, not metric)
    cc_cols = [c for c in df.columns if not c.startswith("LP_") and c != "metric" and not c.startswith("Sum_")]

    # Organize by year/period and age group for nice grid layout
    # Parse structure: asedx_p_YYYY[_suffix]
    # Rows: year/period, Cols: All, GE65, LT65
    baseline_years = {"2017", "2018", "2019"}
    year_labels = []
    seen = set()
    for c in cc_cols:
        base = c.replace("asedx_p_", "")
        if base.endswith("_GE65"):
            yr = base.replace("_GE65", "")
        elif base.endswith("_LT65"):
            yr = base.replace("_LT65", "")
        else:
            yr = base
        if yr not in seen:
            seen.add(yr)
            if args.include_baseline or yr not in baseline_years:
                year_labels.append(yr)

    # Sort: single years first (ascending), then multi-year periods
    single = sorted([y for y in year_labels if '-' not in y])
    multi  = sorted([y for y in year_labels if '-' in y])
    year_labels = single + multi

    age_groups = ["All", "GE65", "LT65"]
    age_suffixes = {"All": "", "GE65": "_GE65", "LT65": "_LT65"}

    n_years = len(year_labels)
    n_ages = len(age_groups)

    # Determine global CC range across all death measures for shared x-axis
    all_cc_vals = []
    for c in cc_cols:
        all_cc_vals.extend(df[c].dropna().values)
    all_cc_vals = np.array(all_cc_vals)
    cc_lo = np.floor(np.min(all_cc_vals) * 20) / 20  # round down to nearest 0.05
    cc_hi = np.ceil(np.max(all_cc_vals) * 20) / 20    # round up to nearest 0.05

    bins = np.arange(cc_lo, cc_hi + 0.01, 0.01)

    if args.transpose:
        # Rows=age groups, Cols=years
        n_rows, n_cols = n_ages, n_years
        fig, axes = plt.subplots(n_rows, n_cols,
                                 figsize=(4.5 * n_cols, 4.5 * n_rows),
                                 sharey=False)
    else:
        # Rows=years, Cols=age groups
        n_rows, n_cols = n_years, n_ages
        fig, axes = plt.subplots(n_rows, n_cols,
                                 figsize=(4.5 * n_cols, 2.2 * n_rows),
                                 sharey=False)
    fig.subplots_adjust(hspace=0.06, wspace=0.05)
    if n_rows == 1:
        axes = axes.reshape(1, -1)
    if n_cols == 1:
        axes = axes.reshape(-1, 1)

    for yi, yr in enumerate(year_labels):
        for ai, ag in enumerate(age_groups):
            if args.transpose:
                ri, ci = ai, yi
            else:
                ri, ci = yi, ai
            ax = axes[ri, ci]
            suffix = age_suffixes[ag]
            cc_col = f"asedx_p_{yr}{suffix}"
            lp_col = f"LP_asedx_p_{yr}{suffix}"

            if cc_col not in df.columns:
                ax.set_visible(False)
                continue

            cc_vals = df[cc_col].dropna().values

            # Get matching LP values
            if lp_col in df.columns:
                lp_vals = df[lp_col].reindex(df[cc_col].dropna().index).values
            else:
                lp_vals = np.full_like(cc_vals, np.nan)

            if not args.lp_stack:
                # Shade by |CC| bands, ignoring p-value.
                acc = np.abs(cc_vals)
                cc_not    = cc_vals[acc < args.cc_sig]
                cc_sig    = cc_vals[(acc >= args.cc_sig) & (acc < args.cc_strong)]
                cc_strong = cc_vals[acc >= args.cc_strong]
                ax.hist([cc_not, cc_sig, cc_strong], bins=bins, stacked=True,
                        color=["#cfe2f3", "#1f4e79", "#e67e22"],
                        edgecolor="white", linewidth=0.4,
                        label=[f"|CC|<={args.cc_sig:g}",
                               f"Moderate ({args.cc_sig:g}-{args.cc_strong:g})",
                               f"Strong (>{args.cc_strong:g})"])
                n_sig_cum  = int((acc >= args.cc_sig).sum())     # |CC| > cc_sig  (incl. very)
                n_very_cum = int((acc >= args.cc_strong).sum())  # |CC| > cc_strong
                ax.text(0.97, 0.95,
                        f"{yr} {ag}\nMod>{args.cc_sig:g}={n_sig_cum}\nStrong>{args.cc_strong:g}={n_very_cum}",
                        transform=ax.transAxes, fontsize=10, fontweight='bold',
                        ha='right', va='top',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
            else:
                sig_mask = ~np.isnan(lp_vals) & (lp_vals <= args.lp_threshold)
                nonsig_mask = ~sig_mask

                cc_sig = cc_vals[sig_mask]
                cc_nonsig = cc_vals[nonsig_mask]

                # Stacked histogram
                ax.hist([cc_nonsig, cc_sig], bins=bins, stacked=True,
                        color=["#a8c8e8", "#1f4e79"],
                        edgecolor="white", linewidth=0.5,
                        label=["not sig", f"p<1e-5"])

                n_sig = len(cc_sig)
                ax.text(0.97, 0.95, f"{yr} {ag}\nsig={n_sig}",
                        transform=ax.transAxes, fontsize=10, fontweight='bold',
                        ha='right', va='top',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

            ax.set_yscale('log')
            ax.set_ylim(bottom=0.5)
            ax.set_xlim(cc_lo, cc_hi)
            ax.axvline(x=0, color='red', linewidth=0.7, linestyle='--', alpha=0.7)
            if not args.lp_stack:
                for xb in (args.cc_sig, args.cc_strong):
                    ax.axvline(x=xb,  color='#333333', linewidth=0.5, linestyle=':', alpha=0.6)
                    ax.axvline(x=-xb, color='#333333', linewidth=0.5, linestyle=':', alpha=0.6)

            if ri == n_rows - 1:
                ax.set_xlabel("CC", fontsize=16)
                ax.tick_params(axis='x', labelsize=14)
                # Remove last tick label on first 5 columns to avoid overlap
                if ci < n_cols - 1:
                    xticks = ax.get_xticks()
                    xlabels = [t.get_text() for t in ax.get_xticklabels()]
                    if len(xticks) > 1:
                        ax.set_xticks(xticks[:-1])
            else:
                ax.tick_params(axis='x', labelbottom=False)
            if ci == 0:
                ax.set_ylabel("Count (log10)", fontsize=16)
                ax.tick_params(axis='y', labelsize=14)
            else:
                ax.set_yticklabels([])
                ax.tick_params(axis='y', which='both', length=0)

    if args.cc_bands:
        _title = (f"CC distributions by death measure (bins=0.01).  "
                  f"moderate |CC| in [{args.cc_sig:g},{args.cc_strong:g}); "
                  f"strong |CC| in [{args.cc_strong:g},1]  (p-value ignored)")
    else:
        _title = f"CC distributions by death measure (bins=0.01, sig: LP <= {args.lp_threshold})"
    fig.suptitle(_title, fontsize=8, y=1.005)
    save_fig(fig, args.output, dpi=300)
    print(f"Saved {os.path.basename(args.output)}  [{os.path.dirname(os.path.abspath(args.output))}]", flush=True)
    print(f"Saved {os.path.basename(args.output)}  [{os.path.dirname(os.path.abspath(args.output))}]", flush=True, file=sys.stderr)

if __name__ == "__main__":
    main()
