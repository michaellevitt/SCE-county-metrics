#!/bin/sh
# ============================================================================
# build_minimal_repo.sh  --  reduce For_Git_Repo to the MINIMAL file set that
# can run BOTH pipelines afresh:
#   (1) code/0000_Run_USCounty-v10.1.sh   -- full from-raw pipeline
#   (2) code/run_standard_k120_w1.0.sh    -- analysis re-run (reuses curated
#                                            clustering: ward_sem_clean2_k120/
#                                            + full_w1.0/)
#
# It (a) copies the curated clustering artifacts in from the parent SANDBOX6,
# then (b) prunes everything not on the dependency-traced keep-list.
#
# Safe to re-run.  The parent dir (one level up) keeps a full copy of every
# original file, so any prune here is recoverable.
#
# Usage:  sh build_minimal_repo.sh            # do it
#         sh build_minimal_repo.sh --dry-run  # list what WOULD be removed
# ============================================================================
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PARENT=$(cd "$HERE/.." && pwd)
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
say(){ echo "$@"; }
rm_(){ if [ "$DRY" = "1" ]; then echo "  would rm  $1"; else rm -rf -- "$1"; fi; }

cd "$HERE" || exit 1
say "=== repo: $HERE"
say "=== parent (backup source): $PARENT"

# ---------------------------------------------------------------------------
# 1. COPY IN curated clustering artifacts needed by run_standard_k120_w1.0.sh
# ---------------------------------------------------------------------------
say "--- 1. copy curated inputs from parent ---"
mkdir -p ward_sem_clean2_k120 full_w1.0/ward_xde_2745
for f in ward_sem_metrics.csv sem100_labels.csv sc_label_embeddings.npy \
         Z_med_sem100.npy medoid_list_sem100.json ward_sem_reps.csv \
         README_pipeline.md; do
  [ -f "ward_sem_clean2_k120/$f" ] || cp -p "$PARENT/ward_sem_clean2_k120/$f" ward_sem_clean2_k120/ 2>/dev/null \
     && say "  ward_sem_clean2_k120/$f"
done
for f in "metric_x_death_cc_1.0_0.csv" "full_cc_ase0_p=1.0_0.csv"; do
  [ -f "full_w1.0/$f" ] || cp -p "$PARENT/full_w1.0/$f" full_w1.0/ 2>/dev/null \
     && say "  full_w1.0/$f"
done
for f in Z_med_xde100.npy medoid_list_xde100.json xde100_reps.csv xde100_assignments.csv; do
  [ -f "full_w1.0/ward_xde_2745/$f" ] || cp -p "$PARENT/full_w1.0/ward_xde_2745/$f" full_w1.0/ward_xde_2745/ 2>/dev/null \
     && say "  full_w1.0/ward_xde_2745/$f"
done

