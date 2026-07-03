#!/usr/bin/env python3
"""
regen_supp_tsv_s7top6_s8.py

Regenerates the two CC-dependent supplementary TSVs that build_paper_docx.js READS
(no other generator for them existed in the repo as of 2026-06-21; reconstructed then):

  Supplementary_Tables_Figures/Table_S4_top6_metrics_per_supercluster.tsv
      Per super-cluster, the top metrics of its semantic clusters whose representative
      reaches |CC| > 0.30, up to 6, ranked by max|CC| desc. Columns:
        SC, Super-cluster, Rank, Metric (explain), metric_code, CC (signed, 2dp),
        year, n_collapsed
      n_collapsed = (# metrics in that representative's semantic cluster with
        max|CC| over 2020-2024 > 0.30) - 1   [verified: matches the legacy file exactly]
      SC blocks are ordered by Table-1 % |CC|>0.30 (descending). An SC with no
      cluster reaching 0.30 emits one "(none significant)" row.

  Supplementary_Tables_Figures/Table_S5_age_band_divergence.tsv
      Per pandemic year: count of metrics (2,727 basis) with |CC| > 0.30 and the
      single largest |CC|, for all-age / <65 / >=65 death measures.

Inputs (all from the STANDARD own-year pipeline, run_standard_k120_w1.0.sh):
  full_w1.0/metric_x_death_cc_1.0_0.csv                       (primary CC, own-year norm)
  ward_sem_clean2_k120/ward_sem_metrics.csv                   (metric -> semantic cluster)
  ward_sem_clean2_k120/top_metric_per_cluster_2020_2024_w1.0.tsv  (StepF: per-cluster top metric)

Run from the SANDBOX6 root:  python3 code/regen_supp_tsv_s7top6_s8.py
Then rebuild the docx.  SC_ORDER must track Table 1's order in build_paper_docx.js.
"""
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Supplementary_Tables_Figures")
os.makedirs(OUT, exist_ok=True)
YEARS = [2020, 2021, 2022, 2023, 2024]
ALLAGE = [f"asedx_p_{y}" for y in YEARS]
SC_ORDER = [3, 5, 8, 1, 2, 9, 4, 6, 7, 11, 10]   # Table-1 order, % |CC|>0.30 desc (own-year)

cc = pd.read_csv(os.path.join(ROOT, "full_w1.0/metric_x_death_cc_1.0_0.csv"))
mcol = "metric" if "metric" in cc.columns else cc.columns[0]
for c in ALLAGE:
    cc[c] = pd.to_numeric(cc[c], errors="coerce")
cc["_mx"] = cc[ALLAGE].abs().max(axis=1)

wm = pd.read_csv(os.path.join(ROOT, "ward_sem_clean2_k120/ward_sem_metrics.csv"))
m = wm.merge(cc[[mcol, "_mx"]], left_on="metric", right_on=mcol, how="left")
clu_n30 = m[m["_mx"] > 0.30].groupby("semantic_cluster_id").size().to_dict()

top = pd.read_csv(os.path.join(ROOT, "ward_sem_clean2_k120/top_metric_per_cluster_2020_2024_w1.0.tsv"), sep="\t")
scname = dict(zip(top["sc_id"], top["sc_name"]))

# ---- Table S7 top-6 ----
rows = ["\t".join(["SC", "Super-cluster", "Rank", "Metric (explain)", "metric_code", "CC", "year", "n_collapsed"])]
for sc in SC_ORDER:
    g = top[(top["sc_id"] == sc) & (top["max_abs_cc"] > 0.30)].sort_values("max_abs_cc", ascending=False).head(6)
    if len(g) == 0:
        rows.append("\t".join([str(sc), scname[sc], "-", "(none significant)", "-", "-", "-", "-"]))
        continue
    for i, (_, r) in enumerate(g.iterrows(), 1):
        ncol = clu_n30.get(r["cluster"], 1) - 1
        rows.append("\t".join([
            str(sc) if i == 1 else "", scname[sc] if i == 1 else "", str(i),
            str(r["explain"]), str(r["metric"]), f"{r['cc_at_best']:+.2f}",
            str(int(r["best_year"])), str(int(ncol))]))
with open(os.path.join(OUT, "Table_S4_top6_metrics_per_supercluster.tsv"), "w") as f:
    f.write("\n".join(rows) + "\n")
print(f"WROTE Table_S4_top6_metrics_per_supercluster.tsv ({len(rows)-1} rows)")

# ---- Table S8 age-band divergence (2,727 basis) ----
clus = set(wm["metric"].astype(str))
d = cc[cc[mcol].astype(str).isin(clus)].copy()
s8 = ["\t".join(["Year", "All n", "<65 n", ">=65 n", "All max", "<65 max", ">=65 max"])]
for y in YEARS:
    a = d[f"asedx_p_{y}"].abs(); lt = d[f"asedx_p_{y}_LT65"].abs(); ge = d[f"asedx_p_{y}_GE65"].abs()
    s8.append("\t".join([str(y), str(int((a > 0.30).sum())), str(int((lt > 0.30).sum())),
                         str(int((ge > 0.30).sum())), f"{a.max():.2f}", f"{lt.max():.2f}", f"{ge.max():.2f}"]))
with open(os.path.join(OUT, "Table_S5_age_band_divergence.tsv"), "w") as f:
    f.write("\n".join(s8) + "\n")
print("WROTE Table_S5_age_band_divergence.tsv")
