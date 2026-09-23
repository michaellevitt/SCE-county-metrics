# Withheld file

`affected_counties.csv` is not published here.

It listed the 50 counties whose all-age annual death total falls below 10. Naming those
counties discloses, for each of them, that a CDC WONDER suppressed cell lies in the 1 to 9
range. CDC disclosure rules prohibit publishing a sub-national count of nine deaths or
fewer, and publishing the identity of the counties concerned gives the same information in
a different form.

The list is reproduced locally by `code/suppression_analysis_v1.py` from the mortality
extract, which is itself not redistributed. Only the count, 50, and the share of analysis
weight they carry, 0.0143%, are reported in the paper and in `suppression_summary.json`.

The same rule is applied to the maps in `geography/`: any county whose pooled 2020 and 2021
death count is nine or fewer is drawn grey rather than coloured, seven counties in all. See
`code/geography_and_map_v1.py`.
