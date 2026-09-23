# The four remaining Frontiers revision analyses

Run 2026-09-19. Scripts `code/revision_analyses_v1.py` and `code/silhouette_curve_v1.py`.

Two of the four turned up errors in the manuscript. Both are in our favour on the science
and against us on the bookkeeping.

---

## A. Super-cluster by data-year crosstab (Reviewer 1, major comment 4)

Data year parsed from the explain string exactly as `code/make_master_excel_v12.py` does,
and cross-checked against the f-code's last two digits: the two methods agree on all 2,725
variables that carry a year, with zero disagreements.

Median data year by super-cluster, and the share dated 2019 or later:

| SC | Super-cluster | n | Median year | Range | % 2019 or later |
|---|---|---|---|---|---|
| 1 | Race, Ethnicity and Population by Age | 463 | 2010 | 2010–2018 | 0.0 |
| 2 | Geography, Environment and Housing | 94 | 2013 | 1960–2020 | 14.9 |
| 3 | Socioeconomic, Insurance and Demographic | 412 | 2014 | 2010–2019 | 1.0 |
| 4 | Vital Statistics and Total Physician Counts | 88 | 2016 | 2010–2019 | 5.7 |
| 5 | Poverty, Insurance Coverage and Public Programs | 176 | 2018 | 2010–2019 | 15.9 |
| 6 | Primary Care, Generalist and Diagnostic Physicians | 597 | 2018 | 2016–2019 | 0.3 |
| 7 | Surgical, Procedural and Specialty Physicians | 270 | 2018 | 2018 only | 0.0 |
| 8 | Commuting and Industry Employment | 48 | 2014 | 2014–2018 | 0.0 |
| 9 | Aggregate Physician and Facility Totals | 180 | 2018 | 2018 only | 0.0 |
| 10 | Hospital Telehealth and Advanced Imaging | 43 | 2018 | 2010–2018 | 0.0 |
| 11 | Hospital Capacity and Nursing and Allied Staffing | 374 | 2018 | 2001–2020 | 14.2 |

Full crosstab in `A_supercluster_x_datayear.csv`.

The two families differ in a way worth stating. The demographic and socioeconomic
super-clusters are the *older* ones: SC1 is almost entirely 2010 census data and SC3 and
SC8 are mostly 2014. The health-system super-clusters are almost uniformly 2018. So the
stronger correlations come from the older measurements, not from anything closer to the
pandemic. That is the opposite of what a reverse-causality or contamination concern would
predict, and it is the most useful thing this table says.

Counts of variables per super-cluster here are the full 2,745. Table S1 reports 2,727
because it drops the 18 zero-variance variables. The difference falls entirely in SC2
(+6), SC5 (+1), SC6 (+7) and SC7 (+4), which sums to 18.

**This closes the outstanding super-cluster 2 question**: SC2 has 94 variables in total and
88 with a valid correlation. The Pearson-versus-Spearman working file reporting 94 is not
inconsistent with Table S1 reporting 88, and no reconciliation is needed beyond a footnote.

---

## B. Excluding predictors dated 2020 (Reviewer 1, major comment 4)

**The manuscript is wrong about this number.** The text says "only 40 variables from year
2020". The true figure is **11**.

Table S6's 2020 row of 40 is a catch-all. It comprises:

| Component | n |
|---|---|
| Variables genuinely carrying data year 2020 | 11 |
| Variables with no data year at all, pooled into the 2020 row | 20 |
| Extra columns in Table S6's wider 2,754-variable universe | 9 |
| **Total shown in Table S6** | **40** |

Every other year in Table S6 reproduces exactly (2010 = 589, 2014 = 345, 2015 = 12,
2016 = 71, 2017 = 3, 2018 = 1,539, 2019 = 95, and the small pre-2010 rows). Only the 2020
row is inflated. The 20 undated variables are contiguous-county identifiers, census region
and division codes, and FIPS codes, none of which has a measurement year at all.

The 11 genuinely 2020-dated variables, with their maximum absolute correlation:

| Variable | Description | Max \|CC\| |
|---|---|---|
| f0979220 | Health Professions Shortage Area code, dentists | 0.162 |
| f1249220 | Health Professions Shortage Area code, mental health | 0.154 |
| f1419320 | Metropolitan Division code | 0.083 |
| f1389320 | Combined Statistical Area code | 0.083 |
| f1389120 | Core Based Statistical Area code | 0.058 |
| f0978720 | Health Professions Shortage Area code, primary care | 0.027 |
| f1406720 | Core Based Statistical Area indicator code | 0.020 |
| f1419420 | Metropolitan Division name | no CC |
| f1389420 | Combined Statistical Area name | no CC |
| f1389220 | Core Based Statistical Area name | no CC |
| f1419520 | Core Based Statistical Area county status | no CC |

Every one is an administrative or geographic code. Not one is a substantive socioeconomic
or health-system measurement, and the largest correlation any of them achieves is 0.162,
well inside the weak band.

Sensitivity:

| Analysis | n | Variables > 0.30 | Variables > 0.45 | Largest \|CC\| |
|---|---|---|---|---|
| All variables, as published | 2,727 | 472 | 77 | 0.5429 |
| Excluding the 11 dated 2020 | 2,720 | 472 | 77 | 0.5429 |

