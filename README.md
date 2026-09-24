# SCE — Semantic-Cluster Excess-death analysis of US-county measures

Code and data to reproduce the analysis in the SCE county-metrics manuscript
(Levitt, Ioannidis et al.).

Starting from ~2,745 county-level predictor variables (largely from the Area
Health Resources File) and county COVID-era excess-death measures, the pipeline:

1. computes population-weighted correlation coefficients (CC) of every predictor
   against the excess-death measures, and the full predictor×predictor CC matrix;
2. organizes the predictors into **120 semantic clusters** and **11
   super-clusters**;
3. produces the manuscript's tables and figures.

---

## 1. Setup (one time)

> **Fresh machine? Check prerequisites first.** This block assumes **Git LFS**
> and **Python 3.11+** are already on your PATH. If `git lfs install` fails with
> `git: 'lfs' is not a git command`, if your `python3` is older than 3.11, or if
> you can't use Homebrew / `sudo`, do the
> [Troubleshooting: no-admin setup](#troubleshooting-no-admin-setup-no-homebrew--no-sudo)
> steps **before** running this block, then return here.

```sh
# clone WITH Git LFS — large derived files are stored in LFS (see §7).
# Needs the git-lfs binary; if this errors "'lfs' is not a git command",
# install it first — see Troubleshooting below (no Homebrew/sudo required).
git lfs install
git clone <repo-url>
cd <repo>

# isolated Python environment
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

**Python 3.11+ is required** (tested on 3.13). On macOS do **not** use the system
`/usr/bin/python3` (3.9) — it ships a broken numpy. The run scripts prepend
`/opt/homebrew/bin` to `PATH`; if your Python is elsewhere, edit that line at the
top of each script or just run inside the venv above.

`requirements.txt` splits the dependencies: the **core** stack (numpy, pandas,
scipy, scikit-learn, matplotlib, openpyxl, requests) is enough for everything
except the from-raw semantic clustering, which additionally needs
`sentence-transformers`, `torch`, and `umap-learn`.

### Troubleshooting: no-admin setup (no Homebrew / no sudo)

The setup above assumes you already have **Git LFS** and a **Python 3.11+** on
your PATH. If your machine lacks Git LFS, has only an older system Python (e.g.
macOS `/usr/bin/python3` = 3.9), or has a conflicting Anaconda/conda install
ahead of the system tools, the steps below install everything **locally** under
`~/.local/bin` — no Homebrew, no `sudo`, no Xcode-license prompt. They were
verified on a fresh macOS reproduction (2026-07-02).

> **Tip:** if a `curl`-based step misbehaves, a stray Anaconda `curl` may be
> shadowing the system one. Use `/usr/bin/curl` explicitly (as below).

**1. Git LFS, locally** — run *before* `git clone`:

```sh
mkdir -p "$HOME/.local/bin"
GIT_LFS_TMP=$(mktemp -d)
GIT_LFS_VERSION=$(/usr/bin/curl -fsSIL -o /dev/null -w '%{url_effective}' https://github.com/git-lfs/git-lfs/releases/latest | sed 's#.*/tag/v##')
case "$(uname -m)" in
  x86_64) GIT_LFS_ARCH=amd64 ;;
  arm64)  GIT_LFS_ARCH=arm64 ;;
  *) echo "Unsupported arch: $(uname -m)"; exit 1 ;;
esac
/usr/bin/curl -fL "https://github.com/git-lfs/git-lfs/releases/download/v${GIT_LFS_VERSION}/git-lfs-darwin-${GIT_LFS_ARCH}-v${GIT_LFS_VERSION}.tar.gz" -o "$GIT_LFS_TMP/git-lfs.tar.gz"
tar -xzf "$GIT_LFS_TMP/git-lfs.tar.gz" -C "$GIT_LFS_TMP" --strip-components=1
cp "$GIT_LFS_TMP/git-lfs" "$HOME/.local/bin/"
export PATH="$HOME/.local/bin:$PATH"
git lfs install
```

**2. Python 3.11 via `uv`, locally** — if your `python3` is older than 3.11:

```sh
mkdir -p "$HOME/.local/bin"
UV_TMP=$(mktemp -d)
UV_VERSION=$(/usr/bin/curl -fsSIL -o /dev/null -w '%{url_effective}' https://github.com/astral-sh/uv/releases/latest | sed 's#.*/tag/##')
case "$(uname -m)" in
  arm64)  UV_TARGET=aarch64-apple-darwin ;;
  x86_64) UV_TARGET=x86_64-apple-darwin ;;
  *) echo "Unsupported arch: $(uname -m)"; exit 1 ;;
