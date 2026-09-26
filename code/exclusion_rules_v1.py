#!/usr/bin/env python3
"""
exclusion_rules_v1.py

The two county exclusions adopted on 24 September 2026, and a filtered copy of
the normalized matrix for the correlation steps.

Rule 1, minimum count. A county is omitted if it recorded fewer than 10 deaths
  in any age group used (all ages, under 65, 65 and over) in any year
  considered (2017 to 2024). Its excess-death ratio then rests on too few deaths
  to be stable, and publishing it would breach the CDC WONDER restriction on
  statistics based on nine or fewer deaths. The rule also removes the two
  counties with a zero baseline, Kalawao and Loving, whose outcome is undefined.

Rule 2, Connecticut. The eight Connecticut counties are omitted. From 2020 their
  population estimates follow the nine planning regions that replaced them,
  while their deaths still follow the old counties, so their outcome is wrong.

The list of omitted counties is written locally and must NOT be published:
naming the counties omitted under rule 1 discloses that each holds a cell of
nine or fewer deaths.

Dropping rows after normalization is equivalent to dropping them before,
because the 0-9,999 rescaling is linear and a correlation is unaffected by it.

Usage:
    python3 code/exclusion_rules_v1.py --in NORMED.csv --out NORMED_excl.csv
"""
import sys
import os
import argparse

import pandas as pd

EXTRACT = 'data/raw/usa-county-result.10Feb26.csv'
AGES = ['all', '0-64', '65+']
YEARS = list(range(2017, 2025))
MIN_DEATHS = 10
CONNECTICUT = '09'


def excluded():
    if not os.path.isfile(EXTRACT):
        sys.exit('The county mortality extract {path} is not in this repository: CDC WONDER rules forbid publishing counts of 1 to 9 deaths. Regenerate it with the Mortality.Watch county pipeline (commit aabee352cc505548fdf9b167884db01eb5d4681f) and place it at that path. See README, "County mortality extract".'.format(path=EXTRACT))
    r = pd.read_csv(EXTRACT, dtype={'fips': str}, low_memory=False)
    r['f'] = r['fips'].str.zfill(5)
    r = r[r['year'].astype(str).isin([str(y) for y in YEARS]) & r['age_group'].isin(AGES)]
    low = r.groupby('f')['deaths'].min() < MIN_DEATHS
    rule1 = set(low.index[low])
    rule2 = {f for f in r['f'].unique() if f.startswith(CONNECTICUT)}
    return rule1, rule2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--list', default='logs/excluded_fips_DO_NOT_PUBLISH.txt')
    a = ap.parse_args()
    rule1, rule2 = excluded()
    both = rule1 | rule2
    df = pd.read_csv(a.inp, dtype={'fips': str}, low_memory=False)
    f = df['fips'].astype(str).str.zfill(5)
    keep = ~f.isin(both)
    w = df['population_2019']
    print('counties in the matrix          : %d' % len(df))
    print('rule 1, fewer than %d deaths     : %d counties, %.3f%% of the population'
          % (MIN_DEATHS, f.isin(rule1).sum(), 100 * w[f.isin(rule1)].sum() / w.sum()))
    print('rule 2, Connecticut             : %d counties, %.3f%% of the population'
          % (f.isin(rule2).sum(), 100 * w[f.isin(rule2)].sum() / w.sum()))
    print('overlap                         : %d' % len(rule1 & rule2))
    print('kept                            : %d counties, %.3f%% of the population'
          % (keep.sum(), 100 * w[keep].sum() / w.sum()))
    df[keep].to_csv(a.out, index=False)
    with open(a.list, 'w') as fh:
        fh.write('# Omitted counties. DO NOT PUBLISH: rule 1 discloses cells of 9 or fewer deaths.\n')
        for x in sorted(both):
            fh.write('%s\t%s\n' % (x, 'connecticut' if x in rule2 else 'min_count'))
    print('wrote %s and the local list %s' % (a.out, a.list))


if __name__ == '__main__':
    main()
