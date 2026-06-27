#!/bin/sh
# Pipeline uses explicit check_file guards for critical steps rather than set -e
# (set -e has unreliable behaviour with pipes and subshells in sh)

# Use Homebrew Python (3.13+) explicitly. The system /usr/bin/python3 (3.9) on
# this Mac has a broken numpy install (x86_64 build on an arm64 host).
PATH=/opt/homebrew/bin:$PATH
export PATH
# ==========================================================================
# 0000_Run_USCounty-v10.1.sh
# Complete SCE US County pipeline v10.1
# SEM Ward100 clusters as primary organising unit
# XDE Ward100 clusters used only for CC heatmap + dendrogram figures
#
# SIGNIFICANCE RULE: |CC| magnitude bands (project default since 2026-05).
#   Significant = |CC| > 0.3 ; Very Significant = |CC| > 0.45.
#   The legacy LP/p-value rule is retired (dormant; reachable via --sig-mode lp /
#   --lp-stack / --lp-label). LP_ values are still computed and stored as data.
#   lp_threshold below now only affects the supplementary LP-sensitivity step.
#
# Usage:
#   sh code/0000_Run_USCounty-v10.1.sh 0.0 25.1 -13.0
#
# Arguments (all optional, defaults shown):
#   power        weight power for CC computation    (default: 0.0)
#   min_ased     min ased_bl county filter           (default: 25.1)
#   lp_threshold LP significance threshold           (default: -13.0)
#
# Files required in working directory:
#   data/raw/                              raw input data files
#   hub_members_extensive_intensive.csv
#   data/BEN_MERGED_MEASURES_explain_extended_2745.csv
#   sem_sc_assignments_manual.csv  (chmod -w protected)
#   sem_sc_names_manual.csv        (chmod -w protected)
#
# Set API key before running Step 02c (SEM labels):
#   export ANTHROPIC_API_KEY=<your-key>
# ==========================================================================

# Check that a critical file was produced; exit with message if not
check_file() {
    if [ ! -f "$1" ]; then
        echo "ERROR: expected output not found: $1" >&2
        echo "Check the log file for the failed step." >&2
        exit 1
    fi
}


power=${1:-0.0}
min_ased=${2:-25.1}
lp_thresh=${3:--13.0}
skip_labels=${4:-0}   # set to 1 to skip LLM label generation (Step 02c)
skip_assembly=${5:-0} # set to 1 to skip Steps 01+02 (assembly + normalisation)
skip_sem=${6:-0}      # set to 1 to skip Steps 03+04+05 (SEM clustering)
                      # e.g.: sh code/0000_Run_USCounty-v10.1.sh 0.0 25.1 -13.0 1 1 1

NEW=BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NEW.csv
NORMED=BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv
EXPLAIN=data/BEN_MERGED_MEASURES_explain_extended_2745.csv
CLASSIF=hub_members_extensive_intensive.csv
DEATH_CC=metric_x_death_cc_${power}_${min_ased}.csv
METRICS=metric_x_death_cc_${power}_${min_ased}.metrics
CC_MATRIX=full_cc_ase0_p=${power}_${min_ased}.csv
WARD_OUT=ward_xde_2745
SEM_OUT=ward_sem_2745
MASTER=master_sem_clusters_2745.xlsx
EXTRA=extra_tables_sem_2745.xlsx
FIG_OUT=figures_2745

echo "========================================================"
echo " SCE US County Pipeline v10.1  (SEM-primary)"
echo " power=${power}  min_ased=${min_ased}  lp_thresh=${lp_thresh}  skip_labels=${skip_labels}  skip_assembly=${skip_assembly}  skip_sem=${skip_sem}"
echo "========================================================"

# -----------------------------------------------------------------------
# PRE-FLIGHT: Check essential input files
# -----------------------------------------------------------------------
echo "Checking essential input files..."
preflight_ok=1

if [ -f "${EXPLAIN}" ]; then
    echo "  OK  ${EXPLAIN}"
else
    echo "  MISSING  ${EXPLAIN}"
    preflight_ok=0
fi

if [ -f "${CLASSIF}" ]; then
    echo "  OK  ${CLASSIF}"
else
    echo "  MISSING  ${CLASSIF}"
    preflight_ok=0
fi

if [ -f "sem_sc_assignments_manual.csv" ]; then
    echo "  OK  sem_sc_assignments_manual.csv"
else
    echo "  MISSING  sem_sc_assignments_manual.csv"
    preflight_ok=0
fi

if [ -f "sem_sc_names_manual.csv" ]; then
    echo "  OK  sem_sc_names_manual.csv"
else
    echo "  MISSING  sem_sc_names_manual.csv"
    preflight_ok=0
fi

if [ "${preflight_ok}" = "0" ]; then
    echo "ERROR: one or more essential files missing -- aborting." >&2
    exit 1