esac
/usr/bin/curl -fL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_TARGET}.tar.gz" -o "$UV_TMP/uv.tar.gz"
tar -xzf "$UV_TMP/uv.tar.gz" -C "$UV_TMP" --strip-components=1
cp "$UV_TMP/uv" "$HOME/.local/bin/"
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.11
uv venv --python 3.11 .venv
. .venv/bin/activate
```

**3. Seed `pip` inside the `uv` venv** — a `uv`-created venv ships without `pip`,
so a bare `pip` can fall through to a broken global install. Seed it first, then
install:

```sh
python -m ensurepip --upgrade
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

(If you used the plain `python3 -m venv` from the standard setup instead, `pip`
is already present and `pip install -r requirements.txt` works directly.)

After these, continue with `sh code/run_standard_k120_w1.0.sh` as normal.

---

## 2. Running

All scripts are run from the repo root, e.g. `sh code/run_all.sh`.

| Command | What it does | Time |
|---|---|---|
| `sh code/run_all.sh` | **Regenerate everything.** Rebuilds the `full_w1.0/` CC files + XDE clustering from `data/raw/`, then builds every table and figure. | ~2.5 min |
| `sh code/run_standard_k120_w1.0.sh` | Build all tables + figures from the **pre-built** curated inputs (no raw recompute). | ~1 min |
| `sh code/derive_w1.0_cc.sh` | Rebuild only the `full_w1.0/` CC files + XDE clustering from raw. | ~1.5 min |
| `sh code/clean_all.sh` | Delete everything the runs generate, restoring the committed tree. Add `--dry-run` to preview. | instant |
| `sh code/0000_Run_USCounty-v10.1.sh 0.0 25.1 -13.0` | Original full from-raw pipeline (also re-derives the SEM clustering). Needs the clustering deps and `ANTHROPIC_API_KEY` (for the LLM cluster-label step). | slow |

**Sensitivity analyses (paper §"Sensitivity analysis on the correlation method" / Table S8; Figures S4–S6):**

| Command | What it does | Time |
|---|---|---|
| `sh code/run_spearman.sh` | **Spearman sensitivity.** Regenerates the CC files under population-weighted **Spearman** (weighted-ECDF ranks), builds `*_spearman` tables + `figures_2745_spearman/`, then restores the Pearson primary. Needs AHRF (from-raw). | ~2.5 min |
| `python3 code/make_spearman_comparison.py` | Build **Table S8** + `SCE_Pearson_vs_Spearman_supplement.xlsx` from the Pearson and Spearman death-CC files (run `run_all.sh` then `run_spearman.sh` first). | instant |
| `python3 code/vintage_cc_continuous.py` | **Cross-vintage figure (Figure S6)** + stats: per-variable signed CC, 2019 vs ≤2015 and 2019 vs 2023–2024 (own-year normalized). Writes to `Supplementary_Tables_Figures/`. | instant |

The correlation method is also exposed directly: `calc_metric_death_cc_v4.py` and
`09a_compute_cc_matrix.py` take `--method {pearson,spearman}` (default `pearson`)
and `--rank-mode {weighted,plain}`; `derive_w1.0_cc.sh spearman weighted` uses them.
Pearson remains the primary analysis; the committed `full_w1.0/` inputs are Pearson.

**Typical use:** `sh code/run_standard_k120_w1.0.sh` to build all tables and
figures from the included derived data, then `sh code/clean_all.sh` to reset.

> **Note:** `run_standard_k120_w1.0.sh` works out of the box. The from-raw paths
> (`run_all.sh`, `derive_w1.0_cc.sh`, `0000_…`) additionally require the AHRF
> source file, which is **not** included — see **§"AHRF data (not included)"**.

`run_all.sh` is just `derive_w1.0_cc.sh` (stage 1) followed by
`run_standard_k120_w1.0.sh` (stage 2); run either alone if you only need that
half.

**Manuscript & supplementary tables.** Two further scripts build the paper
artifacts from the analysis outputs:

