#!/usr/bin/env python3
"""
vintage_cc_continuous.py  --  continuous cross-vintage robustness (Item 4 / JPAI comment 26)

Compares the per-metric metric x death correlations between the main analysis (2019
predictor vintage) and the two sensitivity vintages (latest <=2015; AHRF 2023-2024
release, predictors ~2022), using the corrected population_2019-weighted CC files.

IMPORTANT (matching / what is actually tested):
  Metrics are matched across vintages by base code (f-code minus its last two year
  digits). The 2022 ("post-pandemic") build reuses the SAME f-code column names as the
  2019 baseline and only swaps the underlying county VALUES to the >=2021 vintage where
  one exists (via the AHRF 2023-2024 crosswalk); the 2015 build rolls the latest-year
  cutoff back. Consequently a large fraction of matched metrics are IDENTICAL by
  construction (never refreshed / not rolled back). Those identical metrics are
  EXCLUDED here, so the reported correlations, sign-flips and agreement describe only
  metrics whose vintage value genuinely changed -- the real vintage test.

Per metric: signed CC (all-age) for each pandemic year 2020-2024; the comparison value
is the signed CC at the year of maximum |CC| IN THE 2019 (reference) vintage.
Outputs: a 2-panel scatter PNG and a stats TSV in Supplementary_Tables_Figures/.
"""
import csv, re, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, spearmanr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# NOTE: per JPAI (v23 comment 63), ALL THREE builds are now normalized on each variable's
# OWN-YEAR county population (not a fixed 2019 denominator). 2019 = live own-year primary;
# 2015 and 2022 = the own-year-renormalized vintage builds (code/renorm_vintage_ownyear path).
FILES = {
    "2015": os.path.join(ROOT, "cutoff_2015/metric_x_death_cc_2015_ownyear_1.0_0.csv"),
    "2019": os.path.join(ROOT, "full_w1.0/metric_x_death_cc_1.0_0.csv"),
    "2022": os.path.join(ROOT, "postpandemic_2022/POST_full_cc_ownyear_1.0_0.csv"),
}
YEARS = ["2020", "2021", "2022", "2023", "2024"]
MOD = 0.30
ATOL = 1e-6
OUTDIR = os.path.join(ROOT, "Supplementary_Tables_Figures")


def base_code(m):
    return m[:-2] if re.match(r"^f\d{7}$", m) else m


def load(path):
    """base code -> full signed CC vector (len 5) for its max-|CC| representative metric."""
    out = {}
    cols = ["asedx_p_" + y for y in YEARS]
    with open(path) as fh:
        for row in csv.DictReader(fh):
            vals = []
            for c in cols:
                v = row.get(c, "")
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    vals.append(np.nan)
            vals = np.array(vals, float)
            if np.all(np.isnan(vals)):
                continue
            mx = np.nanmax(np.abs(vals))
            k = base_code(row["metric"])
            if k not in out or mx > out[k][1]:
                out[k] = (vals, mx)
    return {k: v[0] for k, v in out.items()}


data = {v: load(p) for v, p in FILES.items()}
for v in FILES:
    print(f"{v}: {len(data[v])} base codes")


def compare(other):
    """ref vintage is always 2019; 'other' is 2015 or 2022."""
    ref = data["2019"]; oth = data[other]
    keys = sorted(set(ref) & set(oth))
    vr = np.array([ref[k] for k in keys])      # (n,5)
    vo = np.array([oth[k] for k in keys])
    # identical-by-construction: full year-vector equal (NaNs treated equal)
    identical = np.array([np.allclose(vr[i], vo[i], atol=ATOL, equal_nan=True)
                          for i in range(len(keys))])
    diff = ~identical
    # comparison value = each vintage's OWN headline value: signed CC at its own
    # argmax-|CC| year (i.e. the per-metric "correlation with death" in that vintage,
    # the max-|CC| summary used throughout the paper). Not anchored to one year, to
    # avoid circularly inflating the agreement.
    x = np.array([vr[i][int(np.nanargmax(np.abs(vr[i])))] for i in range(len(keys))])  # 2019
    y = np.array([vo[i][int(np.nanargmax(np.abs(vo[i])))] for i in range(len(keys))])  # other
    xd, yd = x[diff], y[diff]
    # sign flips among differing metrics with |CC_2019| > 0.30
    strong = np.abs(xd) > MOD
    flips = int(np.sum(np.sign(xd[strong]) != np.sign(yd[strong])))
    # binary moderate-association agreement on the DIFFERING subset (for Table S2)
    ca = np.abs(xd) > MOD; cb = np.abs(yd) > MOD
    return {
        "other": other, "x": xd, "y": yd,
        "n_matched": len(keys), "n_identical": int(identical.sum()),
        "n_diff": int(diff.sum()),
        "pearson": pearsonr(xd, yd)[0], "spearman": spearmanr(xd, yd)[0],
        "n_strong": int(strong.sum()), "n_flips": flips,
        "mod_both": int(np.sum(ca & cb)), "neither_both": int(np.sum(~ca & ~cb)),
        "agree_pct": 100.0 * np.mean(ca == cb),
    }


