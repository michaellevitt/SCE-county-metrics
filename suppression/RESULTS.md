# Suppression and age standardization, answered from Ben Marten's source code

Revised 2026-09-19 after reading the upstream repository. **This supersedes the first
version** (`RESULTS_v1_superseded.md`), which inferred the suppression burden from the
delivered aggregate file and understated it by a factor of 25. The conclusion is
unchanged and in fact stronger, but the framing was wrong.

Source read: `/Users/levitt/levitt/tmp/covid19-KEEP/New_Clone_01Sep2025/us-county`,
modified 9 to 10 February 2026, matching the data extract dated 10 February 2026.
Key files `src/data/deaths_yasr.r`, `src/data/deaths_result.r`, `src/lib/result.r`,
`src/lib/std_pop.r`, `src/lib/config.r`.

---

## Question 1: age standardization (Reviewer 1, minor comment 9)

**The paper's outcome does not use an external standard population at all.** It is
indirectly standardized against each county's own pre-pandemic age-specific rates. Saying
only "age-standardized" in the Methods is what drew the referee's question, and the honest
answer is more interesting than a standard-million citation.

From `.calculate_asd` in `src/lib/result.r`, with `age` at single years:

    ased      = sum over age of deaths(age, year)                         [= total deaths]
    ased_bl   = sum over age of  mean_{2017..2019}[ deaths(age)/pop(age) ] x pop(age, year)
    asedx_p   = ased / ased_bl - 1

So the expected count applies the county's own mean 2017 to 2019 age-specific death rates
to its age structure in the index year. `bl_start_year = 2017`, `bl_end_year = 2019`,
`obs_end_year = 2024` (`src/lib/config.r`). This explains why `ased` equals the raw death
count in essentially every row: the standardization lives entirely in the denominator.

**The 2000 US Standard Million is used, but for a different column.** `src/lib/result.r`
line 166 calls `.calculate_asmr(..., std_pop = usa2000)`, parsed by `src/lib/std_pop.r`
from the SEER `stdpop.19ages.html` table "2000 U.S. Standard Million". That standard
produces the `asmr` and `asmrx_p` columns, which the paper does not use as its outcome.

**Age bands.** Single years of age. `src/data/deaths_result.r` reads
`out/county/deaths-yasr.csv.xz` at single-year-of-age, sex and race, filters to
`sex == "all"` and `race == "all"`, and collapses ages 85 to 99 and 100+ into `85+`,
giving 86 bands (0 to 84, plus 85+). Age "NS", not stated, is dropped.

**Sparse and zero cells.** `.redistribute_zero_pop` in `src/lib/result.r` handles the case
of an age cell with a zero population estimate but a non-zero death count, which occurs in
small counties: the death is carried forward into the next age band that has positive
population, and the zero-population band is dropped. This is the answer to the referee's
second half of comment 9.

**What to write in the paper.** That the outcome is an indirectly standardized excess-death
ratio, computed over single years of age to 85+, with each county's own 2017 to 2019
age-specific rates as the reference, and that no external standard population enters the
outcome. Because standardization is internal to the county, between-county differences in
age structure are removed by construction, which is what the Methods already claims.

---

## Question 2: the suppressed counts (Reviewer 1, major comment 8)

### The procedure, confirmed in code and in the raw downloads

`src/data/deaths_yasr.r`, in `parse_data`:

```r
totals <- totals[, !"fips", with = FALSE]
df2 <- df2[!is.na(year)][totals,
  on = c("year", "age", "sex", "race"),
  deaths := i.deaths - deaths
]
```

`i.deaths` is the national total and `deaths` is the value in the per-county file. For the
result to be that county's deaths, the per-county file must hold the national total
*excluding* that county. It does.

**Direct proof from the raw download.** The file
`data_wonder/yas/2018_n/2021_2023/06037.txt.xz` is named for Los Angeles County. Its
"Residence States" footnote enumerates every county in the query and runs
"... Lassen County, CA (06035); Madera County, CA (06039); ...", skipping 06037. The query
is every county except Los Angeles.

Worked example, 2021, age under 1, female:

| Quantity | Deaths |
|---|---|
| National total | 9,011 |
| All counties except Los Angeles | 8,839 |
| **Los Angeles County, by difference** | **172** |

So the method is:

    deaths(county X) = deaths(all counties) - deaths(all counties except X)

### Unique recovery: the referee's sharpest question

Each query is run once per county and contains exactly one unknown, so recovery is exact
for every county independently and does not degrade as the number of small counties grows.
The failure mode the referee has in mind, where one aggregate query holds several
suppressed cells and yields only their sum, cannot arise.

**The complement query is never itself suppressed.** Sampling 60 of the 3,142 per-county
files and parsing all 36,720 data rows: zero rows returned "Suppressed", and the smallest
cell value anywhere was 16, comfortably above the threshold of 10. This is expected, since
each complement aggregates more than three thousand counties, but it is worth stating
because it is the assumption the whole method rests on.