| Command | What it does |
|---|---|
| `python3 code/regen_supp_tsv_s7top6_s8.py` | Regenerates the two CC-dependent supplementary tables — `Table_S4_top6_metrics_per_supercluster.tsv` and `Table_S5_age_band_divergence.tsv` — into `Supplementary_Tables_Figures/`. Reads `full_w1.0/metric_x_death_cc_1.0_0.csv`, `ward_sem_clean2_k120/ward_sem_metrics.csv`, and the pipeline-generated `ward_sem_clean2_k120/top_metric_per_cluster_2020_2024_w1.0.tsv` (so run `run_standard_k120_w1.0.sh` first). |
| `node code/build_paper_docx.js` | Renders the full manuscript to `DRAFT_PAPER_SCE_county_metrics.docx`. Needs Node.js + the `docx` package (`npm i docx`). It reads `full_w1.0/metric_x_death_cc_1.0_0.csv`, the four `Table_S3…S6` supplementary TSVs, and the manuscript figures; the static supplementary inputs (`Table_S3_supercluster_cluster_names.tsv`, `Table_S4A_collapsed_variants.tsv`, `Table_S6_vintage_composition.tsv`, `Fig_S1.png`, and the histogram PNGs) are not regenerated by this repo, so a full docx build needs those supplied. |

The seven machine-readable supplementary files are named to match their rendered
table numbers: `Top_metric_per_cluster_2020_2024_w1.0.tsv`,
`Table_S3_supercluster_cluster_names.tsv`,
`Table_S4_top6_metrics_per_supercluster.tsv`,
`Table_S4A_collapsed_variants.tsv`, `Table_S5_age_band_divergence.tsv`,
`Table_S6_vintage_composition.tsv`, and `Excluded_columns_417.tsv`.

---

## 3. Referee-revision analyses

Added for the peer review of the manuscript. Each script is self-contained, is run
from the repo root, and writes its own output directory. All of them read the
committed `full_w1.0/metric_x_death_cc_1.0_0.csv` and
`ward_sem_clean2_k120/ward_sem_metrics.csv`; the ones marked "needs AHRF" also read
`data/raw/AHRF2020.fips.csv` or the merged matrix built from it, which is not
included (see §"AHRF data (not included)").

| Command | What it answers | Output |
|---|---|---|
| `python3 code/permutation_null_v2.py --n-perm 10000 --seed 20260918 --strata 20` | Multiple comparisons. Permutes county labels of the whole five-year outcome block and reruns the screen. 472 observed against a null mean of 2.4, p = 0.0001; family-wise 5% critical value \|CC\| = 0.408. | `permutation_null/` + Figure S7 |
| `python3 code/suppression_analysis_v1.py` | CDC WONDER small-count suppression: how much is withheld, how it is recovered, and a sensitivity analysis. Needs AHRF. | `suppression/` |
| `python3 code/weighted_spearman_v1.py` | Population-weighted Spearman coefficients as weighted empirical-distribution ranks followed by a weighted Pearson. | Table S13 inputs |
| `python3 code/revision_analyses_v1.py` | Super-cluster by data-year crosstab, the 2020-vintage sensitivity, and the cluster span of the 472 variables. Needs AHRF. | `revision_analyses/` |
| `python3 code/silhouette_curve_v1.py` | Silhouette against k from 2 to 1000. It rises monotonically and so cannot select k, which is why the paper no longer cites it as justification. | `revision_analyses/` + Figure S8 |
| `python3 code/imputation_sensitivity_v1.py` | The two data-handling choices: the counties with a zero baseline, and the column-mean fill of missing predictor cells. The decisive scenario leaves every filled-in cell missing, with a 90% population-coverage rule: 535 variables above 0.30 rather than 472, because a filled-in count divided by the 85 residents of Kalawao County, Hawaii had been suppressing 92 variables. Needs AHRF. | `imputation_sensitivity/` + Table S16 |
| `python3 code/geography_and_map_v1.py` | Where the advantaged and disadvantaged counties are: an advantage index built from the 77 strongest variables, population-weighted quintiles, Census region and division, and county maps. Needs AHRF. | `geography/` + Figure S9 |

The county boundaries for the maps are `data/raw/geojson-counties-fips.json`, the
public county file keyed on 5-digit FIPS. The maps are drawn with `matplotlib`
alone, in an Albers equal-area projection, so no geospatial packages are needed.

