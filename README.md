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

```sh
# clone WITH Git LFS — large derived files are stored in LFS (see §6)
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

**Typical use:** `sh code/run_standard_k120_w1.0.sh` to build all tables and
figures from the included derived data, then `sh code/clean_all.sh` to reset.

> **Note:** `run_standard_k120_w1.0.sh` works out of the box. The from-raw paths
> (`run_all.sh`, `derive_w1.0_cc.sh`, `0000_…`) additionally require the AHRF
> source file, which is **not** included — see **§"AHRF data (not included)"**.

`run_all.sh` is just `derive_w1.0_cc.sh` (stage 1) followed by
`run_standard_k120_w1.0.sh` (stage 2); run either alone if you only need that
half.

---

## 3. Outputs

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

## 4. Repository layout

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
                               NOT included — supply it per §7; *.names = AHRF column dictionaries)
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
```

---

## 5. Reproducibility notes

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

## 6. Large files (Git LFS)

The derived CC matrix `full_w1.0/full_cc_ase0_p=1.0_0.csv` (~54 MB) and
`embeddings_mpnet_2745.npy` (~8 MB) are tracked with Git LFS (see
`.gitattributes`). Run `git lfs install` **before** cloning, or the clone will
contain pointer stubs instead of the real files and the pipeline will fail.

---

## 7. AHRF data (not included)

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

## 8. Other data sources

Ancillary predictors include CDC/ATSDR SVI, Census county poverty, urban-area
crosswalks, and CDC vaccination summaries (all in `data/raw/`, public-domain
sources). Excess-death measures are county-level COVID-era mortality derived by
the authors.

## 9. License

Code and the authors' own derived outputs in this repository are released under
the **MIT License** (see `LICENSE`). This does not extend to third-party data:
AHRF is not included (HRSA Data Use Agreement, §7), and the bundled CDC/Census
source files remain under their respective public-domain / agency terms.