r15 = compare("2015")
r22 = compare("2022")

os.makedirs(OUTDIR, exist_ok=True)
with open(os.path.join(OUTDIR, "Table_vintage_continuous.tsv"), "w") as f:
    f.write("comparison\tmatched\tidentical_by_construction\tdiffering(tested)\t"
            "pearson_signed\tspearman_signed\tn_|CC|>0.30\tsign_flips\t"
            "moderate_both\tneither_both\tbinary_agreement_%\n")
    for r, nm in ((r15, "2019 vs 2015 (backward)"), (r22, "2019 vs 2023-2024 (forward)")):
        f.write(f"{nm}\t{r['n_matched']}\t{r['n_identical']}\t{r['n_diff']}\t"
                f"{r['pearson']:.3f}\t{r['spearman']:.3f}\t{r['n_strong']}\t{r['n_flips']}\t"
                f"{r['mod_both']}\t{r['neither_both']}\t{r['agree_pct']:.1f}\n")

# ---- 2-panel scatter, DIFFERING metrics only ----
fig, axes = plt.subplots(1, 2, figsize=(11, 5.4))
for ax, r, yl, title in [
    (axes[0], r15, "r (latest ≤2015)", "2019 vs 2015 (backward)"),
    (axes[1], r22, "r (AHRF 2023–2024)", "2019 vs 2023-2024 (forward)")]:
    x, y = r["x"], r["y"]
    agree = np.sign(x) == np.sign(y)
    ax.axhline(0, color="#bbbbbb", lw=0.6); ax.axvline(0, color="#bbbbbb", lw=0.6)
    ax.plot([-0.6, 0.6], [-0.6, 0.6], color="#888888", lw=0.8, ls="--", zorder=1)
    for v in (MOD, -MOD):
        ax.axvline(v, color="#e0b0b0", lw=0.6, ls=":"); ax.axhline(v, color="#e0b0b0", lw=0.6, ls=":")
    ax.scatter(x[agree], y[agree], s=8, c="#1f4e79", alpha=0.45, lw=0, label="sign agrees")
    ax.scatter(x[~agree], y[~agree], s=11, c="#d62728", alpha=0.85, lw=0, label="sign flip")
    ax.set_xlim(-0.6, 0.6); ax.set_ylim(-0.6, 0.6); ax.set_aspect("equal")
    ax.set_xlabel("r (main analysis, 2019)"); ax.set_ylabel(yl)
    ax.set_title(title, fontsize=11, fontweight="bold")
    txt = (f"changed variables n={r['n_diff']}\n(identical excluded: {r['n_identical']})\n"
           f"Pearson={r['pearson']:.2f}  Spearman={r['spearman']:.2f}\n"
           f"sign flips |CC|>0.30: {r['n_flips']}/{r['n_strong']}")
    ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", ha="left", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cccccc", alpha=0.9))
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
fig.suptitle("Cross-vintage stability of per-variable signed correlation with excess death — "
             "variables whose vintage value actually changed (identical-by-construction excluded)",
             fontsize=10.5)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(OUTDIR, "cc_vintage_scatter.png"), dpi=300,
            bbox_inches="tight", facecolor="white")

for r, nm in ((r15, "2019 vs 2015"), (r22, "2019 vs 2023-2024")):
    print(f"\n=== {nm} (DIFFERING subset) ===")
    print(f"  matched {r['n_matched']} | identical-by-construction {r['n_identical']} | "
          f"differing/tested {r['n_diff']}")
    print(f"  Pearson(signed)={r['pearson']:.3f}  Spearman(signed)={r['spearman']:.3f}")
    print(f"  |CC_2019|>0.30: {r['n_strong']}  sign flips: {r['n_flips']}")
    print(f"  binary agreement on differing: {r['agree_pct']:.1f}%  "
          f"(moderate-both {r['mod_both']}, neither-both {r['neither_both']})")
print("\nwrote cc_vintage_scatter.png and Table_vintage_continuous.tsv")
