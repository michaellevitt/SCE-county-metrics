#!/bin/sh
# ============================================================================
# STANDARD analysis conditions:  2019 metrics | w1.0 weighting | k120 clusters
# ============================================================================
# Analysis-layer re-run: REUSES the pre-built k120 cleaned-name SEM clustering
# and its curated artifacts (NOT re-derived from raw -- see README_pipeline.md):
#     ward_sem_clean2_k120/ward_sem_metrics.csv     (cluster assignment)
#     ward_sem_clean2_k120/sem100_labels.csv        (120 hand-written labels)
#     ward_sem_clean2_k120/sc_label_embeddings.npy  (cluster-label embeddings)
#     ward_sem_clean2_k120/Z_med_sem100.npy, medoid_list_sem100.json
# Everything CC-dependent is (re)built on the population-weighted (w1.0) inputs.
# Tables get a _w1.0 suffix; ALL figures are written to figures_2745/.
#
# Run from anywhere:  sh code/run_standard_k120_w1.0.sh
# (the old complete from-raw pipeline is code/0000_Run_USCounty-v10.1.sh)
# ----------------------------------------------------------------------------
cd "$(dirname "$0")/.." || exit 1          # -> SANDBOX6 root (script lives in code/)
PATH=/opt/homebrew/bin:$PATH; export PATH
set -e

SEM=ward_sem_clean2_k120
FIG="${1:-figures_2745}"                          # all figures land here (override: arg 1 = output dir)
mkdir -p "$FIG"
W=full_w1.0/ward_xde_2745                         # w1.0 XDE clustering (for XDE figures)
DEATH_CC=full_w1.0/metric_x_death_cc_1.0_0.csv    # population-weighted metric x death CC
CC_MATRIX="full_w1.0/full_cc_ase0_p=1.0_0.csv"    # population-weighted metric x metric CC
EXPLAIN=data/BEN_MERGED_MEASURES_explain_extended_2745.csv
CLASSIF=hub_members_extensive_intensive.csv
MASTER=master_sem_clusters_clean2_k120_w1.0.xlsx
EXTRA=extra_tables_clean2_k120_w1.0.xlsx
ORDERED=$SEM/metrics_by_cluster_ordered_w1.0.tsv
TOP=$SEM/top_metric_per_cluster_2020_2024_w1.0.tsv
TOP_CSV=$SEM/top_metric_per_cluster.csv             # comma-separated copy (one row per cluster)

for f in "$SEM/ward_sem_metrics.csv" "$SEM/sem100_labels.csv" "$SEM/sc_label_embeddings.npy" \
         "$SEM/Z_med_sem100.npy" "$SEM/medoid_list_sem100.json" \
         "$DEATH_CC" "$CC_MATRIX" "$EXPLAIN" "$CLASSIF"; do
  [ -f "$f" ] || { echo "MISSING: $f" >&2; exit 1; }
done
mkdir -p "$FIG"
echo "=== STANDARD: 2019 metrics | w1.0 weighting | k120 clusters | figs -> $FIG/ ==="

echo "--- A. best_cc (w1.0) ---"
cp -p $SEM/ward_sem_reps.csv $SEM/ward_sem_reps_w1.0.csv
python3 code/compute_sem_best_cc.py --sem-metrics $SEM/ward_sem_metrics.csv \
    --cc-file $DEATH_CC --reps $SEM/ward_sem_reps_w1.0.csv > StepA_w1.0_bestcc.log 2>&1

echo "--- B. super-clusters = Ward dendrogram cut (K=11) ---"
python3 code/define_superclusters_dendro.py --sem-metrics $SEM/ward_sem_metrics.csv \
    --embeddings $SEM/sc_label_embeddings.npy --k 11 \
    --out-assign $SEM/sem_sc_assignments.csv --out-names $SEM/sem_sc_names.csv > StepB_w1.0_superclusters.log 2>&1

echo "--- C. master Excel (w1.0, new SCs) ---"
python3 code/make_master_excel_v12.py --cc-file $DEATH_CC \
    --sem-assignments $SEM/ward_sem_metrics.csv --sem-labels $SEM/sem100_labels.csv \
    --sem-reps $SEM/ward_sem_reps_w1.0.csv --extended-explain $EXPLAIN \
    --sem-z-med $SEM/Z_med_sem100.npy --sem-medoid-list $SEM/medoid_list_sem100.json \
    --ei-file $CLASSIF --sc-names-file $SEM/sem_sc_names.csv \
    --sc-assignments $SEM/sem_sc_assignments.csv --output $MASTER > StepC_w1.0_master.log 2>&1

echo "--- D. extra tables (w1.0) ---"
python3 code/make_extra_tables_v5.py --master-xlsx $MASTER --cc-file $DEATH_CC \
    --output $EXTRA > StepD_w1.0_extra.log 2>&1

echo "--- E. best-LP table (w1.0) ---"
python3 code/make_ward_best_lp_table.py --master-xlsx $MASTER \
    --output sem_best_lp_clean2_k120_w1.0.xlsx > StepE_w1.0_bestlp.log 2>&1