# ---------------------------------------------------------------------------
# 2. PRUNE code/  -- keep only the 28 scripts used by the two pipelines
# ---------------------------------------------------------------------------
say "--- 2. prune code/ ---"
KEEP_CODE="run_all.sh clean_all.sh run_standard_k120_w1.0.sh 0000_Run_USCounty-v10.1.sh derive_w1.0_cc.sh _workbook_style.py \
00_assemble_merged_BEN_file_v7.py normalize_extensive_metrics_v3.py \
semantic_cluster_metrics_v2.py cluster_labels_to_superclusters.py \
generate_cluster_labels.py calc_metric_death_cc_v4.py compute_sem_best_cc.py \
analyse_despair_metrics.py plot_cc_histograms.py 09a_compute_cc_matrix.py \
ward_medoid_ccbs_v4.py combine_dendrogram_heatmap_v2.py plot_full_heatmap.py \
make_master_excel_v12.py make_sig_heatmap.py make_extra_tables_v5.py \
make_ward_best_lp_table.py make_figures.py lp_sensitivity_analysis.py \
validate_tables.py define_superclusters_dendro.py rank_metrics_by_cluster.py \
plot_sem120_rep_heatmap.py plot_full_cc_ordered.py make_consolidated_tables.py"
for p in code/* code/.DS_Store; do
  [ -e "$p" ] || continue
  b=$(basename "$p"); keep=0
  for k in $KEEP_CODE; do [ "$b" = "$k" ] && keep=1 && break; done
  [ "$keep" = "1" ] || rm_ "$p"
done

# ---------------------------------------------------------------------------
# 3. PRUNE data/  -- keep raw assembly inputs + the 2745 explain file
# ---------------------------------------------------------------------------
say "--- 3. prune data/ ---"
rm_ "data/AHRF 2023-2024 CSV"
rm_ "data/AHRF 2023-2024 User Tech"
rm_ "data/BEN_MERGED_MEASURES_explain_extended_2769.csv"
rm_ "data/BEN_MERGED_MEASURES_explain_extended_2745.csv.dup" 2>/dev/null
rm_ "data/Clean_AHRF_2019-2020_Technical_Doc_W2-Table_1_Abbrev.csv"
rm_ "data/Clean_AHRF_2019-2020_Technical_Doc_W2-Table_1_Fields.csv"
rm_ "data/.DS_Store"
rm_ "data/raw/county=result-causes-f1-4,12.csv"
# census_pop: keep ONLY the two files the own-year normalize step needs
KEEP_POP="county_pop_by_year_2000_2024.csv metric_year_map.csv"
for p in data/raw/census_pop/*; do
  [ -e "$p" ] || continue; b=$(basename "$p"); keep=0
  for k in $KEEP_POP; do [ "$b" = "$k" ] && keep=1 && break; done
  [ "$keep" = "1" ] || rm_ "$p"
done

# ---------------------------------------------------------------------------
# 4. PRUNE repo root  -- whitelist; remove everything else at depth 1
# ---------------------------------------------------------------------------
say "--- 4. prune root ---"
KEEP_ROOT="code data ward_sem_clean2_k120 full_w1.0 \
hub_members_extensive_intensive.csv sem_sc_assignments_manual.csv \
sem_sc_names_manual.csv embeddings_mpnet_2745.npy \
.gitignore .gitattributes README.md requirements.txt build_minimal_repo.sh \
.git . .."
for p in * .[!.]*; do
  [ -e "$p" ] || continue
  keep=0
  for k in $KEEP_ROOT; do [ "$p" = "$k" ] && keep=1 && break; done
  [ "$keep" = "1" ] || rm_ "$p"
done

# ---------------------------------------------------------------------------
# 5. PRUNE curated input dirs back to input-only (drop run_standard outputs
#    that land inside them: ward_sem_reps_w1.0.csv, sem_sc_*.csv, *_w1.0.tsv,
#    top_metric_per_cluster*, etc.)
# ---------------------------------------------------------------------------
say "--- 5. prune curated dirs to inputs only ---"
KEEP_SEM="ward_sem_metrics.csv sem100_labels.csv sc_label_embeddings.npy \
Z_med_sem100.npy medoid_list_sem100.json ward_sem_reps.csv README_pipeline.md"
for p in ward_sem_clean2_k120/*; do
  [ -e "$p" ] || continue; b=$(basename "$p"); keep=0
  for k in $KEEP_SEM; do [ "$b" = "$k" ] && keep=1 && break; done
  [ "$keep" = "1" ] || rm_ "$p"
done
KEEP_W="metric_x_death_cc_1.0_0.csv full_cc_ase0_p=1.0_0.csv ward_xde_2745"
for p in full_w1.0/*; do
  [ -e "$p" ] || continue; b=$(basename "$p"); keep=0
  for k in $KEEP_W; do [ "$b" = "$k" ] && keep=1 && break; done
  [ "$keep" = "1" ] || rm_ "$p"
done
KEEP_XDE="Z_med_xde100.npy medoid_list_xde100.json xde100_reps.csv xde100_assignments.csv"
for p in full_w1.0/ward_xde_2745/*; do
  [ -e "$p" ] || continue; b=$(basename "$p"); keep=0
  for k in $KEEP_XDE; do [ "$b" = "$k" ] && keep=1 && break; done
  [ "$keep" = "1" ] || rm_ "$p"
done

say "=== done.  size now: $(du -sh "$HERE" 2>/dev/null | cut -f1)"
