"""Outcome figures use only invented towns, personnel and housing observations."""
import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

from visualise import style, heading, INK, BLUE, GOLD, GREY, MUTED, GRID


def decision_shares(summary):
    style()
    ordered = summary.sort_values('accepted_share', ascending=False)
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.subplots_adjust(left=.17, right=.83, top=.72, bottom=.24)
    heading(fig, 'Linkage decisions across six fictional towns',
            'Share of earlier personnel · sorted by accepted-link share · segment labels are people')
    colors, hatches = [BLUE, '#eed9b1', GREY], ['', '///', '']
    for y, (town, row) in enumerate(ordered.iterrows()):
        left = 0
        for status, color, hatch in zip(['accepted', 'review', 'not_observed'], colors, hatches):
            share = row[status+'_share']
            ax.barh(y, share, left=left, height=.6, color=color,
                    edgecolor=GOLD if status == 'review' else 'white', linewidth=.6, hatch=hatch)
            if share > 0:
                ax.text(left+share/2, y, f"{int(row[status])}", ha='center', va='center',
                        color='white' if status == 'accepted' else INK, weight='bold')
            left += share
        assert abs(left-1) < 1e-12
        ax.text(1.03, y, f"{row['accepted_share']:.1%}  ({int(row['accepted'])}/{int(row['baseline_people'])})",
                va='center', fontsize=11)
    ax.text(1.03, 1.05, 'Accepted / baseline', transform=ax.get_xaxis_transform(), fontsize=10, color=MUTED)
    ax.set(xlim=(0, 1), ylim=(len(ordered)-.6, -.6), yticks=range(len(ordered)),
           yticklabels=ordered.index, xticks=[0, .25, .5, .75, 1], xlabel='Share of the earlier personnel roster')
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.tick_params(axis='y', length=0, pad=12)
    ax.spines['left'].set_visible(False)
    fig.legend([Patch(facecolor=c, edgecolor=GOLD if h else c, hatch=h) for c,h in zip(colors, hatches)],
               ['Accepted', 'Review', 'Not observed'], frameon=False, ncol=3,
               loc='upper left', bbox_to_anchor=(.165, .82))
    fig.text(.055, .115,
             f"{int(summary['baseline_people'].sum())} invented people · {int(summary['accepted'].sum())} accepted · "
             f"{int(summary['review'].sum())} under review · {int(summary['not_observed'].sum())} not observed", weight='bold')
    fig.text(.055, .065, 'Not observed is a linkage status, not evidence that a person left. These shares are not true continuity rates.',
             color=MUTED, fontsize=10)
    return fig


def housing_panels(panel):
    style()
    periods = ['Year 1', 'Year 2', 'Year 3']
    towns = sorted(panel['town'].unique())
    assert len(towns) == 6 and not panel.duplicated(['town', 'period']).any()
    ymax = 2*math.ceil(panel['dwellings_per_1000'].max()/2)
    fig, axes = plt.subplots(2, 3, figsize=(12, 8.4), sharex=True, sharey=True)
    fig.subplots_adjust(left=.085, right=.96, top=.79, bottom=.20, wspace=.25, hspace=.48)
    heading(fig, 'Housing construction, town by town',
            'Completed dwellings per 1,000 residents · six fictional towns · identical axes in every panel')
    for ax, town in zip(axes.flat, towns):
        rows = panel.loc[panel['town'].eq(town)].set_index('period').reindex(periods)
        rates = rows['dwellings_per_1000']
        for x, rate in enumerate(rates):
            if math.isnan(rate):
                ax.text(x, .08, 'Missing', transform=ax.get_xaxis_transform(),
                        ha='center', color=MUTED, fontsize=10, style='italic')
                continue
            ax.vlines(x, 0, rate, color=GREY, linewidth=2)
            ax.scatter(x, rate, s=60, facecolor=BLUE if x == 2 else 'white',
                       edgecolor=BLUE, linewidth=1.6, zorder=3)
            ax.annotate(f'{rate:.1f}', (x, rate), xytext=(0, 8),
                        textcoords='offset points', ha='center', fontsize=11)
        ax.set(title=town, xlim=(-.4, 2.4), ylim=(0, ymax+.8),
               xticks=range(3), xticklabels=periods, yticks=range(0, ymax+1, 4))
        ax.tick_params(axis='x', labelbottom=True, length=0, pad=8)
        ax.tick_params(axis='y', length=0)
        ax.grid(axis='y', color=GRID, linewidth=.7)
        ax.set_axisbelow(True)
    observed = int(panel['dwellings_per_1000'].notna().sum())
    fig.text(.055, .108, f'{observed} of {len(panel)} town-period outcomes observed. A missing value has no point and no stem; it is not zero.', fontsize=11)
    fig.text(.055, .058, 'Rate = completed dwellings ÷ same-period population × 1,000. Markers show discrete annual flows, not a housing stock.\n'
             'Open circles: Years 1–2. Filled circles: Year 3. All observations and periods are invented.', fontsize=10, color=MUTED, linespacing=1.5)
    return fig