echo "--- F. metric lists: within-cluster max|CC| ranking + per-cluster top metric ---"
python3 code/rank_metrics_by_cluster.py --sem-metrics $SEM/ward_sem_metrics.csv \
    --death-cc $DEATH_CC --sem100-labels $SEM/sem100_labels.csv \
    --sc-assignments $SEM/sem_sc_assignments.csv --years 2020-2024 \
    --out-ordered $ORDERED --out-top $TOP --out-top-csv $TOP_CSV > StepF_w1.0_rank.log 2>&1

echo "--- G. cluster-label cosine + dendrogram (the 120x120 'beautiful' figure) ---"
python3 code/make_sig_heatmap.py --sem-clusters $SEM/ward_sem_metrics.csv \
    --sc-assignments $SEM/sem_sc_assignments.csv --sc-names $SEM/sem_sc_names.csv \
    --sem100-labels $SEM/sem100_labels.csv --master-xlsx $MASTER \
    --embeddings-cache $SEM/sc_label_embeddings.npy --min-sig-metrics 3 --min-sig-years 2 \
    --out $FIG/sc_label_heatmap_flat_w1.0.png \
    --out-dendro $FIG/sc_label_heatmap_sig_w1.0.png > StepG_w1.0_sigheat.log 2>&1

echo "--- H. 120x120 representative heatmaps (signed CC, and |CC| at cap 0.45) ---"
python3 code/plot_sem120_rep_heatmap.py --top $TOP --metric cc \
    --cc-matrix "$CC_MATRIX" --cc-threshold 0.5 \
    --out $FIG/sem120_rep_heatmap_w1.0.png > StepH1_w1.0_rep_signed.log 2>&1
python3 code/plot_sem120_rep_heatmap.py --top $TOP --metric cc --abs --cc-threshold 0.45 \
    --cc-matrix "$CC_MATRIX" \
    --out $FIG/sem120_rep_absCC_heatmap_w1.0_cap0.45.png > StepH2_w1.0_rep_abs045.log 2>&1

echo "--- I. complete metric x metric heatmaps (signed, and |CC| at cap 0.45) ---"
python3 code/plot_full_cc_ordered.py --order $ORDERED --cc-matrix "$CC_MATRIX" \
    --cc-threshold 0.5 --out $FIG/full_cc_heatmap_ordered_w1.0.png > StepI1_w1.0_full_signed.log 2>&1
python3 code/plot_full_cc_ordered.py --order $ORDERED --cc-matrix "$CC_MATRIX" \
    --cc-threshold 0.45 --abs \
    --out $FIG/full_absCC_heatmap_ordered_w1.0_cap0.45.png > StepI2_w1.0_full_abs045.log 2>&1

echo "--- J. (XDE clustering) dendrogram + centroid heatmap, and full heatmap ---"
python3 code/combine_dendrogram_heatmap_v2.py --labels $SEM/ward_sem_metrics.csv \
    --sem-labels $SEM/sem100_labels.csv --z-med $W/Z_med_xde100.npy \
    --medoid-list $W/medoid_list_xde100.json --reps-csv $W/xde100_reps.csv \
    --cc-matrix "$CC_MATRIX" --extended-explain $EXPLAIN --death-cc $DEATH_CC \
    --assignments $W/xde100_assignments.csv --nsuper 11 --centroid-heatmap \
    --out $FIG/combined_xde_dendrogram_w1.0.png > StepJ1_w1.0_xde_combine.log 2>&1
python3 code/plot_full_heatmap.py --cc-matrix "$CC_MATRIX" \
    --assignments $W/xde100_assignments.csv --z-med $W/Z_med_xde100.npy \
    --medoid-list $W/medoid_list_xde100.json --reps-csv $W/xde100_reps.csv \
    --labels-csv $SEM/ward_sem_metrics.csv --sem-labels $SEM/sem100_labels.csv \
    --nsuper 11 --out $FIG/full_heatmap_w1.0.png > StepJ2_w1.0_xde_full.log 2>&1

echo "--- K. summary figures fig1-7 (+ Metric_Super-Cluster_Cluster.csv) ---"
python3 code/make_figures.py --sc-names $SEM/sem_sc_names.csv --master-xlsx $MASTER \
    --cc-file $DEATH_CC --sig-mode cc --cc-sig 0.3 --out-dir $FIG/ > StepK_w1.0_make_figures.log 2>&1

echo "--- L. consolidated paper-tables workbook (Index + essential tabs, |CC| bands) ---"
python3 code/make_consolidated_tables.py --master $MASTER --extra $EXTRA \
    --best sem_best_lp_clean2_k120_w1.0.xlsx \
    --output SCE_paper_tables_consolidated_clean2_k120_w1.0.xlsx > StepL_w1.0_consolidated.log 2>&1

echo "=== DONE."
echo "  tables : $MASTER, $EXTRA, sem_best_lp_clean2_k120_w1.0.xlsx, $TOP, $ORDERED,"
echo "           SCE_paper_tables_consolidated_clean2_k120_w1.0.xlsx"
echo "  figures (all in $FIG/): fig1..7 + Metric_Super-Cluster_Cluster.csv,"
echo "           sc_label_heatmap_sig_w1.0.png, sem120_rep_heatmap_w1.0.png,"
echo "           sem120_rep_absCC_heatmap_w1.0_cap0.45.png, full_cc_heatmap_ordered_w1.0.png,"
echo "           full_absCC_heatmap_ordered_w1.0_cap0.45.png, combined_xde_dendrogram_w1.0.png,"
echo "           full_heatmap_w1.0.png ==="