`geography/county_advantage_index.csv`, the per-county table, is **not** committed
because its columns are derived from AHRF at full county resolution; the script
writes it locally. The aggregate tables are committed.

**Manuscript figures at printed size.** Figures 1 and 2 were originally drawn about
28 and 22 inches wide and then placed at 6.4 inches, which shrank every label by a
factor of four. Both scripts now take `--page-layout`, which draws the figure at the
width it is printed at, so a point size in the script is a point size on the page.
The flag defaults off, so the originally submitted figures remain reproducible.

```sh
python3 code/make_sig_heatmap.py --sem-clusters ward_sem_clean2_k120/ward_sem_metrics.csv \
    --sc-assignments ward_sem_clean2_k120/sem_sc_assignments.csv \
    --sc-names ward_sem_clean2_k120/sem_sc_names.csv \
    --sem100-labels ward_sem_clean2_k120/sem100_labels.csv \
    --master-xlsx master_sem_clusters_clean2_k120_w1.0.xlsx \
    --embeddings-cache ward_sem_clean2_k120/sc_label_embeddings.npy \
    --min-sig-metrics 3 --min-sig-years 2 --page-layout \
    --out /tmp/discard_flat.png --out-dendro figures_revision/fig1_page_layout.png

python3 code/plot_cc_histograms.py \
    --input full_w1.0/metric_x_death_cc_1.0_0_analysis2745.csv \
    --output figures_revision/fig2_page_layout.png \
    --transpose --cc-bands --cc-strong 0.45 --page-layout
```

Figure 1 cannot carry its 120 cluster labels at journal width, since 120 labels over
3.8 inches of axis leaves 2.3 points of pitch each. The page-layout version labels
the 11 super-clusters and the caption directs the reader to Table S3, which lists
all 120 cluster names.

`full_w1.0/metric_x_death_cc_1.0_0_analysis2745.csv` is the correlation file
restricted to the 2,745-variable analysis set. Figure 2 uses it so that its panel
counts match the Results; the wider `metric_x_death_cc_1.0_0.csv` holds 30 further
rows, Census 2020 urban and rural variables, which are computed but carry no
reported result. After a from-raw run it is rebuilt with:

```sh
python3 -c "import pandas as pd; \
m=set(pd.read_csv('ward_sem_clean2_k120/ward_sem_metrics.csv')['metric']); \
d=pd.read_csv('full_w1.0/metric_x_death_cc_1.0_0.csv'); \
d[d.metric.isin(m)].to_csv('full_w1.0/metric_x_death_cc_1.0_0_analysis2745.csv', index=False)"
```

**County exclusions (revision of 24 September 2026).** The revised analysis omits
two groups of counties, leaving 2,770 counties that hold 98.5% of the population:

1. every county with fewer than 10 deaths in any age group used (all ages, under 65,
   65 and over) in any year from 2017 to 2024, 361 counties holding 0.38% of the
   population, among them the two with no baseline deaths (Kalawao, Hawaii and
   Loving, Texas);
2. the eight Connecticut counties, whose population estimates follow the new planning
   regions from 2020 while their deaths still follow the old counties.

`code/exclusion_rules_v1.py` applies both rules to the normalized matrix. It writes
the list of omitted counties locally only (`logs/excluded_fips_DO_NOT_PUBLISH.txt`,
ignored by git), because naming the counties omitted under rule 1 would disclose that
each holds a cell of nine or fewer deaths. The rerun:

```sh
sh code/derive_w1.0_cc.sh
python3 code/exclusion_rules_v1.py \
    --in  BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv \
    --out BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv
sh code/derive_excl.sh pearson
sh code/derive_excl.sh spearman
sh code/run_standard_k120_w1.0.sh
python3 code/paper_numbers.py --cc full_w1.0/metric_x_death_cc_1.0_0.csv --out logs/numbers.json
python3 code/paper_numbers2.py --out logs/numbers2.json
python3 code/permutation_null_v2.py --n-perm 10000 --seed 20260918 --strata 20 \
    --out-prefix permutation_null/perm_null_strat20
python3 code/permutation_null_v2.py --n-perm 10000 --seed 20260918 \
    --out-prefix permutation_null/perm_null
python3 code/plot_permutation_null_v1.py
python3 code/geography_and_map_v1.py
python3 code/imputation_sensitivity_v1.py
```