def linkage_scenario(panel):
    style()
    cross = panel.loc[panel['period'].eq('Year 3')].copy()
    cross['review_accepted_share'] = (cross['accepted']+cross['review'])/cross['baseline_people']
    assert cross['town'].is_unique and cross[['accepted_share', 'review_accepted_share', 'dwellings_per_1000']].notna().all().all()
    assert cross['review_accepted_share'].between(cross['accepted_share'], 1).all()
    fig, ax = plt.subplots(figsize=(12, 9.2))
    fig.subplots_adjust(left=.10, right=.95, top=.78, bottom=.25)
    heading(fig, 'How pending reviews change the comparison',
            'Year 3 · six fictional towns · the outcome stays fixed while the linkage assumption changes')
    for row in cross.itertuples():
        x, end, y = row.accepted_share, row.review_accepted_share, row.dwellings_per_1000
        ax.plot([x, end], [y, y], color=GREY, linewidth=1.5, zorder=1)
        ax.scatter(x, y, color=BLUE, s=30, zorder=3)
        ax.scatter(end, y, facecolor='white', edgecolor=GOLD, marker='D', s=20, linewidth=1.3, zorder=3)
        # ponytail: fixed labels for six towns; facet larger or crowded samples.
        below = row.town in ('Fictional 04', 'Fictional 06')
        ax.annotate(row.town, (x, y), xytext=(-4, -18 if below else 10),
                    textcoords='offset points', ha='right' if below else 'left', fontsize=10)
    ax.set(xlim=(0, 1), ylim=(0, 11), xticks=[0, .25, .5, .75, 1], yticks=[0, 2, 4, 6, 8, 10],
           xlabel='Share of earlier personnel linked to the later roster',
           ylabel='Completed dwellings per 1,000 residents')
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.grid(color=GRID, linewidth=.7)
    ax.set_axisbelow(True)
    fig.legend([Line2D([], [], marker='o', color=BLUE, linestyle='none', markersize=7),
                Line2D([], [], marker='D', markerfacecolor='white', color=GOLD, linestyle='none', markersize=7)],
               ['Accepted links only', 'Scenario: every review item becomes accepted'],
               loc='upper left', bbox_to_anchor=(.095, .835), ncol=2, frameon=False, fontsize=11)
    fig.text(.055, .135, 'Each connector joins two assumptions for the same town. It is not a confidence interval.', fontsize=11, weight='bold')
    fig.text(.055, .065, 'Both shares use 12 earlier people per town. The scenario is not an upper bound on true continuity: missed records can remain.\n'
             'Six invented observations describe plotting and sensitivity methods; they support no effect estimate or causal conclusion.',
             color=MUTED, fontsize=10, linespacing=1.5)
    return fig, cross
