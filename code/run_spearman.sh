#!/bin/sh
# ============================================================================
# run_spearman.sh  --  Spearman-correlation SENSITIVITY run (paper Table S8 /
# "Sensitivity analysis on the correlation method").
#
# The primary analysis is Pearson; the committed full_w1.0/ CC files are Pearson.
# This script regenerates the CC files under population-weighted SPEARMAN
# (weighted-ECDF ranks), rebuilds all tables + figures into *_spearman outputs,
# preserves the Spearman death-CC for the Pearson-vs-Spearman comparison, and
# then RESTORES the committed Pearson full_w1.0/ inputs (via an EXIT trap, so
# the Pearson primary is restored even if the run is interrupted).
#
# Like run_all.sh / derive_w1.0_cc.sh, this rebuilds from raw and therefore needs
# the AHRF source file in data/raw/ (see README "AHRF data (not included)").
#
# Run from the repo root:  sh code/run_spearman.sh
# Then:                    sh code/make_spearman_comparison.py   (builds Table S8)
# ============================================================================
set -e
cd "$(dirname "$0")/.." || exit 1
PATH=/opt/homebrew/bin:$PATH; export PATH

OUT=full_w1.0
BK=/tmp/full_w1.0_pearson_bak
XDE="Z_med_xde100.npy medoid_list_xde100.json xde100_reps.csv xde100_assignments.csv"

# ---- back up the committed Pearson curated inputs ----
rm -rf "$BK"; mkdir -p "$BK/ward_xde_2745"
cp -p "$OUT/metric_x_death_cc_1.0_0.csv" "$OUT/full_cc_ase0_p=1.0_0.csv" "$BK/"
for f in $XDE; do cp -p "$OUT/ward_xde_2745/$f" "$BK/ward_xde_2745/"; done

restore() {
  echo "--- restoring committed Pearson full_w1.0/ inputs ---"
  cp -p "$BK/metric_x_death_cc_1.0_0.csv" "$BK/full_cc_ase0_p=1.0_0.csv" "$OUT/" 2>/dev/null || true
  for f in $XDE; do cp -p "$BK/ward_xde_2745/$f" "$OUT/ward_xde_2745/" 2>/dev/null || true; done
}
trap restore EXIT

# ---- 1. regenerate CC + XDE clustering under weighted Spearman ----
echo "############ Spearman derive (weighted ranks) ############"
sh code/derive_w1.0_cc.sh spearman weighted

# ---- 2. preserve the Spearman death-CC for the comparison (Table S8) ----
mkdir -p spearman_results
cp -p "$OUT/metric_x_death_cc_1.0_0.csv" spearman_results/metric_x_death_cc_1.0_0.csv

# ---- 3. build all tables + figures on the Spearman inputs ----
echo "############ run_standard on Spearman inputs ############"
sh code/run_standard_k120_w1.0.sh figures_2745_spearman

# ---- 4. rename the Spearman table workbooks so they don't clobber Pearson ----
for f in master_sem_clusters_clean2_k120_w1.0 extra_tables_clean2_k120_w1.0 \
         sem_best_lp_clean2_k120_w1.0 SCE_paper_tables_consolidated_clean2_k120_w1.0; do
  [ -f "$f.xlsx" ] && mv -f "$f.xlsx" "${f}_spearman.xlsx"
done

echo "=== Spearman sensitivity run DONE ==="
echo "  spearman tables : *_spearman.xlsx"
echo "  spearman figures: figures_2745_spearman/"
echo "  spearman death-CC (for comparison): spearman_results/metric_x_death_cc_1.0_0.csv"
echo "  (Pearson full_w1.0/ inputs are restored on exit)"
echo "  next: python3 code/make_spearman_comparison.py   -> Table S8 + supplement workbook"
