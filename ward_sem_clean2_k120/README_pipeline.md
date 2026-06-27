# Standard pipeline — k120 clusters · w1.0 weighting · 2019 metrics

`../run_standard_k120_w1.0.sh` rebuilds the entire CC-dependent analysis layer for
the **standard conditions**:

- **metrics**: 2019 / standard release (the main `data/BEN_MERGED_…2745` set)
- **weighting**: w1.0 = population-weighted CC (`full_w1.0/metric_x_death_cc_1.0_0.csv`)
- **clusters**: k120 cleaned-name SEM clustering (this directory)

Run from anywhere:  `sh code/run_standard_k120_w1.0.sh`  (it cd's to the SANDBOX6 root).
Each step logs to `Step{A..K}_w1.0_*.log`; wrapper log `run_standard_k120_w1.0.log`.
**All figures are written to `figures_2745/`** (tables stay at root / in this dir).

## Curated (manual) vs computed (scripted)

**Curated artifacts — NOT re-derived from raw data** (reused by the pipeline):
| file | what | why manual |
|---|---|---|
| `ward_sem_metrics.csv` | the k120 cleaned-name SEM clustering (metric → semantic_cluster_id) | from `semantic_cluster_metrics_v2.py --clean-names --n-clusters 120`; the clustering itself is a one-time build |
| `sem100_labels.csv` (`label_proposed`) | the 120 cluster labels | hand-written from each cluster's full member set (the labeling API was billing-blocked) |
| `sc_label_embeddings.npy` | 120 cluster-label embeddings | from `cluster_labels_to_superclusters.py` (embeds the labels) |
| `Z_med_sem100.npy`, `medoid_list_sem100.json` | SEM medoid linkage + medoids | clustering output |
| 11 super-cluster **names** | in `code/define_superclusters_dendro.py` (`NAMES_K11`) | hand-authored to match the K=11 Ward cut |

**Computed by the pipeline** (everything else): best_cc, super-cluster *assignment*
(Ward dendrogram cut), master Excel, extra tables, best-LP, the metric rankings,
and all figures.

## Step order

| step | script | output |
|---|---|---|
| A | `compute_sem_best_cc.py` | `ward_sem_reps_w1.0.csv` |
| B | `define_superclusters_dendro.py` | `sem_sc_assignments.csv`, `sem_sc_names.csv` (Ward cut of the cluster-label cosine dendrogram, K=11, renumbered top→bottom) |
| C | `make_master_excel_v12.py` | `../master_sem_clusters_clean2_k120_w1.0.xlsx` |
| D | `make_extra_tables_v5.py` | `../extra_tables_clean2_k120_w1.0.xlsx` |
| E | `make_ward_best_lp_table.py` | `../sem_best_lp_clean2_k120_w1.0.xlsx` |
| F | `rank_metrics_by_cluster.py` | `top_metric_per_cluster_2020_2024_w1.0.tsv` (1/cluster, max\|CC\|), `top_metric_per_cluster.csv` (comma-separated copy of same), and `metrics_by_cluster_ordered_w1.0.tsv` (all, ranked within cluster) |
| G | `make_sig_heatmap.py --out-dendro` | `sc_label_heatmap_sig_w1.0.png` (dendrogram + 120×120 cosine, per-SC coloured branches, symlog axis, SC separators) + `sc_label_heatmap_flat_w1.0.png` |
| H | `plot_sem120_rep_heatmap.py` | `sem120_rep_heatmap_w1.0.png` (signed CC, ±0.5) and `sem120_rep_absCC_heatmap_w1.0_cap0.45.png` (\|CC\|, 0–0.45) |
| I | `plot_full_cc_ordered.py` | `full_cc_heatmap_ordered_w1.0.png` (signed, ±0.5) and `full_absCC_heatmap_ordered_w1.0_cap0.45.png` (\|CC\|, 0–0.45) |
| J | `combine_dendrogram_heatmap_v2.py`, `plot_full_heatmap.py` | `combined_xde_dendrogram_w1.0.png`, `full_heatmap_w1.0.png` (XDE/CC clustering views, annotated with SEM labels) |
| K | `make_figures.py` | `fig1..7` + `fig2b` + `Metric_Super-Cluster_Cluster.csv` (summary figures) |

(Steps G–K write into `figures_2745/`; A–F write tables.)

## Conventions
- **Representative of a cluster** = the member metric with the highest max\|CC\| over
  2020–2024 (NOT the medoid). This is `rank_in_cluster == 1` in the ordered TSV.
- **Within-cluster ordering** = by max\|CC\| descending.
- **Heatmap colour**: signed CC → diverging blue/white/red symmetric at 0, saturate ±0.5;
  \|CC\| → white→red, cap 0.45 (chosen from the pair-distribution: p90≈0.345, p95≈0.481).
- **Super-clusters** = Ward cut (K=11) of the cluster-label cosine dendrogram, contiguous
  in dendrogram order (so boundary lines are clean). Old label-embedding assignment backed
  up as `sem_sc_assignments.csv.bak_labelembed_*`.

## Scripts created this session (in `code/`)
`define_superclusters_dendro.py`, `rank_metrics_by_cluster.py`,
`plot_sem120_rep_heatmap.py`, `plot_full_cc_ordered.py`.
Also extended: `make_sig_heatmap.py` (Ward linkage, symlog, per-SC dendrogram colour,
SC separators, 120×120 title), `combine_dendrogram_heatmap_v2.py` (`--cc-threshold`),
`semantic_cluster_metrics_v2.py` (`--clean-names`), `generate_cluster_labels.py`
(use ALL members, not just medoid).

See `README_adoption.md` for the history of how this clustering was adopted.
