import os
import sys
# analyse_despair_metrics.py
# Analyses pre-pandemic despair/transport proxy metrics against pandemic-era
# excess mortality across age groups (All, GE65, LT65) and years 2020-2024.
#
# Inputs:
#   metric_x_death_cc_0_1_csv.gz
#   BEN_MERGED_MEASURES_imputed_20s_v1_31_GG_Add2024.explain
#
# Outputs:
#   despair_cc_trajectory.png  -- CC by year/age for suicide, MVA, homicide
#   despair_lp_lt65.png        -- LP trajectory LT65 for all despair/proxy metrics
#
# Usage:
#   python3 analyse_despair_metrics.py
#   python3 analyse_despair_metrics.py --lp-sig -14 --lp-near -5
#   python3 analyse_despair_metrics.py --death-cc my_file.gz --explain my.explain

import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


LP_ORDER = [
    'LP_asedx_p_2020',     'LP_asedx_p_2020_GE65', 'LP_asedx_p_2020_LT65',
    'LP_asedx_p_2021',     'LP_asedx_p_2021_GE65', 'LP_asedx_p_2021_LT65',
    'LP_asedx_p_2022',     'LP_asedx_p_2022_GE65', 'LP_asedx_p_2022_LT65',
    'LP_asedx_p_2023',     'LP_asedx_p_2023_GE65', 'LP_asedx_p_2023_LT65',
    'LP_asedx_p_2024',     'LP_asedx_p_2024_GE65', 'LP_asedx_p_2024_LT65',
]
CC_ORDER   = [c.replace('LP_', '') for c in LP_ORDER]
BIT_LABELS = ['2020A','2020G','2020L','2021A','2021G','2021L',
              '2022A','2022G','2022L','2023A','2023G','2023L','2024A','2024G','2024L']
YEARS      = [2020,2020,2020,2021,2021,2021,2022,2022,2022,2023,2023,2023,2024,2024,2024]
AGES       = ['All','GE65','LT65'] * 5
YEARS_X    = [2020, 2021, 2022, 2023, 2024]


def build_explain(path):
    df = pd.read_csv(path)
    # Support both column naming conventions
    if 'METRIC_VALUE' in df.columns and 'EXPLAIN' in df.columns:
        return dict(zip(df['METRIC_VALUE'], df['EXPLAIN']))
    elif 'metric' in df.columns and 'explain' in df.columns:
        return dict(zip(df['metric'], df['explain']))
    else:
        raise ValueError(f'Cannot find metric/explain columns in {path}. Columns: {df.columns.tolist()}')


def find_despair_metrics(explain):
    """Return dict of {group_name: [metric_ids]} for despair/transport groups."""
    groups = {
        'Suicide':                  [],
        'Motor vehicle accidents':  [],
        'Homicide':                 [],
        'Alcohol services':         [],
        'Medicare Rx Drug (opioid proxy)': [],
        'Mental health NHSC':       [],
        'Mental health HPSA':       [],
        'Community mental health':  [],
    }
    for m, d in explain.items():
        dl = d.lower()
        if 'suicide'                                      in dl: groups['Suicide'].append(m)
        if 'motor_vehicle_accident'                       in dl: groups['Motor vehicle accidents'].append(m)
        if 'homicide'                                     in dl: groups['Homicide'].append(m)
        if 'alcohol' in dl and 'chemical' in dl           :      groups['Alcohol services'].append(m)
        if any(k in dl for k in ['prescription_drug','opioid','narcotic']): groups['Medicare Rx Drug (opioid proxy)'].append(m)
        if 'national_health_service_corps' in dl and 'mental' in dl:        groups['Mental health NHSC'].append(m)
        if 'health_professions_shortage'   in dl and 'mental' in dl:        groups['Mental health HPSA'].append(m)
        if 'community_mental_health'       in dl         :       groups['Community mental health'].append(m)
    return groups


def print_cc_lp_table(metrics_dict, lp, cc, lp_sig, lp_near):
    """Print CC and LP for each metric across all 15 death measures."""
    print(f"\nCC and LP by death measure")
    print(f"  * = LP <= {lp_sig}   ~ = LP <= {lp_near}   (blank = weaker than {lp_near})\n")
    header = f"{'Metric':<40s}" + ''.join(f'{b:>7s}' for b in BIT_LABELS)
    print(header)
    print("-" * (40 + 7*15))
    for name, m in metrics_dict.items():
        if m not in lp.index:
            print(f"{name:<40s}  [not in death matrix]")
            continue
        lp_row = lp.loc[m].values
        cc_row = cc.loc[m].values
        cc_str = ''.join(
            f"{cc_row[j]:+7.3f}" if lp_row[j] <= lp_near else '      .'
            for j in range(15)
        )
        lp_str = ''.join(
            (f"  {'*' if lp_row[j] <= lp_sig else '~'}{lp_row[j]:5.1f}"
             if lp_row[j] <= lp_near else '      .')
            for j in range(15)
        )
        print(f"{name:<40s}{cc_str}")
        print(f"  {'LP':<38s}{lp_str}")
        print()