fi
echo ""

# -----------------------------------------------------------------------
# STEP 01: Assemble merged BEN file
# -----------------------------------------------------------------------
if [ "${skip_assembly}" = "1" ]; then
    echo "--- Skipping Steps 01+02 (assembly+normalisation) -- using existing ${NEW}, ${NORMED} ---"
else
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 01: Assemble merged BEN file ---"
python3 code/00_assemble_merged_BEN_file_v7.py > Step_01_00_assemble_merged_BEN_file_v7.log
check_file ${NEW}
head -1 ${NEW} | tr ',' '\n' | grep -v '^fips$' | grep -v '^$' > assembled_metrics.txt
echo "  Metric list: assembled_metrics.txt ($(wc -l < assembled_metrics.txt) metrics)"

# -----------------------------------------------------------------------
# STEP 02: Normalize extensive metrics
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 02: Normalize extensive metrics ---"
python3 code/normalize_extensive_metrics_v3.py --input ${NEW} --output ${NORMED} --classification ${CLASSIF} > Step_02_normalize_extensive_metrics_v3.log
check_file ${NORMED}

if [ "${skip_sem}" = "1" ]; then
    echo "--- Skipping Steps 02a+02b+02c (SEM clustering) -- using existing files ---"
else
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 03: SEM clustering (100 SEM clusters, explain-text only) ---"
mkdir -p ${SEM_OUT}
python3 code/semantic_cluster_metrics_v2.py --explain ${EXPLAIN} --metrics-list assembled_metrics.txt --output-dir ${SEM_OUT}/ --embeddings-cache embeddings_mpnet_2745.npy --model all-mpnet-base-v2 --umap-dims 0 --n-clusters 100 --silhouette-ks 40,60,80,100,120,150,200,280 > Step_03_semantic_cluster_metrics_v2.log
check_file ${SEM_OUT}/ward_sem_metrics.csv
check_file ${SEM_OUT}/Z_med_sem100.npy
echo "" >&2
echo "" >&2
echo "--- Step 04: Derive SEM super-clusters from SEM cluster explain texts ---"
python3 code/cluster_labels_to_superclusters.py --sem-clusters ${SEM_OUT}/ward_sem_metrics.csv --explain ${EXPLAIN} --n-super 11 --manual-assignments sem_sc_assignments_manual.csv --manual-names sem_sc_names_manual.csv --model all-mpnet-base-v2 --embeddings-cache ${WARD_OUT}/sem_sc_label_embeddings.npy --sem100-labels ${SEM_OUT}/sem100_labels.csv --out-dir ${WARD_OUT}/ > Step_04_cluster_labels_to_superclusters.log
check_file ${WARD_OUT}/sem_sc_assignments.csv
check_file ${WARD_OUT}/sem_sc_names.csv

date >&2
if [ "${skip_labels}" = "1" ]; then
    echo "--- Step 05: Skipping SEM cluster label generation (skip_labels=1) ---"
    if [ ! -f ${SEM_OUT}/sem100_labels.csv ]; then
        echo "WARNING: ${SEM_OUT}/sem100_labels.csv not found -- Step 02b may use unlabelled clusters"
    fi
else
    echo "--- Step 05: Generate SEM cluster labels via Claude API ---"
    python3 code/generate_cluster_labels.py --assignments ${SEM_OUT}/ward_sem_metrics.csv --reps-csv ${SEM_OUT}/ward_sem_summary.csv --extended-explain ${EXPLAIN} --out ${SEM_OUT}/sem100_labels.csv --tag sem --cluster-col cluster_id > Step_09_generate_sem_labels.log
    check_file ${SEM_OUT}/sem100_labels.csv
fi

# -----------------------------------------------------------------------
# STEP 10: Dendrogram + centroid heatmap (Fig 2)
# -----------------------------------------------------------------------
fi  # end skip_sem
fi  # end skip_assembly

# -----------------------------------------------------------------------
# STEP 03: Compute metric x death CC file
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 06: Compute metric x death CC ---"
cat ${NORMED} | python3 code/calc_metric_death_cc_v4.py --lp-threshold ${lp_thresh} --min-ased-bl ${min_ased} --weight-power ${power} --output ${DEATH_CC} > Step_10_calc_metric_death_cc_v4.log
check_file ${DEATH_CC}
cat ${DEATH_CC} | cut -d',' -f1 > ${METRICS}

date >&2
echo "" >&2
echo "" >&2
echo "--- Step 07: Compute best_cc per SEM cluster ---"
python3 code/compute_sem_best_cc.py --sem-metrics ${SEM_OUT}/ward_sem_metrics.csv --cc-file ${DEATH_CC} --reps ${SEM_OUT}/ward_sem_reps.csv > Step_07_sem_best_cc.log
check_file ${SEM_OUT}/ward_sem_reps.csv