Nothing changes, because none of the 11 was contributing anything.

**This is a strong answer to the referee.** His concern is that predictor information could
have been measured during the pandemic. In fact 11 of 2,745 variables carry a 2020 data
year, all 11 are administrative geography codes, and removing them changes no reported
number. The correction from 40 to 11 makes our position better, and it has to be made
anyway because Table S6 as printed is wrong.

---

## C. How many clusters the 472 span (Reviewer 1, minor comment 11)

| Set | Variables | Distinct clusters (of 120) | Distinct super-clusters (of 11) |
|---|---|---|---|
| Max \|CC\| > 0.30 | 472 | **58** | **10** |
| Max \|CC\| > 0.45 | 77 | **18** | **4** |

Concentration: the largest single cluster contributes 32 of the 472, the ten largest
contribute 228 (48%), and the median represented cluster contributes 5.

The ten clusters contributing most:

| n | SC | Cluster |
|---|---|---|
| 32 | 3 | Civilian Labor Force by Race, Sex and Status |
| 28 | 1 | Hispanic or Latino Population by Age and Sex |
| 26 | 1 | White Non-Hispanic Population by Age and Sex |
| 23 | 5 | Poverty Status by Race, Age and Family |
| 22 | 5 | Uninsured and Insured Under-65 Estimates |
| 21 | 3 | Household and Family Structure by Race |
| 20 | 1 | Some Other Race Population by Age and Sex |
| 20 | 3 | Household Income Brackets by Race and Ethnicity |
| 19 | 3 | Educational Attainment Percentages by Race |
| 17 | 1 | Hispanic and Latino Detailed Origin Population |

Full list in `C_clusters_among_472.csv`.

The referee is right that 472 is not 472 independent findings, and this supports our own
reading rather than undercutting it. The 472 collapse to 58 semantic clusters, and the 77
strongest to 18 clusters in only 4 super-clusters. The signal is a broad socioeconomic
gradient expressed through many redundant measures, which is what the paper argues.

---

## D. Silhouette against k (Reviewer 1, major comment 6)

Recomputed from `embeddings_normed.npy` with the pipeline's own recipe: row-normalise,
euclidean pdist, Ward linkage, fcluster maxclust, euclidean silhouette. Reproduces the
seven published values in `ward_sem_clean2_k120/silhouette_scores.csv` to 2 × 10⁻⁸.

Extended from k = 2 to k = 1000:

| k | 2 | 10 | 20 | 40 | 60 | 80 | 100 | **120** | 150 | 200 | 300 | 500 | 700 | 1000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Silhouette | 0.114 | 0.084 | 0.140 | 0.224 | 0.299 | 0.345 | 0.387 | **0.423** | 0.445 | 0.477 | 0.530 | 0.595 | 0.637 | 0.660 |

**The silhouette rises monotonically over the entire range and does not peak.** It cannot
select k = 120, and the referee is right to say so. The dendrogram's merge-height gaps do
not help either: the largest gaps are at k = 2, 4 and 7, reflecting the top-level split
between the demographic and health-system halves, with nothing distinguishing 120 from its
neighbours.

The honest position, which is close to what our Discussion already says but which the
Results overstates, is that **k = 120 is a granularity choice and not an optimum**. It was
chosen to make clusters small enough to act as a de-duplication unit and large enough to
carry an interpretable label. Every result in the paper is reported at the level of the 11
super-clusters, and the contrast between the two families survives the purely algorithmic
two-way dendrogram cut (29.2% against 7.6%, versus 30.5% against 7.1% for the content-based
grouping).

The manuscript sentence that the k = 120 and k = 11 choices were "justified by silhouette
metrics and dendrogram structure" is not supportable and should be rewritten.

Figure: `FigS_silhouette_vs_k.png`.

---

## Errors found, to add to the three already listed in the response letter

4. **Table S6's 2020 row.** Printed as 40; the true count of variables carrying a 2020
   data year is 11. The row silently absorbs 20 undated administrative variables and 9
   columns from a wider universe. The Methods sentence "only 40 variables from year 2020"
   must become 11.
5. **The silhouette justification.** The claim that k = 120 was "justified by silhouette
   metrics" does not hold: the criterion rises monotonically to k = 1000.
6. **Stale artifact.** `ward_sem_clean2_k120/metrics_with_labels.tsv` carries the
   pre-2026-06-09 super-cluster numbering, in which SC1 is nursing and allied health
   rather than race and ethnicity. It disagrees with `sem_sc_assignments.csv`, which is
   the file the pipeline actually uses and which matches Table S1. Anyone rebuilding from
   the repository could pick up the wrong mapping. It should be regenerated or deleted
   before the code is made public.

## Files

- `A_supercluster_x_datayear.csv`, `A_supercluster_year_summary.csv`
- `B_drop2020_sensitivity.csv`
- `C_clusters_among_472.csv`
- `D_silhouette_curve.csv`, `D_merge_gaps.csv`, `FigS_silhouette_vs_k.png`
- `ABC_summary.json`