def plot_cc_trajectories(core_metrics, lp, cc, lp_sig, lp_near, outpath):
    """
    Panel plot: one panel per metric, CC by year for All / GE65 / LT65.
    Stars = LP <= lp_sig; open circles = LP <= lp_near.
    """
    n = len(core_metrics)
    fig, axes = plt.subplots(1, n, figsize=(5.5*n, 5), sharey=False)
    if n == 1:
        axes = [axes]

    colors  = {'All': '#555555', 'GE65': '#377EB8', 'LT65': '#E41A1C'}
    lstyles = {'All': '--',       'GE65': ':',       'LT65': '-'}
    lwidths = {'All': 1.5,        'GE65': 1.5,       'LT65': 2.5}

    for ax, (name, m) in zip(axes, core_metrics.items()):
        if m not in lp.index:
            ax.set_title(f"{name}\n[not in matrix]", fontsize=9)
            continue
        lp_row = lp.loc[m].values
        cc_row = cc.loc[m].values

        for age in ['All', 'GE65', 'LT65']:
            idx     = [i for i in range(15) if AGES[i] == age]
            cc_vals = [cc_row[i] for i in idx]
            lp_vals = [lp_row[i] for i in idx]
            ax.plot(YEARS_X, cc_vals,
                    color=colors[age], ls=lstyles[age], lw=lwidths[age],
                    marker='o', ms=5, label=age)
            for yr, cv, lpv in zip(YEARS_X, cc_vals, lp_vals):
                if lpv <= lp_sig:
                    ax.plot(yr, cv, '*', color=colors[age], ms=13, zorder=5)
                elif lpv <= lp_near:
                    ax.plot(yr, cv, 'o', color=colors[age], ms=8,
                            markerfacecolor='none', markeredgewidth=1.8, zorder=5)

        ax.axhline(0, color='black', lw=0.8)
        ax.axvline(2021.5, color='grey', lw=0.8, ls='--', alpha=0.6)
        ax.set_title(name, fontsize=9, fontweight='bold')
        ax.set_xlabel('Pandemic year', fontsize=9)
        ax.set_ylabel('Correlation coefficient (CC)', fontsize=9)
        ax.set_xticks(YEARS_X)
        ax.set_xlim(2019.7, 2024.3)
        ax.legend(fontsize=8, title='Age group', title_fontsize=8)
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        'Pre-pandemic Despair Metrics vs Pandemic-era Excess Mortality\n'
        f'Stars = LP\u2264{lp_sig} (significant)   Open circles = LP\u2264{lp_near} (near-sig)   '
        'Dashed line = 2021/2022 boundary\n'
        'LT65 signal strengthens late-pandemic -- consistent with deaths-of-despair hypothesis',
        fontsize=10, y=1.02
    )
    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {outpath}")
    print('Saved ' + os.path.basename(outpath) + '  [' + 
          outpath, file=sys.stderr, flush=True)


