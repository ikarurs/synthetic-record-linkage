"""Figures from source pixels and pipeline outputs; no historical text is redrawn."""
from textwrap import fill

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle
from PIL import Image

from ocr import ROOT

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
        fig.savefig(ROOT/'outputs'/f'{name}.{suffix}', dpi=160,
                    metadata={'Date': None} if suffix == 'svg' else {})


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
    fig = plt.figure(figsize=(14, 9.2))
    heading(fig, f'{case.upper()} / From printed entry to comparable fields',
            'Real archival excerpts · city, year and source identifiers concealed · names retained')
    grid = fig.add_gridspec(2, 4, left=.055, right=.96, bottom=.15, top=.80,
                           width_ratios=[1, 3.4, 1, 3.4], height_ratios=[1, 1.25],
                           wspace=.30, hspace=.18)
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
            detail.text(0, -.12, 'Enlarged detail from the outlined region',
                        transform=detail.transAxes, fontsize=9, color=MUTED, va='top')
        fields = fig.add_subplot(grid[1, 2*i:2*i+2])
        fields.set(xlim=(0, 1), ylim=(0, 1))
        fields.axis('off')
        fields.text(0, 1.04, 'SAVED OCR → DERIVED COMPARISON FIELDS', fontsize=10, weight='bold')
        y = .96
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


def comparison(pairs, decisions):
    """Show component evidence and its contribution to the ranking score."""
    style()
    fig = plt.figure(figsize=(15, 7))
    heading(fig, 'Why one candidate links and two do not',
            'Two selected anchors · three surname candidates · comparison scores are not probabilities')
    grid = fig.add_gridspec(1, 3, left=.055, right=.965, bottom=.26, top=.73,
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
        contributions = [.55*pair['surname_similarity'], .25*pair['given_agreement'],
                         .20*max(pair['career_similarity'], pair['institution_similarity'])]
        assert abs(sum(contributions)-pair['score']) < 1e-12
        for amount, color, hatch in zip(contributions, (BLUE, '#ddb56c', GREY), ('', '//', '..')):
            score.barh(i, amount, left=left, height=.34, color=color,
                       edgecolor='white', linewidth=.6, hatch=hatch)
            left += amount
        score.text(pair['score'], i-.23, f"{pair['score']:.3f}", ha='center', fontsize=11, weight='bold')
    score.axvline(.84, color=INK, linestyle='--', linewidth=1.2, zorder=0)
    score.text(.84, 1.05, 'Acceptance floor 0.84', transform=score.get_xaxis_transform(),
               ha='center', fontsize=10)
    score.set(xlim=(0, 1.03), xticks=[0, .25, .5, .75, 1], yticks=[], xlabel='Weighted ranking score')
    score.spines['left'].set_visible(False)
    score.grid(axis='x', color=GRID, linewidth=.6)
    score.set_axisbelow(True)
    fig.legend([Patch(facecolor=c, hatch=h) for c, h in zip((BLUE, '#ddb56c', GREY), ('', '//', '..'))],
               ['Surname × 0.55', 'Given name × 0.25', 'Best context × 0.20'],
               loc='lower right', bbox_to_anchor=(.975, .11), ncol=3, frameon=False, fontsize=10)
    a = next(d for d in decisions if d['case_id'] == 'A')
    fig.text(.055, .17, f"A: the lead over the next candidate is {a['margin']:.2f} (minimum required: 0.08).", fontsize=11)
    fig.text(.055, .065,
             'A high score alone cannot create a link: conflicting given names reject a candidate.\n'
             'Acceptance also checks both margins, mutual preference and source confidence. Selected cases do not measure accuracy.',
             fontsize=10, color=MUTED, linespacing=1.5)
    return fig
