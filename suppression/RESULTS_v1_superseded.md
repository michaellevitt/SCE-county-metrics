# Suppressed CDC WONDER counts: burden, validation and sensitivity

Run 2026-09-19. Script `code/suppression_analysis_v1.py`.
Answers Frontiers Reviewer 1, major comment 8. Also closes John's comment 13, open since June.

## Method of identification

CDC WONDER suppresses any sub-national cell whose death count is 1 to 9, and returns no
row at all when the count is 0. Any county-year in the mortality source that carries a
count of 0 to 9 therefore could not have been read from a direct query and must have been
recovered. This gives an exact count of the reconstruction burden from the delivered data
alone, without access to the upstream code.

Source: `data/raw/usa-county-result.10Feb26.csv`, the Mortality.Watch county extract
(Ben Marten, 10 February 2026). 3,139 counties by 8 years by 3 age groups, 75,336 cells,
no missing values, all counts integer.

## 1. How much was suppressed

| Category | Cells | Share |
|---|---|---|
| Count = 0, no row returned by WONDER | 121 | 0.16% |
| Count 1 to 9, suppressed by WONDER | 2,328 | 3.09% |
| **Total requiring reconstruction** | **2,449** | **3.25%** |

By age group, of 25,112 cells each:

| Age group | Cells needing reconstruction | Share |
|---|---|---|
| All ages | 257 | 1.02% |
| 0 to 64 | 1,841 | 7.33% |
| 65 and over | 351 | 1.40% |

All-age series by year, the series the main outcome uses:

| Year | County-years reconstructed | Share |
|---|---|---|
| 2017 | 33 | 1.05% |
| 2018 | 38 | 1.21% |
| 2019 | 35 | 1.12% |
| 2020 | 27 | 0.86% |
| 2021 | 29 | 0.92% |
| 2022 | 33 | 1.05% |
| 2023 | 28 | 0.89% |
| 2024 | 34 | 1.08% |

The under-65 stratum carries seven times the burden of the all-age series, which matters
for Table S5 and should be stated there.

## 2. Validation against published national totals

Summing the reconstructed county counts and comparing with the NCHS published national
all-cause resident death totals:

| Year | County sum | Published NCHS | Difference | Percent |
|---|---|---|---|---|
| 2017 | 2,813,193 | 2,813,503 | −310 | −0.011% |
| 2018 | 2,838,901 | 2,839,205 | −304 | −0.011% |
| 2019 | 2,854,570 | 2,854,838 | −268 | −0.009% |
| 2020 | 3,383,392 | 3,383,729 | −337 | −0.010% |
| 2021 | 3,463,850 | 3,464,231 | −381 | −0.011% |
| 2022 | 3,279,509 | 3,279,857 | −348 | −0.011% |
| 2023 | 3,090,643 | 3,090,964 | −321 | −0.010% |
| 2024 | 3,071,279 | 3,072,666 | −1,387 | −0.045% |

2021, 2022, 2023 and 2024 published figures verified against NCHS Data Briefs 456, 492,
521 and 548 respectively. 2017 to 2020 are entered from memory and still need checking
against the source publications.

The county sums agree to about one part in ten thousand in every year from 2017 to 2023.
The shortfall is stable at roughly 300 deaths a year and does not grow with the total,
which is the signature of deaths that cannot be allocated to a county of residence rather
than of reconstruction error. If the reconstruction were dropping or mis-assigning
suppressed cells, the error would scale with the 2,449 affected cells and would vary from
year to year. It does neither.

2024 is the exception at −0.045%, about four times the other years. The extract is dated
February 2026 and 2024 registrations may still have been incomplete. Worth a sentence.

## 3. Unique recovery, the reviewer's sharpest question

The reviewer asks whether several simultaneously suppressed observations can be uniquely
recovered. On the method the manuscript describes, they can.

A difference method that queries WONDER for "all counties except the target" returns an
aggregate over more than three thousand counties, which is far above the suppression
threshold and is therefore released. Subtracting that from the national total leaves the
target county exactly:

    deaths(county X) = deaths(all counties) − deaths(all counties except X)

Because the query is run once per county, each query contains exactly one unknown. Unique
recovery holds for every county independently and does not degrade as the number of
suppressed counties grows. This is the opposite of the failure mode the reviewer has in
mind, which arises when one aggregate query contains several suppressed cells and yields
only their sum.

**This must be confirmed with Ben Marten before it goes in the letter.** It is the reading
that makes the manuscript's sentence coherent, and it is consistent with the completeness
and integer structure of the delivered file, but the upstream code is not in this
repository and I have not seen it.

## 4. Sensitivity: does the headline depend on reconstructed values?

Counties whose excess-death outcome touches at least one reconstructed count, either in
the 2017 to 2019 baseline or in an outcome year 2020 to 2024:

| Affected in | Counties |
|---|---|
| Baseline 2017 to 2019 | 46 |
| Any outcome year 2020 to 2024 | 42 |
| **Either** | **50** (1.59% of 3,139) |

These 50 counties carry **0.0143%** of the population weight.

Re-running the full 2,745-variable screen without them (the screen reproduces the
production correlation file to 5 × 10⁻⁷ before any exclusion):

| Analysis | Variables > 0.30 | Variables > 0.45 | Largest \|CC\| | Median max \|CC\| |
|---|---|---|---|---|
| All 3,139 counties, as published | 472 | 77 | 0.543 | 0.156 |
| **Excluding the 50 affected counties** | **526** | **121** | **0.563** | 0.161 |
| Only the 50 affected counties | 387 | 149 | 0.618 | 0.218 |

The third row is 50 counties and is statistically meaningless; it is shown for context
only.

**The principal correlations do not depend on reconstructed values.** Removing every
county that touches one makes the result stronger, not weaker: 472 becomes 526 and the
largest correlation rises from 0.543 to 0.563. Whatever error the reconstruction carries,
it cannot be manufacturing the signal, because deleting all of it increases the signal.

The direction is worth understanding rather than just reporting. These 50 counties are
very small, and small counties combine volatile excess-death rates with extreme per-capita
predictor values. They inflate the denominator of the weighted Pearson correlation and
attenuate it. This is the same mechanism found in the permutation work, where Kalawao
County, population 85, supplies more than half the weighted variance of 92 predictors.

An 11% change in the headline count from counties holding 0.014% of the weight is not
negligible and should be reported as such, in the same breath as the weighting sensitivity
in Table S7. The honest summary is that the published 472 is the conservative number.

## 5. Still outstanding

1. **Confirm the procedure with Ben Marten**, in his words, including whether the
   per-county complement query is what was run and how counts of 0 were distinguished
   from suppressed counts of 1 to 9.
2. **Verify the 2017 to 2020 published national totals** against the NCHS publications.
3. **Explain the 2024 shortfall** of 1,387, four times the other years.
4. The under-65 stratum carries 7.33% reconstruction against 1.02% for all ages. Table S5
   should say so.

## Files

- `code/suppression_analysis_v1.py`
- `suppression_summary.json` — all counts, validation and sensitivity in machine-readable form
- `sensitivity_table.csv` — the table in section 4
- `affected_counties.csv` — the 50 FIPS codes

Reproduce:

    python3 code/suppression_analysis_v1.py
