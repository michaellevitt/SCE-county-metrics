#!/bin/sh
# derive_excl.sh
#
# The correlation steps of derive_w1.0_cc.sh (steps 3 to 5), rerun on the
# county-filtered normalized matrix written by code/exclusion_rules_v1.py, plus
# the alternative county weightings of Table S7.
#
# Order of a full rerun under the two county exclusions:
#   sh code/derive_w1.0_cc.sh                    # assemble and normalize, all counties
#   python3 code/exclusion_rules_v1.py \
#       --in  BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv \
#       --out BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv
#   sh code/derive_excl.sh pearson                # this script
#   sh code/run_standard_k120_w1.0.sh             # tables and figures
#
# Dropping counties after normalization is equivalent to dropping them before,
# because the 0-9,999 rescaling is linear and a correlation is unaffected by it.
#
# Usage: sh code/derive_excl.sh [pearson|spearman] [weighted|unweighted]
set -e
cd "$(dirname "$0")/.." || exit 1
METHOD="${1:-pearson}"; RANKMODE="${2:-weighted}"
NORMED=BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv
OUT=full_w1.0
DEATH_CC=$OUT/metric_x_death_cc_1.0_0.csv
CC_MATRIX="$OUT/full_cc_ase0_p=1.0_0.csv"
METRICS=/tmp/derive_excl_metrics.txt
L=/tmp
mkdir -p "$OUT"

if [ "$METHOD" = spearman ]; then
    # Tables S8 and S13 read the Spearman correlations from their own file
    echo "--- metric x death correlations (spearman) ---"
    cat "$NORMED" | python3 code/calc_metric_death_cc_v4.py --weight-col population_2019 \
        --weight-power 1.0 --min-ased-bl 0 --method spearman --rank-mode "$RANKMODE" \
        --lp-threshold -5.0 --output $OUT/metric_x_death_spearman_1.0_0.csv \
        > $L/derive_excl_s06_spearman.log 2>&1
    echo "derive_excl spearman done"
    exit 0
fi

echo "--- metric x death correlations ($METHOD) ---"
cat "$NORMED" | python3 code/calc_metric_death_cc_v4.py --weight-col population_2019 \
    --weight-power 1.0 --min-ased-bl 0 --method "$METHOD" --rank-mode "$RANKMODE" \
    --lp-threshold -5.0 --output "$DEATH_CC" > $L/derive_excl_s06_$METHOD.log 2>&1

echo "--- metric x metric correlation matrix ---"
cut -d',' -f1 "$DEATH_CC" > "$METRICS"
cat "$NORMED" | python3 code/09a_compute_cc_matrix.py --metrics-file "$METRICS" \
    --weight-col population_2019 --threshold 0 --power 1.0 --method "$METHOD" \
    --rank-mode "$RANKMODE" --output "$CC_MATRIX" > $L/derive_excl_s10_$METHOD.log 2>&1

echo "--- Ward clustering on the correlation matrix ---"
python3 code/ward_medoid_ccbs_v4.py --cc-matrix "$CC_MATRIX" --death-cc "$DEATH_CC" \
    --explain data/BEN_MERGED_MEASURES_explain_extended_2745.csv --ward-k-list 100 \
    --out-dir "$OUT/ward_xde_2745/" > $L/derive_excl_s11_$METHOD.log 2>&1

if [ "$METHOD" = pearson ]; then
    echo "--- alternative county weightings, Table S7 ---"
    mkdir -p excl/weights
    for p in 0.0 0.5 0.75; do
        cat "$NORMED" | python3 code/calc_metric_death_cc_v4.py --weight-col population_2019 \
            --weight-power $p --min-ased-bl 0 --method pearson --rank-mode weighted \
            --lp-threshold -5.0 --output excl/weights/metric_x_death_cc_${p}_0.csv \
            > $L/derive_excl_weight_$p.log 2>&1
    done
    cp -p "$DEATH_CC" excl/weights/metric_x_death_cc_1.0_0.csv
fi
echo "derive_excl $METHOD done (logs: $L/derive_excl_*.log)"
