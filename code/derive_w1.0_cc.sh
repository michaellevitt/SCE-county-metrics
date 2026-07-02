#!/bin/sh
# ============================================================================
# derive_w1.0_cc.sh  --  regenerate the two curated CC inputs consumed by
# run_standard_k120_w1.0.sh, from raw data, using the from-raw pipeline code:
#
#     full_w1.0/metric_x_death_cc_1.0_0.csv   (metric x death CC)
#     full_w1.0/full_cc_ase0_p=1.0_0.csv      (full metric x metric CC matrix)
#
# BOTH are computed on OWN-YEAR normalization (each extensive metric divided by
# its own metric-year county population) and POPULATION_2019 weighting at
# power 1.0 -- the project's standard "w1.0" condition.
#
# This is the faithful recipe.  Note it differs from 0000_Run_USCounty-v10.1.sh
# in two ways:
#   1. the death-CC step passes  --weight-col population_2019  (0000 omits it and
#      defaults to ased_bl_2019);
#   2. normalization is OWN-YEAR (--peryear-pop / --metric-year), not plain 2019.
#
# Verified: both outputs match the manuscript curated files to max abs diff 0.0
# (once the matrix is put on own-year normalization).
#
# Run from the repo root:  sh code/derive_w1.0_cc.sh
# ============================================================================
set -e
cd "$(dirname "$0")/.." || exit 1
PATH=/opt/homebrew/bin:$PATH; export PATH        # need a Python with working numpy

METHOD="${1:-pearson}"     # pearson (default) | spearman -- correlation type for both CC steps
RANKMODE="${2:-weighted}"  # weighted (default, proper) | plain -- ranking for spearman
echo ">>> correlation method: $METHOD   (spearman rank-mode: $RANKMODE)"

NEW=BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NEW.csv
NORMED=BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv
CLASSIF=hub_members_extensive_intensive.csv
CP=data/raw/census_pop
OUT=full_w1.0
DEATH_CC=$OUT/metric_x_death_cc_1.0_0.csv
CC_MATRIX=$OUT/full_cc_ase0_p=1.0_0.csv
METRICS=/tmp/derive_w1.0_metrics.txt
mkdir -p "$OUT"

echo "--- 1. assemble merged BEN file (Step 01) ---"
python3 code/00_assemble_merged_BEN_file_v7.py > /tmp/derive_s01.log 2>&1

echo "--- 2. normalize EXTENSIVE metrics, OWN-YEAR population (Step 02 + --peryear-pop) ---"
python3 code/normalize_extensive_metrics_v3.py --input "$NEW" --output "$NORMED" \
    --classification "$CLASSIF" \
    --peryear-pop "$CP/county_pop_by_year_2000_2024.csv" \
    --metric-year "$CP/metric_year_map.csv" > /tmp/derive_s02.log 2>&1

echo "--- 3. metric x death CC  (population_2019 ^ 1.0, all counties) ---"
cat "$NORMED" | python3 code/calc_metric_death_cc_v4.py \
    --weight-col population_2019 --weight-power 1.0 --min-ased-bl 0 \
    --method "$METHOD" --rank-mode "$RANKMODE" \
    --lp-threshold -5.0 --output "$DEATH_CC" > /tmp/derive_s06.log 2>&1
cut -d',' -f1 "$DEATH_CC" > "$METRICS"

echo "--- 4. full metric x metric CC matrix  (population_2019 ^ 1.0) ---"
cat "$NORMED" | python3 code/09a_compute_cc_matrix.py \
    --metrics-file "$METRICS" --weight-col population_2019 --threshold 0 --power 1.0 \
    --method "$METHOD" --rank-mode "$RANKMODE" \
    --output "$CC_MATRIX" > /tmp/derive_s10.log 2>&1

echo "--- 5. XDE Ward clustering (k=100) from the own-year matrix ---"
# Produces the curated artifacts run_standard reads from full_w1.0/ward_xde_2745/:
#   Z_med_xde100.npy, medoid_list_xde100.json, xde100_reps.csv, xde100_assignments.csv
# (also writes bulky extras -- cc_sub.npy, PNGs, medoid_analysis_k100.xlsx --
#  which build_minimal_repo.sh prunes; only the 4 files above are inputs.)
python3 code/ward_medoid_ccbs_v4.py --cc-matrix "$CC_MATRIX" --death-cc "$DEATH_CC" \
    --explain data/BEN_MERGED_MEASURES_explain_extended_2745.csv \
    --ward-k-list 100 --out-dir "$OUT/ward_xde_2745/" > /tmp/derive_s11.log 2>&1

echo "=== DONE ==="
ls -la "$DEATH_CC" "$CC_MATRIX" "$OUT/ward_xde_2745/xde100_assignments.csv" | awk '{print "  ", $5, $NF}'
echo "(logs: /tmp/derive_s0{1,2,6}.log, /tmp/derive_s1{0,1}.log)"