# -----------------------------------------------------------------------
# STEP 04: CC histogram plots
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 08: Despair metrics ---"
python3 code/analyse_despair_metrics.py --death-cc ${DEATH_CC} --explain ${EXPLAIN} > Step_08_analyse_despair_metrics.log
echo "" >&2
echo "" >&2
echo "--- Step 09: CC histograms ---"
python3 code/plot_cc_histograms.py --lp-threshold ${lp_thresh} --input ${DEATH_CC} --output cc_histograms_${min_ased}.png > Step_09_plot_cc_histograms.log
python3 code/plot_cc_histograms.py --lp-threshold ${lp_thresh} --input ${DEATH_CC} --output cc_histograms_T_${min_ased}.png --transpose > Step_09_plot_cc_histograms_T.log

# -----------------------------------------------------------------------
# STEP 05: Compute full pairwise metric x metric CC matrix (slow)
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 10: Compute full CC matrix (slow) ---"
cat ${NORMED} | python3 code/09a_compute_cc_matrix.py --metrics-file ${METRICS} --weight-col population_2019 --threshold 0 --power ${power} --output ${CC_MATRIX} > Step_10_09a_compute_cc_matrix.log
check_file ${CC_MATRIX}

# -----------------------------------------------------------------------
# STEP 07: CC-based XDE clustering at k=100
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 11: XDE clustering (k=100) ---"
mkdir -p ${WARD_OUT}
python3 code/ward_medoid_ccbs_v4.py --cc-matrix ${CC_MATRIX} --death-cc ${DEATH_CC} --explain ${EXPLAIN} --ward-k-list 100 --out-dir ${WARD_OUT}/ > Step_11_ward_medoid_ccbs_v4.log
check_file ${WARD_OUT}/xde100_assignments.csv
check_file ${WARD_OUT}/Z_med_xde100.npy

# -----------------------------------------------------------------------
# STEP 09: Derive 12 super-clusters from label embeddings
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 12: XDE dendrogram and centroid heatmap ---"
python3 code/combine_dendrogram_heatmap_v2.py --labels ${SEM_OUT}/ward_sem_metrics.csv --sem-labels ${SEM_OUT}/sem100_labels.csv --z-med ${WARD_OUT}/Z_med_xde100.npy --medoid-list ${WARD_OUT}/medoid_list_xde100.json --reps-csv ${WARD_OUT}/xde100_reps.csv --cc-matrix ${CC_MATRIX} --extended-explain ${EXPLAIN} --death-cc ${DEATH_CC} --assignments ${WARD_OUT}/xde100_assignments.csv --sc-assignments ${WARD_OUT}/sem_sc_assignments.csv --centroid-heatmap --out ${WARD_OUT}/combined_xde_centroid.png > Step_12_combine_dendrogram_heatmap.log

# -----------------------------------------------------------------------
# STEP 11: Full CC heatmap (Fig S1)
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 13: Full CC heatmap ---"
python3 code/plot_full_heatmap.py --cc-matrix ${CC_MATRIX} --assignments ${WARD_OUT}/xde100_assignments.csv --z-med ${WARD_OUT}/Z_med_xde100.npy --medoid-list ${WARD_OUT}/medoid_list_xde100.json --reps-csv ${WARD_OUT}/xde100_reps.csv --labels-csv ${SEM_OUT}/ward_sem_metrics.csv --sem-labels ${SEM_OUT}/sem100_labels.csv --out ${WARD_OUT}/full_heatmap.png > Step_13_plot_full_heatmap.log

# -----------------------------------------------------------------------
# STEP 12: Build master Excel
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 14: Build master Excel ---"
if [ ! -f ${WARD_OUT}/sem_sc_names.csv ]; then
    echo "WARNING: sem_sc_names.csv missing -- re-running Step 01b"
    python3 code/cluster_labels_to_superclusters.py --sem-clusters ${SEM_OUT}/ward_sem_metrics.csv --explain ${EXPLAIN} --n-super 11 --manual-assignments sem_sc_assignments_manual.csv --manual-names sem_sc_names_manual.csv --model all-mpnet-base-v2 --embeddings-cache ${WARD_OUT}/sem_sc_label_embeddings.npy --sem100-labels ${SEM_OUT}/sem100_labels.csv --out-dir ${WARD_OUT}/ > Step_04_cluster_labels_to_superclusters_rerun.log
fi
python3 code/make_master_excel_v12.py --cc-file ${DEATH_CC} --sem-assignments ${SEM_OUT}/ward_sem_metrics.csv --sem-labels ${SEM_OUT}/sem100_labels.csv --sem-reps ${SEM_OUT}/ward_sem_reps.csv --sem-z-med ${SEM_OUT}/Z_med_sem100.npy --sem-medoid-list ${SEM_OUT}/medoid_list_sem100.json --sc-assignments ${WARD_OUT}/sem_sc_assignments.csv --extended-explain ${EXPLAIN} --ei-file ${CLASSIF} --sc-names-file ${WARD_OUT}/sem_sc_names.csv --output ${MASTER} > Step_14_make_master_excel_v12.log
check_file ${MASTER}

