"""Figures from source pixels and pipeline outputs; no historical text is redrawn."""
from textwrap import fill

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle
from PIL import Image

from ocr import ROOT
from linkage import WEIGHTS, score_components

INK = '#203343'
BLUE = '#23658b'
GOLD = '#926018'
GREY = '#c6ced4'
MUTED = '#586875'
GRID = '#e4e9ed'


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
        'text.color': INK, 'axes.labelcolor': INK, 'xtick.color': MUTED,
        'ytick.color': MUTED, 'axes.edgecolor': GREY,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.titleweight': 'bold', 'axes.titlelocation': 'left',
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'savefig.facecolor': 'white', 'svg.fonttype': 'none'})


def heading(fig, title, subtitle):
    fig.text(.055, .95, title, fontsize=21, weight='bold', va='top')
    fig.text(.055, .90, subtitle, fontsize=11, color=MUTED, va='top')


def export(fig, name):
    """PNG for notebook/GitHub reading, SVG for scalable reuse."""
    for suffix in ('png', 'svg'):
        path = ROOT/'outputs'/f'{name}.{suffix}'
        fig.savefig(path, dpi=160,
                    metadata={'Date': None} if suffix == 'svg' else {})
        if suffix == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')


# Hand-reviewed display windows on already redacted images, not OCR detections.
# These only change the viewport: source files and their hashes stay untouched.
DETAILS = {
    'a': [('sample-a-before:023', (1080, 945, 1595, 1095)),
          ('sample-a-after:027', (800, 180, 1590, 310))],
    'b': [('sample-b-before:024', (15, 1430, 790, 1875)),
          ('sample-b-after:006', (70, 875, 1530, 1100))],
}


def pages(case, records):
    """Compare untouched source details with the actual saved OCR fields."""
    style()
    fig = plt.figure(figsize=(14, 9.6))
    heading(fig, f'{case.upper()} / From printed entry to comparable fields',
            'Real archival excerpts · city, year and source identifiers concealed · names retained')
    grid = fig.add_gridspec(3, 4, left=.055, right=.96, bottom=.15, top=.80,
                           width_ratios=[1, 3.4, 1, 3.4], height_ratios=[1, .14, 1.25],
                           wspace=.30, hspace=.12)
    for i, (record_id, box) in enumerate(DETAILS[case]):
        row = next(r for r in records if r['record_id'] == record_id)
        fig.text(.055 + i*.465, .842,
                 'EARLIER  /  surname first' if i == 0 else 'LATER  /  given name first',
                 fontsize=11, weight='bold', color=BLUE)
        with Image.open(ROOT/'data/pages'/f"{row['page_id']}.png") as source:
            locator = fig.add_subplot(grid[0, 2*i])
            locator.imshow(source)
            x0, y0, x1, y1 = box
            assert 0 <= x0 < x1 <= source.width and 0 <= y0 < y1 <= source.height
            locator.add_patch(Rectangle((x0, y0), x1-x0, y1-y0,
                                        fill=False, edgecolor=BLUE, linewidth=2))
            locator.set_anchor('N')
            locator.axis('off')
            detail = fig.add_subplot(grid[0, 2*i+1])
            detail.imshow(source)
            detail.set(xlim=(x0, x1), ylim=(y1, y0))
            detail.set_anchor('N')
            detail.axis('off')
        caption = fig.add_subplot(grid[1, 2*i:2*i+2])
        caption.axis('off')
        caption.text(0, .55, 'Outlined region enlarged at right; original pixels retained.',
                     transform=caption.transAxes, fontsize=9, color=MUTED, va='center')
        fields = fig.add_subplot(grid[2, 2*i:2*i+2])
        fields.set(xlim=(0, 1), ylim=(0, 1))
        fields.axis('off')
        fields.text(0, 1.02, 'SAVED OCR → DERIVED COMPARISON FIELDS', fontsize=10, weight='bold')
        y = .89
        for label, value in [
            ('Printed name', row['name']),
            ('Parsed name', f"{row['given']}  |  {row['surname']}"),
            ('Role', row['role'] or '— empty in OCR'),
            ('Title / rank', row['title'] or '— empty in OCR'),
            ('Institution', row['institution']),
            ('Raw entry', row['raw_entry']),
        ]:
            wrapped = fill(value, width=46, break_long_words=False)
            fields.text(0, y, label, va='top', fontsize=10, color=MUTED)
            fields.text(.25, y, wrapped, va='top', fontsize=10.5,
                        weight='bold' if label in ('Printed name', 'Parsed name') else 'normal')
            y -= .068 * (wrapped.count('\n')+1) + .047
        fields.text(0, -.08, record_id, fontsize=9, color=MUTED)
    note = ('Name order changes and August becomes Aug. The rank appears in different OCR fields;\n'
            'cross-field comparison recovers the agreement without overwriting either extraction.'
            if case == 'a' else
            'Rupert and Roman conflict despite the shared surname. Rank and office also differ.\n'
            'This rejected candidate cannot establish absence from the complete later roster.')
    fig.text(.055, .075, note, fontsize=11, linespacing=1.5)
    return fig


