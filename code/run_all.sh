#!/bin/sh
# ============================================================================
# run_all.sh  --  regenerate the full w1.0 analysis from raw data, one command.
#
# Chains the two stages:
#   STAGE 1  code/derive_w1.0_cc.sh         data/raw/ -> full_w1.0/
#            (assemble -> own-year normalize -> death-CC -> CC matrix -> XDE clustering)
#   STAGE 2  code/run_standard_k120_w1.0.sh full_w1.0/ + ward_sem_clean2_k120/
#            -> all tables (*.xlsx) and all figures (figures_2745/)
#
# REGENERATED from raw:
#   full_w1.0/metric_x_death_cc_1.0_0.csv, full_w1.0/full_cc_ase0_p=1.0_0.csv,
#   full_w1.0/ward_xde_2745/*, master_/extra_/sem_best_lp_/consolidated *.xlsx,
#   and every figure in figures_2745/.
#
# NOT regenerated -- shipped CURATED input, by design:
#   ward_sem_clean2_k120/  (the 120-cluster semantic clustering). Its labels
#   (sem100_labels.csv) are hand-written and the super-cluster curation
#   (sem_sc_*_manual.csv) is manual, so it is a fixed input, not an output.
#
# Requires a Python 3.11+ with the from-raw deps (see requirements.txt) and,
# for STAGE 1, the census-population files in data/raw/census_pop/.
#
# Run from the repo root:  sh code/run_all.sh
# ============================================================================
set -e
cd "$(dirname "$0")/.." || exit 1

echo "############################################################"
echo "# STAGE 1/2  --  derive CC inputs + XDE clustering from raw"
echo "############################################################"
sh code/derive_w1.0_cc.sh

echo "############################################################"
echo "# STAGE 2/2  --  build all tables and figures"
echo "############################################################"
sh code/run_standard_k120_w1.0.sh

echo "############################################################"
echo "# ALL DONE."
echo "#   full_w1.0/      regenerated CC files + XDE clustering"
echo "#   *.xlsx          master / extra / best-LP / consolidated tables"
echo "#   figures_2745/   all figures"
echo "#   (ward_sem_clean2_k120/ is a curated input, not regenerated)"
echo "############################################################"