`code/paper_numbers.py` and `code/paper_numbers2.py` compute every correlation-derived
number the manuscript reports (headline counts, Table 1, Tables S7, S8, S10 and S13)
from the definitions in the captions; run on the originally submitted 3,139-county
analysis they reproduce its numbers exactly. `code/plot_permutation_null_v1.py`
draws Figure S7, which was previously drawn ad hoc. The result files committed
elsewhere in this repository are still those of the originally submitted
3,139-county analysis.

---

## 4. Outputs

Tables (repo root):

- `master_sem_clusters_clean2_k120_w1.0.xlsx` — master per-variable workbook
- `extra_tables_clean2_k120_w1.0.xlsx`
- `sem_best_lp_clean2_k120_w1.0.xlsx`
- `SCE_paper_tables_consolidated_clean2_k120_w1.0.xlsx` — consolidated paper tables

Figures (`figures_2745/`): `fig1`–`fig7`, the super-cluster significance
heatmap, the 120×120 representative and full predictor×predictor CC heatmaps,
and the XDE dendrogram, plus `Metric_Super-Cluster_Cluster.csv`.

All generated outputs are listed in `.gitignore` and removed by `clean_all.sh`.

---

## 5. Repository layout

```
code/                          pipeline scripts + orchestrators
  run_all.sh                   stage 1 + stage 2 (regenerate everything)
  derive_w1.0_cc.sh            stage 1: raw -> full_w1.0/ CC files + XDE clustering
  run_standard_k120_w1.0.sh    stage 2: curated inputs -> tables + figures
  0000_Run_USCounty-v10.1.sh   original full from-raw pipeline
  clean_all.sh                 remove generated outputs
  _workbook_style.py           shared helper (Excel styling)
  *.py                         the ~25 analysis steps invoked by the above
data/
  raw/                         source files assembled by Step 01 (AHRF2020.fips.csv
                               NOT included — supply it per §8; *.names = AHRF column dictionaries)
  raw/census_pop/              county population by year + metric-year map (own-year normalization)
  BEN_..._explain_extended_2745.csv   variable descriptions
ward_sem_clean2_k120/          CURATED 120-cluster semantic clustering (fixed input)
full_w1.0/                     own-year, population-weighted CC matrix + death-CC + XDE clustering
hub_members_extensive_intensive.csv     extensive/intensive variable classification
sem_sc_assignments_manual.csv           manual super-cluster assignment
sem_sc_names_manual.csv                 manual super-cluster names
embeddings_mpnet_2745.npy      cached MPNet embeddings (lets the from-raw SEM step skip re-embedding)
requirements.txt               Python dependencies
build_minimal_repo.sh          how this minimal tree was assembled (provenance; re-runnable)

permutation_null/              referee revision: empirical null for the screen (§3)
suppression/                   referee revision: CDC WONDER suppression and recovery
revision_analyses/             referee revision: data-year crosstab, silhouette curve
imputation_sensitivity/        referee revision: the two data-handling sensitivity analyses
geography/                     referee revision: advantage index, regional tables, county maps
figures_revision/              referee revision: Figures 1 and 2 redrawn at printed size
```

---

## 6. Reproducibility notes

- **`full_w1.0/` is regenerable and verified.** `derive_w1.0_cc.sh` rebuilds
  `metric_x_death_cc_1.0_0.csv` and `full_cc_ase0_p=1.0_0.csv` from raw; both
  match the manuscript files to **max abs diff 0.0**. Both use **own-year**
  normalization (each extensive metric divided by its own metric-year county
  population, via `data/raw/census_pop/`) and **population_2019** weighting at
  power 1.0 — the project's standard "w1.0" condition. The XDE clustering in
  `full_w1.0/ward_xde_2745/` is also rebuilt from that own-year matrix.

- **`ward_sem_clean2_k120/` is a fixed input, not regenerated by `run_all`.**
  The 120-cluster semantic clustering has hand-written cluster labels
  (`sem100_labels.csv`) and a manually curated super-cluster assignment
  (`sem_sc_*_manual.csv`), so it is shipped as a curated artifact. The original
  `0000_Run_USCounty-v10.1.sh` does re-derive a semantic clustering from
  scratch (into `ward_sem_2745/`), but embedding/LLM nondeterminism means it can
  differ slightly from the manuscript version.

