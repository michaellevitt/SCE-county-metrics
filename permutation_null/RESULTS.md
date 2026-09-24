# Permutation null for the SCE county-metric screen

Run 2026-09-18. Script `code/permutation_null_v2.py`, seed 20260918, 10,000 permutations
per null. Answers Frontiers Reviewer 1, major comment 1.

## Validation

The script recomputes the weighted Pearson correlation coefficient (CC) from
`BEN_MERGED_MEASURES_imputed_20s_v1.31.GG.Add2024.NORMED.csv` with weights
population_2019^1.0 and per-(variable, year) valid sets. Against the production file
`full_w1.0/metric_x_death_cc_1.0_0.csv` the largest discrepancy is 5 × 10⁻⁷, which is the
rounding in that file. The observed statistics reproduce the manuscript exactly:

| Statistic | Reproduced | Manuscript |
|---|---|---|
| Variables with max \|CC\| > 0.30 | 472 | 472 |
| Variables with max \|CC\| > 0.45 | 77 | 77 |
| Largest \|CC\| | 0.543 | 0.543 |
| Per-year counts 2020–2024 | 248, 232, 50, 1, 35 | Table S5 |
| Kish effective sample size | 282.9 | 282 |

## Design

County labels of the whole five-year excess-death block are permuted together, so the
year-to-year structure of the outcome survives and the max-over-years statistic is not
inflated by treating the years as independent draws. Predictors and weights stay with
their county row.

The **primary null is stratified**: an outcome may move only to a county in the same
2019-population stratum (20 equal-count strata). The reason is counting noise. The
excess-death ratio of a very small county rests on a handful of deaths: below 5,000 people
its standard deviation is 0.36, three times the 0.12 of counties above 10,000, and above
10,000 it barely depends on size. Unrestricted permutation moves that noise onto the large
counties that carry most of the weight, 80% of it in counties above 100,000, and inflates
the null. Large counties do reach high values legitimately, the Bronx at 0.65 in 2020, but
not through noise. Two unstratified nulls are reported as sensitivity.

The number of strata is itself a choice. With 3,000 permutations at each setting, the
family-wise critical value is 0.388 at 10 strata, 0.409 at 20, 0.441 at 40, 0.477 at 100,
0.491 at 300 and 0.537 unrestricted. It is lowest near 10 to 20, because too few strata
leave the noise in place and too many absorb real association into the null. The count of
472 is far outside every one of these nulls; the claim that all 77 strong-band variables
clear family-wise correction holds at 20 strata but not unrestricted.

## Results

| Null | Observed > 0.30 | Null mean | Null p95 | Null max | p | Critical \|CC\| at FWER 5% | p for observed max |
|---|---|---|---|---|---|---|---|
| **Stratified by population (primary)** | 472 | **2.42** | 11 | 194 | **0.0001** | **0.408** | **0.0028** |
| Unrestricted | 472 | 3.04 | 12 | 164 | 0.0001 | 0.534 | 0.047 |
| Unrestricted, 252 high-leverage predictors removed | 442 | 2.23 | 8 | 150 | 0.0001 | 0.440 | 0.013 |

FWER is the family-wise error rate. The critical value is the 95th percentile of the null
distribution of the largest |CC| anywhere in the screen.

Stratified null, detailed:

| Percentile | Variables > 0.30 | Global max \|CC\| |
|---|---|---|
| 50 | 0 | 0.278 |
| 75 | 1 | 0.307 |
| 90 | 4 | 0.365 |
| 95 | 11 | 0.408 |
| 99 | 54 | 0.498 |
| 99.9 | 102 | 0.568 |

- 71.5% of permutations produce **no** variable above 0.30.
- No permutation of 10,000 reaches the observed 472, so p = 1/10,001 = 0.0001.
- 0.27% of permutations reach the observed global maximum of 0.543.
- Variables above 0.45 under the null: mean 0.05, 95th percentile 0, maximum 10.

## What this supports, and what it does not

**Supports.** The screen as a whole is not a multiple-comparisons artefact. The expected
number of variables above 0.30 under the null is 2.4 against 472 observed, an implied
false-discovery proportion of about 0.5%. All 77 variables above 0.45 clear the
family-wise critical value of 0.408, so the strong band survives correction for every one
of the 13,725 tests.

**Does not support.** Variables between 0.30 and 0.408 are not individually significant
after family-wise correction, even though collectively they are far beyond chance. The
moderate band should be described as a set that is jointly far in excess of the null, not
as 395 individually family-wise-significant findings.

**Heavy tail.** The null count is extremely skewed: median 0, mean 2.4, maximum 194. A
permutation that happens to align the outcome with a dominant axis of the predictor space
lights up hundreds of mutually correlated variables at once. This is a property of a
catalog of 2,745 correlated predictors and is an argument for reporting the count against
its own null rather than treating variables as independent.

## Incidental finding: single-county leverage

Computed while diagnosing the null tail, and relevant to the manuscript independently.

For each predictor, the share of its population-weighted variance contributed by its most
influential single county:

| Share from one county | Variables | % of 2,745 |
|---|---|---|
| > 25% | 534 | 19.5% |
| > 50% | 252 | 9.2% |
| > 75% | 105 | 3.8% |
| > 90% | 73 | 2.7% |

Median across all predictors: 9.8%.

The most frequent single culprit is FIPS 15005, Kalawao County, Hawaii, population 85,
which dominates more than half the weighted variance of 92 predictors and holds the
0–9,999 rescaling maximum for 254 of them. A tiny weight is outweighed by a squared
deviation of order 10⁸.

**This does not contaminate the headline result.** Among the 472 variables above 0.30 the
median single-county share is 8.4%, slightly *lower* than the 9.8% catalog median, and
only 30 of the 472 (6.4%) exceed a 50% share against 9.2% of all variables. Removing all
252 high-leverage predictors leaves 442 of the 472.

Two consequences worth stating in the paper:

1. The Pearson correlations of the high-leverage variables are attenuated towards zero,
   because one extreme county inflates the denominator. Variable f1476110 is the clearest
   case: its 2021 CC is −0.105 with Kalawao included and −0.530 without. This is a
   plausible part of why Spearman correlations run systematically larger than Pearson
   (17.3% versus about 29% above 0.30), which the manuscript reports but does not explain.
2. The 0–9,999 rescaling is a linear transformation and therefore changes no correlation.
   The outliers are in the underlying per-capita values, not created by the rescaling.

## Files

- `code/permutation_null_v2.py` — the analysis, with `--strata` and `--max-leverage`
- `perm_null_strat20_summary.json`, `perm_null_strat20_draws.csv` — primary
- `perm_null_summary.json`, `perm_null_draws.csv` — unrestricted
- `perm_null_lev50_summary.json`, `perm_null_lev50_draws.csv` — leverage-filtered
- `summary_table.csv` — the comparison table above
- `FigS_permutation_null.png` — two-panel figure
- `leverage.npy` — per-predictor single-county variance share, in metric-list order

Reproduce:

    python3 code/permutation_null_v2.py --n-perm 10000 --seed 20260918 --strata 20 \
        --out-prefix permutation_null/perm_null_strat20
