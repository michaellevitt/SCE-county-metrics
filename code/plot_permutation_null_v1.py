#!/usr/bin/env python3
"""
plot_permutation_null_v1.py

Figure S7, the permutation null, drawn from the draws written by
permutation_null_v2.py. The published figure was drawn ad hoc; this script
reproduces its layout so that it can be regenerated.

Usage:
    python3 code/plot_permutation_null_v1.py
"""
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker

RED, BLUE, GREEN, GREY = '#c44e52', '#4c72b0', '#55a868', '#bbbbbb'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='permutation_null')
    ap.add_argument('--out', default='permutation_null/FigS_permutation_null.png')
    a = ap.parse_args()
    s = pd.read_csv(f'{a.dir}/perm_null_strat20_draws.csv')
    u = pd.read_csv(f'{a.dir}/perm_null_draws.csv')
    js = json.load(open(f'{a.dir}/perm_null_strat20_summary.json'))
    obs_n = js['observed']['gt030']
    obs_m = js['observed']['max_absCC']
    crit = js['fwer_critical_absCC']
    n_perm = len(s)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    top = int(np.ceil((max(obs_n, s.n_gt_030.max()) + 1) / 100.0) * 100)
    ax1.hist(s.n_gt_030, bins=np.arange(0, top + 5, 5), color=BLUE, alpha=0.85)
    ax1.set_yscale('log')
    ax1.set_xlim(0, top)
    mean = s.n_gt_030.mean()
    ax1.axvline(mean, color='k', ls='--', lw=1.2)
    ax1.text(mean + top * 0.03, 0.97, 'null mean %.1f' % mean, transform=ax1.get_xaxis_transform(),
             va='top', fontsize=10)
    ax1.axvline(obs_n, color=RED, lw=2.2)
    ax1.text(obs_n - top * 0.02, 0.98, 'observed\n%d' % obs_n, color=RED, ha='right', va='top',
             fontsize=11, fontweight='bold', transform=ax1.get_xaxis_transform())
    ax1.set_xlabel('variables with max |CC| > 0.30', fontsize=11)
    ax1.set_ylabel('permutations (log scale)', fontsize=11)
    ax1.set_title('A  Count above the moderate band', loc='left', fontsize=12, fontweight='bold')

    ax2.hist(u.global_max_absCC, bins=60, color=GREY, alpha=0.7, label='unrestricted null')
    ax2.hist(s.global_max_absCC, bins=60, color=BLUE, alpha=0.85, label='stratified null')
    ax2.axvline(crit, color=GREEN, ls='--', lw=2)
    ax2.text(crit + 0.005, 0.45, 'FWER 5%%\ncritical %.3f' % crit, color=GREEN, fontsize=10,
             transform=ax2.get_xaxis_transform())
    ax2.axvline(obs_m, color=RED, lw=2.2)
    # label to the right of the line, unless the line is near the right edge
    right = obs_m < ax2.get_xlim()[1] - 0.16
    ax2.text(obs_m + (0.01 if right else -0.01), 0.72, 'observed\n%.3f' % obs_m, color=RED,
             fontsize=11, fontweight='bold', ha='left' if right else 'right',
             transform=ax2.get_xaxis_transform())
    ax2.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.1))
    ax2.set_xlabel('largest |CC| anywhere in the screen', fontsize=11)
    ax2.set_ylabel('permutations', fontsize=11)
    ax2.legend(frameon=False, fontsize=10, loc='upper right')
    ax2.set_title('B  Global maximum correlation', loc='left', fontsize=12, fontweight='bold')

    fig.suptitle('Permutation null, %s county-label permutations of the 2020–2024 excess-death '
                 'outcome' % format(n_perm, ','), fontsize=12)
    fig.tight_layout()
    fig.savefig(a.out, dpi=200)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