- **`0000` cannot reproduce the `full_w1.0/` files verbatim** — its death-CC
  step defaults to `ased_bl_2019` weighting (not `population_2019`) and its
  normalization is plain-2019 (not own-year). Use `derive_w1.0_cc.sh` for the
  faithful w1.0 recipe.

---

## 7. Large files (Git LFS)

The derived CC matrix `full_w1.0/full_cc_ase0_p=1.0_0.csv` (~54 MB) and
`embeddings_mpnet_2745.npy` (~8 MB) are tracked with Git LFS (see
`.gitattributes`). Run `git lfs install` **before** cloning, or the clone will
contain pointer stubs instead of the real files and the pipeline will fail.

---

## 8. AHRF data (not included)

The largest predictor source, the **Area Health Resources File (AHRF)**, is
**not redistributed in this repository**. The AHRF Data Use License Agreement
(HRSA / Bureau of Health Workforce) prohibits redistributing copies of the data;
only derived statistics and brief excerpts may be shared. Accordingly:

- **Included** (derived, redistributable): the correlation results in
  `full_w1.0/` (CC matrix + death-CC), variable *descriptions*
  (`data/…explain_extended_2745.csv`), and the AHRF column dictionaries
  (`data/raw/AHRF2020.fips.csv.names`, `*.f-metrics.names`).
- **Not included** (raw data): `data/raw/AHRF2020.fips.csv`.

`run_standard_k120_w1.0.sh` reproduces all tables and figures **without** it (it
reads the derived `full_w1.0/` files). To run the *from-raw* pipeline you must
obtain AHRF yourself and convert it to `data/raw/AHRF2020.fips.csv`:

1. Go to **https://data.hrsa.gov/data/download** and find the AHRF section
   (registration required). Releases are listed by year-pair; this analysis uses
   the **2019–2020** release (that is the "2020" in `AHRF2020.fips.csv`).

2. Download the **2019–2020 SAS** release (`AHRF_2019-2020_SAS.zip`). That
   release is offered only as ASCII or SAS — there is **no CSV** for it (HRSA
   added CSV only from 2022–2023 on) — and the SAS format is the one our
   converter reads. Unzip it to get `ahrf2020.sas7bdat`.

3. Convert SAS → CSV (needs `pip install pyreadstat`):

   ```sh
   python code/AHRF_SAS7BDAT_to_CSV.v2.2_progress.py \
       --sas ahrf2020.sas7bdat --out /tmp/ahrf_raw.csv
   ```

4. Add the 5-digit county `fips` key in the layout the pipeline expects:

   ```sh
   python code/add_fips_to_ahrf.py --in /tmp/ahrf_raw.csv \
       --out data/raw/AHRF2020.fips.csv
   ```
   (`fips` = AHRF `f00011` state code + `f00012` county code; the script also
   drops the redundant raw-FIPS column `f00002`, matching the original layout.)

This recipe is **verified**: a fresh 2019–2020 SAS download run through these two
steps reproduces the AHRF column layout used here exactly (3,230 counties ×
7,237 columns, 0 value differences).

5. Now `sh code/run_all.sh` runs end-to-end. The `data/raw/AHRF2020.fips.csv.names`
   and `*.f-metrics.names` files document the expected f-code columns if you need
   to cross-check the layout.

**Citation:** Area Health Resources Files (AHRF) 2019–2020. US Department of
Health and Human Services, Health Resources and Services Administration, Bureau
of Health Workforce, Rockville, MD.

## 9. Other data sources

Ancillary predictors include CDC/ATSDR SVI, Census county poverty, urban-area
crosswalks, and CDC vaccination summaries (all in `data/raw/`, public-domain
sources). Excess-death measures are county-level COVID-era mortality derived by
the authors.

County boundaries for the maps of §3 are `data/raw/geojson-counties-fips.json`,
the public 5-digit-FIPS county GeoJSON derived from US Census cartographic
boundary files.

## 10. License

Code and the authors' own derived outputs in this repository are released under
the **MIT License** (see `LICENSE`). This does not extend to third-party data:
AHRF is not included (HRSA Data Use Agreement, §8), and the bundled CDC/Census
source files remain under their respective public-domain / agency terms.