### How much the method recovers

At the single-year-of-age resolution the standardization actually uses, county by year by
age band, 2017 to 2024:

| Cell value | Cells | Share |
|---|---|---|
| Exactly 0 (no row returned by WONDER) | 857,998 | 39.68% |
| 1 to 9 (suppressed by WONDER) | 921,682 | 42.63% |
| **0 to 9, not obtainable by direct query** | **1,779,680** | **82.31%** |
| 10 or more | 382,446 | 17.69% |
| Total | 2,162,126 | |

Those cells hold 2,943,519 of 24,797,072 deaths, **11.87%** of all deaths in the period.
The share is stable at 80 to 84% in every year.

**This is the number to give the referee, and it is 25 times my earlier estimate.** The
first version of this document measured 3.25%, using the delivered file aggregated to all
ages, under 65 and 65 and over. That was the wrong level: the standardization runs on
single years of age, where four cells in five are below the suppression threshold.

The point is not that 82% of the data is uncertain. The point is the opposite. Without the
complement-difference method, four out of five cells and one death in eight would be
unavailable, and a county-level age-standardized analysis of this kind would not be
possible. The recovered values are exact arithmetic, not estimates.

### Validation

**Against published national totals**, summing the reconstructed county counts:

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

**All eight published totals are now verified against the NCHS Data Brief that reports
them**, each stating "a total of N resident deaths were registered in the United States":

| Year | Published total | Source |
|---|---|---|
| 2017 | 2,813,503 | Data Brief 328 |
| 2018 | 2,839,205 | Data Brief 355 |
| 2019 | 2,854,838 | Data Brief 395 |
| 2020 | 3,383,729 | Data Brief 427 |
| 2021 | 3,464,231 | Data Brief 456 |
| 2022 | 3,279,857 | Data Brief 492 |
| 2023 | 3,090,964 | Data Brief 521 |
| 2024 | 3,072,666 | Data Brief 548 |

The year-on-year changes the briefs state also reconcile with the totals: +25,702 for 2018,
+15,633 for 2019, +528,891 for 2020 and -188,893 for 2023. The series is internally
consistent as well as individually sourced.

The shortfall against our county sums is flat at about 300 deaths a year and does not scale
with the total, which is the signature of deaths with no county of residence rather than of
reconstruction error. 2024 is four times the other years, and the February 2026 extract
probably predates complete 2024 registration.

**Ben's own validation, built into the pipeline.** `src/data/deaths_yasr.r` reconstructs
state totals from the recovered county counts, compares them with independently retrieved
state totals, allows at most 60 deaths of difference per state-year for the "not stated"
age group, and calls `stopifnot` otherwise. The pipeline therefore cannot produce output
unless every state-year reconciles. This is a stronger internal check than anything the
manuscript currently reports and it should be cited.

### Sensitivity, and a correction to the first version

The first version defined 50 "reconstruction-dependent" counties and re-ran the screen
without them. That definition is not meaningful under the corrected understanding, because
every county cell is obtained by difference. Those 50 counties are better described as the
ones whose all-age annual total is itself under 10, that is the most extreme micro-counties.

Re-run on that reading, and relabelled:

| Analysis | Variables > 0.30 | Variables > 0.45 | Largest \|CC\| |
|---|---|---|---|
| All 3,139 counties, as published | 472 | 77 | 0.543 |
| Excluding 50 counties with an all-age annual total below 10 | 526 | 121 | 0.563 |

This is a micro-county robustness check, not a test of the reconstruction. It still
answers the referee's last bullet in substance: the principal correlations do not weaken
when the smallest and least reliable counties are removed, they strengthen. Combined with
the exactness of the arithmetic and the two validations above, there is no route by which
reconstruction error could be generating the reported signal.

---

## What still needs Ben

Both referee questions are now answered from the code, so the email can be much shorter.
Remaining items are courtesies and checks rather than blockers:

1. Confirm that the 01Sep2025 clone is the code that produced the 10 February 2026 extract.
2. Confirm the 2024 shortfall is incomplete registration. All eight published totals are
   now verified against their NCHS Data Briefs, so this is the only open question on the
   validation table.
3. Kalawao County Hawaii and Loving County Texas have a zero age-standardized baseline and
   come through as infinite rather than missing. Our code converts infinite to missing
   before correlating, so no result is affected, but the two files should agree.

## Files

- `code/suppression_analysis_v1.py` — the aggregate-level analysis and the sensitivity
- `RESULTS_v1_superseded.md` — the first version, kept for the record
- `suppression_summary.json`, `sensitivity_table.csv`
- `affected_counties.csv` is written locally but is **not published**: naming the
  counties would disclose that each holds a CDC WONDER cell in the 1 to 9 range. See
  `README_disclosure.md`.