def plot_lp_lt65(all_metrics, lp, lp_sig, lp_near, outpath):
    """
    LP trajectory for LT65 only across all despair/proxy metrics.
    Y-axis inverted (more negative = stronger).
    Only metrics where at least one LT65 year reaches LP <= lp_near are shown.
    """
    palette = ['#E41A1C','#FF7F00','#984EA3','#4DAF4A','#377EB8',
               '#A65628','#F781BF','#999999','#1B9E77','#D95F02']
    lt65_idx = [i for i in range(15) if AGES[i] == 'LT65']

    fig, ax = plt.subplots(figsize=(11, 5))
    plotted = 0
    for (name, m), color in zip(all_metrics.items(), palette):
        if m not in lp.index:
            continue
        lp_row  = lp.loc[m].values
        lt65_lp = [lp_row[i] for i in lt65_idx]
        if min(lt65_lp) > lp_near:          # skip if no year reaches threshold
            continue
        ax.plot(YEARS_X, lt65_lp, marker='o', ms=6, lw=2,
                color=color, label=name)
        plotted += 1

    ax.axhline(lp_sig,  color='black', lw=1.3, ls='--',
               label=f'LP = {lp_sig} (significance threshold)')
    ax.axhline(lp_near, color='grey',  lw=0.9, ls=':',
               label=f'LP = {lp_near}')
    ax.set_xlabel('Pandemic year', fontsize=10)
    ax.set_ylabel('Log p-value (LP)', fontsize=10)
    ax.set_title(
        'LT65 Excess Mortality: LP Trajectory for Despair / Opioid Proxy Metrics\n'
        'More negative = stronger association   '
        f'(only metrics reaching LP \u2264 {lp_near} shown)',
        fontsize=11
    )
    ax.set_xticks(YEARS_X)
    ax.set_xlim(2019.7, 2024.3)
    ax.legend(fontsize=8, loc='lower left')
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {outpath}")
    print('Saved ' + os.path.basename(outpath) + '  [' + 
          outpath, file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='Analyse pre-pandemic despair metrics vs pandemic excess mortality.')
    parser.add_argument('--death-cc',  default='metric_x_death_cc_0_1_csv.gz')
    parser.add_argument('--explain',   default='BEN_MERGED_MEASURES_imputed_20s_v1_31_GG_Add2024.explain')
    parser.add_argument('--lp-sig',    type=float, default=-13.0,
                        help='LP threshold for significance (default: -13)')
    parser.add_argument('--lp-near',   type=float, default=-5.0,
                        help='LP threshold for near-sig display (default: -5, use -5 to see near-sig patterns)')
    parser.add_argument('--out-traj',  default='despair_cc_trajectory.png')
    parser.add_argument('--out-lp',    default='despair_lp_lt65.png')
    args = parser.parse_args()

    print("Loading data...")
    death    = pd.read_csv(args.death_cc, index_col=0)
    explain  = build_explain(args.explain)
    lp       = death[LP_ORDER]
    cc       = death[CC_ORDER]

    # -- Discover metrics
    groups   = find_despair_metrics(explain)
    groups   = {k: [m for m in v if m in death.index] for k, v in groups.items()}

    # -- Print group summary
    print(f"\nGroup summary (sign pattern at LP <= {args.lp_near}):\n")
    print(f"{'Metric':12s}  {'best_LP':>8s}  {'Sign pattern':17s}  Description")
    print("-"*110)
    for grp_name, mlist in groups.items():
        if not mlist:
            print(f"\n[{grp_name}]  -- no metrics in death matrix")
            continue
        print(f"\n[{grp_name}]  ({len(mlist)} metrics)")
        rows = []
        for m in mlist:
            lp_row = lp.loc[m].values
            cc_row = cc.loc[m].values
            best   = lp_row.min()
            sig    = lp_row <= args.lp_near
            signs  = ''.join(
                ('+' if cc_row[j] > 0 else '-') if sig[j] else '.'
                for j in range(15)
            )
            rows.append((m, best, signs, explain.get(m, '')))
        rows.sort(key=lambda x: x[1])
        for m, best, signs, desc in rows:
            print(f"  {m:12s}  {best:8.2f}  {signs}  {desc}")

    # -- Core despair metrics for CC trajectory plot
    # pick most significant metric from each of the 3 core despair groups
    core_metrics = {}
    for grp in ['Suicide', 'Motor vehicle accidents', 'Homicide']:
        mlist = groups.get(grp, [])
        if not mlist:
            continue
        best_m = min(mlist, key=lambda m: lp.loc[m].min())
        label  = explain.get(best_m, best_m)
        if '=' in label:
            label = label[:label.index('=')].replace('_', ' ').strip()
        core_metrics[label] = best_m

    if core_metrics:
        print_cc_lp_table(core_metrics, lp, cc, args.lp_sig, args.lp_near)
        plot_cc_trajectories(core_metrics, lp, cc, args.lp_sig, args.lp_near, args.out_traj)

    # -- All despair metrics for LT65 LP plot
    # collect best metric per group; pre-filter to those reaching lp_near in LT65
    lt65_idx = [i for i in range(15) if AGES[i] == 'LT65']
    all_plot_metrics = {}
    for grp_name, mlist in groups.items():
        if not mlist:
            continue
        best_m  = min(mlist, key=lambda m: lp.loc[m].min())
        lt65_lp = [lp.loc[best_m].values[i] for i in lt65_idx]
        if min(lt65_lp) <= args.lp_near:
            all_plot_metrics[grp_name] = best_m

    if all_plot_metrics:
        plot_lp_lt65(all_plot_metrics, lp, args.lp_sig, args.lp_near, args.out_lp)

    print("\nDone.")


if __name__ == '__main__':
    main()