# -----------------------------------------------------------------------
# STEP 14b: Significance-colored SC label heatmap
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "--- Step 14b: Significance-colored heatmap ---"
python3 code/make_sig_heatmap.py \
    --sem-clusters ${SEM_OUT}/ward_sem_metrics.csv \
    --sc-assignments ${WARD_OUT}/sem_sc_assignments.csv \
    --sc-names ${WARD_OUT}/sem_sc_names.csv \
    --sem100-labels ${SEM_OUT}/sem100_labels.csv \
    --master-xlsx ${MASTER} \
    --embeddings-cache ${WARD_OUT}/sem_sc_label_embeddings.npy \
    --lp-thresh ${lp_thresh} \
    --out ${WARD_OUT}/sc_label_heatmap_sig.png > Step_14b_make_sig_heatmap.log
check_file ${WARD_OUT}/sc_label_heatmap_sig.png

# -----------------------------------------------------------------------
# STEP 13: Build extra tables
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 15: Build extra tables ---"
python3 code/make_extra_tables_v5.py --master-xlsx ${MASTER} --cc-file ${DEATH_CC} --output ${EXTRA} --z-med ${WARD_OUT}/Z_med_xde100.npy --medoid-list ${WARD_OUT}/medoid_list_xde100.json --reps ${WARD_OUT}/xde100_reps.csv --sem-sc ${WARD_OUT}/sem_sc_assignments.csv --sem-names ${WARD_OUT}/sem_sc_names.csv > Step_15_make_extra_tables.log
check_file ${EXTRA}
echo "" >&2
echo "" >&2
echo "--- Step 16: Best-LP per SEM cluster table ---"
python3 code/make_ward_best_lp_table.py --master-xlsx ${MASTER} --output sem_best_lp_2745.xlsx > Step_16_sem_best_lp.log

# -----------------------------------------------------------------------
# STEP 14: Build figures
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 18: Build figures ---"
mkdir -p ${FIG_OUT}
python3 code/make_figures.py --sc-names ${WARD_OUT}/sem_sc_names.csv --master-xlsx ${MASTER} --cc-file ${DEATH_CC} --out-dir ${FIG_OUT}/ > Step_18_make_figures.log

# -----------------------------------------------------------------------
# STEP 16: LP sensitivity analysis
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 19: LP sensitivity analysis ---"
mkdir -p lp_sensitivity_sweep
python3 code/lp_sensitivity_analysis.py --cc-file ${DEATH_CC} --master-xlsx ${MASTER} --sc-names ${WARD_OUT}/sem_sc_names.csv --out-dir lp_sensitivity_sweep/ --compare -11,-13,-15 > Step_19_lp_sensitivity_analysis.log

# -----------------------------------------------------------------------
# STEP 17: Validate final tables (runs last so figures + LP sweep exist)
# -----------------------------------------------------------------------
date >&2
echo "" >&2
echo "" >&2
echo "--- Step 17: Validate final tables ---"
python3 code/validate_tables.py --master ${MASTER} --extra ${EXTRA} --best-lp sem_best_lp_2745.xlsx --lp-sensitivity lp_sensitivity_sweep/lp_sensitivity_counts.xlsx --base-dir . --min-ased ${min_ased} --sig-min 1 --sig-max 3000 > Step_17_validate_tables.log


date >&2
echo "========================================================"
echo " Pipeline complete."
echo "   ${DEATH_CC}    metric x death CC/LP"
echo "   ${CC_MATRIX}   full metric CC matrix"
echo "   ${WARD_OUT}/   XDE clustering + SC assignments"
echo "   ${WARD_OUT}/sem_sc_coherence_report.txt  SC coherence report"
echo "   ${SEM_OUT}/    Semantic clustering"
echo "   ${MASTER}      master Excel (SEM-primary)"
echo "   ${EXTRA}       extra tables Excel"
echo "   sem_best_lp_2745.xlsx   best-LP metric per SEM cluster"
echo "   ${FIG_OUT}/    figures"
echo ""
N_PNG=$(find ${FIG_OUT} ${WARD_OUT} ${SEM_OUT} lp_sensitivity_sweep . -maxdepth 1 -name "*.png" 2>/dev/null | wc -l | tr -d " ")
N_XLSX=$(find . -maxdepth 2 -name "*.xlsx" -not -path "./.git/*" 2>/dev/null | wc -l | tr -d " ")
echo "   PNG files:  ${N_PNG}  (expected 29)"
echo "   XLSX files: ${N_XLSX}  (expected 5)"
echo "========================================================"