def comparison(pairs, decisions, pool, records):
    """Show focal evidence and both directions of the full excerpt comparison."""
    style()
    fig = plt.figure(figsize=(15, 10.8))
    threshold = decisions[0]['threshold']
    assert all(d['threshold'] == threshold for d in decisions)
    heading(fig, 'Why one candidate links and two do not',
            f'{len(decisions)} selected anchors · {len(pairs)} focal candidate pairs · scores are not probabilities')
    grid = fig.add_gridspec(1, 3, left=.055, right=.965, bottom=.49, top=.79,
                           width_ratios=[2.5, 4, 4], wspace=.25)
    labels, matrix, score = [fig.add_subplot(grid[0, i]) for i in range(3)]
    for ax in (labels, matrix, score):
        ax.set_ylim(len(pairs)-.5, -.5)
    labels.axis('off')
    fields = ['surname_similarity', 'given_agreement', 'career_similarity', 'institution_similarity']
    values = [[p[f] for f in fields] for p in pairs]
    cmap = LinearSegmentedColormap.from_list('agreement', ['#f3f6f8', BLUE])
    matrix.imshow(values, vmin=0, vmax=1, cmap=cmap, aspect='auto')
    matrix.set(xticks=range(4), xticklabels=['Surname', 'Given\nname', 'Rank /\nrole', 'Office'], yticks=[])
    matrix.xaxis.tick_top()
    matrix.tick_params(axis='both', length=0, pad=12)
    for spine in matrix.spines.values():
        spine.set_visible(False)
    for i, pair in enumerate(pairs):
        accepted = any(d['right_id'] == pair['right_id'] and d['case_id'] == pair['case_id'] for d in decisions)
        status = 'Accepted link' if accepted else 'Given-name conflict' if pair['given_relation'] == 'conflict' else 'Not selected'
        labels.text(0, i-.18, f"{pair['case_id']}  {pair['left_name']}", fontsize=11, weight='bold')
        labels.text(0, i+.03, f"→ {pair['right_name']}", fontsize=11)
        labels.text(0, i+.25, status, fontsize=10, color=BLUE if accepted else GOLD)
        for j, value in enumerate(values[i]):
            suffix = '\nprefix' if j == 1 and pair['given_relation'] == 'abbreviation' else '\nconflict' if j == 1 and pair['given_relation'] == 'conflict' else ''
            matrix.text(j, i, f'{value:.2f}{suffix}', ha='center', va='center',
                        color='white' if value >= .6 else INK, fontsize=11)
        left = 0
        contributions = list(score_components(pair).values())
        assert abs(sum(contributions)-pair['score']) < 1e-12
        for amount, color, hatch in zip(contributions, (BLUE, '#ddb56c', GREY), ('', '//', '..')):
            score.barh(i, amount, left=left, height=.34, color=color,
                       edgecolor='white', linewidth=.6, hatch=hatch)
            left += amount
        score.text(pair['score'], i-.23, f"{pair['score']:.3f}", ha='center', fontsize=11, weight='bold')
    score.axvline(threshold, color=INK, linestyle='--', linewidth=1.2, zorder=0)
    score.text(threshold, 1.05, f'Acceptance floor {threshold:.2f}', transform=score.get_xaxis_transform(),
               ha='center', fontsize=10)
    score.set(xlim=(0, 1.03), xticks=[0, .25, .5, .75, 1], yticks=[], xlabel='Weighted ranking score')
    score.spines['left'].set_visible(False)
    score.grid(axis='x', color=GRID, linewidth=.6)
    score.set_axisbelow(True)
    fig.legend([Patch(facecolor=c, hatch=h) for c, h in zip((BLUE, '#ddb56c', GREY), ('', '//', '..'))],
               [f"Surname × {WEIGHTS['surname']:.2f}", f"Given name × {WEIGHTS['given']:.2f}",
                f"Best context × {WEIGHTS['context']:.2f}"],
               loc='lower right', bbox_to_anchor=(.975, .407), ncol=3, frameon=False, fontsize=10)
    a = next(d for d in decisions if d['case_id'] == 'A')
    chosen = next(p for p in pairs if p['case_id'] == 'A' and p['right_id'] == a['right_id'])
    directions = [
        ('Forward: later entries for Huber August', 'left_id', chosen['left_id'], 'right_name', 'margin', .20),
        ('Reverse: earlier entries for Aug. Huber', 'right_id', chosen['right_id'], 'left_name', 'reverse_margin', .68),
    ]
    for title, key, value, name, margin_key, left in directions:
        ax = fig.add_axes([left, .17, .275, .17])
        candidates = sorted([p for p in pool if p[key] == value], key=lambda p: (-p['score'], p['left_id'], p['right_id']))
        for y, pair in enumerate(candidates):
            focal = pair['left_id'] == chosen['left_id'] and pair['right_id'] == chosen['right_id']
            ax.hlines(y, 0, pair['score'], color=GREY, linewidth=1.5)
            ax.scatter(pair['score'], y, facecolor=BLUE if focal else 'white', edgecolor=BLUE,
                       marker='o' if focal else 'D', s=40, zorder=3)
            ax.annotate(f"{pair['score']:.3f}", (pair['score'], y), xytext=(0, 9),
                        textcoords='offset points', ha='center', fontsize=10)
        ax.set(xlim=(0, 1.04), ylim=(len(candidates)-.4, -.6),
               yticks=range(len(candidates)), yticklabels=[p[name] for p in candidates],
               xticks=[0, .5, 1], xlabel='Ranking score')
        ax.tick_params(axis='y', length=0, pad=8)
        ax.set_title(title, fontsize=11, pad=20)
        ax.spines['left'].set_visible(False)
        ax.grid(axis='x', color=GRID, linewidth=.7)
        ax.set_axisbelow(True)
        gap = a[margin_key]
        explanation = ('No competing candidate' if gap is None else
                       f"Margin {gap:.3f} ≥ {a['required_margin']:.2f} required")
        ax.text(0, -.43, explanation, transform=ax.transAxes, fontsize=11, weight='bold')
    earlier = sum(r['period'] == 'earlier' for r in records)
    later = sum(r['period'] == 'later' for r in records)
    fig.text(.055, .035,
             f'Competition uses all {earlier} earlier and {later} later excerpt entries: {len(pool)} pairs pass the surname filter, including conflicts.\n'
             'These are excerpt-level checks, not a complete roster search. Name evidence and source confidence are additional acceptance checks.',
             fontsize=10, color=MUTED, linespacing=1.5)
    return fig
