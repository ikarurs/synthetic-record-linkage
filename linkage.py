"""Small, explicit linkage example over redacted real source excerpts."""
from collections import defaultdict
from difflib import SequenceMatcher
import json
import re
import unicodedata

from ocr import ROOT, read_page


def normalise(value):
    value = value.lower().translate(str.maketrans({'ä':'ae','ö':'oe','ü':'ue','ß':'ss'}))
    value = ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z]+', value))


def parse_name(value, order):
    value = re.sub(r'\b(?:Dr|Prof)\.?\s*', '', value, flags=re.I)
    if ',' in value:
        surname, given = value.split(',', 1)
        return normalise(given), normalise(surname)
    words = normalise(value).split()
    if len(words) < 2:
        return '', ' '.join(words)
    # ponytail: page-level order is visually reviewed for these excerpts. Mixed
    # lists and ambiguous compound names need the research workflow's context rule.
    if order == 'surname_first':
        return words[-1], ' '.join(words[:-1])
    if order == 'given_first':
        return ' '.join(words[:-1]), words[-1]
    raise ValueError('Unsupported name order')


def extract():
    manifest = json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
    if len({p['page_id'] for p in manifest}) != len(manifest):
        raise ValueError('Duplicate page ID')
    records, pages = [], []
    for meta in manifest:
        saved = read_page(meta)
        page = saved['page']
        for i, entry in enumerate(page['entries'], 1):
            given, surname = parse_name(entry['name'], meta['name_order'])
            records.append(dict(record_id=f"{meta['page_id']}:{i:03d}",page_id=meta['page_id'],
                town=meta['town'],period=meta['period'],name=entry['name'],given=given,surname=surname,
                role=entry['role'],title=entry['title'],institution=' > '.join(entry['institution_path']),
                address=entry['address'],raw_entry=entry['raw_entry'],
                ocr_confidence=page['confidence'],image_sha256=saved['image_sha256']))
        pages.append(dict(page_id=meta['page_id'],people=len(page['entries']),model=saved['model'],
                          confidence=page['confidence'],empty_reason=page['empty_result_reason']))
    return records,pages


def select_anchors(records, anchors):
    selected=[]
    for anchor in anchors:
        options=[r for r in records if r['page_id']==anchor['page_id'] and normalise(r['name'])==normalise(anchor['name_query'])]
        if len(options)!=1:
            raise ValueError(f"Anchor {anchor['case_id']} needs source review: found {len(options)} records")
        selected.append(dict(options[0],case_id=anchor['case_id']))
    return selected


def sim(a,b):
    return SequenceMatcher(None,normalise(a),normalise(b)).ratio() if a and b else 0.


def given_evidence(a,b):
    if not a or not b:
        return 'missing',0.
    if a==b:
        return 'exact',1.
    short,long=sorted((a,b),key=len)
    if long.startswith(short):
        return ('initial',.5) if len(short)==1 else ('abbreviation',.8)
    return 'conflict',0.


def career_text(value):
    value=normalise(value)
    for short,full in {'stadtamtm':'stadtamtmann','verwaltungsinsp':'verwaltungsinspektor',
                       'verw':'verwaltung','oberinsp':'oberinspektor'}.items():
        value=re.sub(r'\b'+short+r'\b',full,value)
    return value


def candidate_pairs(anchors,records):
    pairs=[]
    for left in anchors:
        for right in records:
            if right['period']!='later' or left['town']!=right['town']:
                continue
            surname=sim(left['surname'],right['surname'])
            if surname<.82:
                continue
            relation,given=given_evidence(left['given'],right['given'])
            # Compare role and title across fields: extraction can allocate a rank
            # to either field without losing the underlying printed evidence.
            career=max(sim(career_text(left[a]),career_text(right[b]))
                       for a in ('role','title') for b in ('role','title'))
            institution=sim(left['institution'],right['institution'])
            context=max(career,institution)
            score=.55*surname+.25*given+.20*context
            pairs.append(dict(case_id=left['case_id'],left_id=left['record_id'],right_id=right['record_id'],
                left_name=left['name'],right_name=right['name'],right_page=right['page_id'],
                surname_similarity=surname,given_relation=relation,given_agreement=given,
                career_similarity=career,institution_similarity=institution,score=score,
                ocr_min=min(left['ocr_confidence'],right['ocr_confidence'])))
    return sorted(pairs,key=lambda p:(p['case_id'],-p['score'],p['right_id']))


def find_matches(anchors,pairs,threshold=.84,margin=.08):
    if not 0<=threshold<=1 or not 0<=margin<=1:
        raise ValueError('Threshold and margin must be finite and in [0,1]')
    if len({(p['left_id'],p['right_id']) for p in pairs})!=len(pairs):
        raise ValueError('Duplicate candidate')
    grouped,reverse=defaultdict(list),defaultdict(list)
    for pair in pairs:
        grouped[pair['case_id']].append(pair)
        reverse[pair['right_id']].append(pair)
    for values in [*grouped.values(),*reverse.values()]:
        values.sort(key=lambda p:(-p['score'],p['left_id'],p['right_id']))
    decisions=[]
    for anchor in anchors:
        choices=grouped[anchor['case_id']]
        best=choices[0] if choices else None
        gap=best['score']-choices[1]['score'] if len(choices)>1 else best['score'] if best else 0.
        rivals=reverse[best['right_id']] if best else []
        reverse_gap=rivals[0]['score']-rivals[1]['score'] if len(rivals)>1 else best['score'] if best else 0.
        reason=('no_candidate' if not best else 'given_name_conflict' if best['given_relation']=='conflict'
                else 'insufficient_name_evidence' if best['given_relation'] in ('initial','missing')
                else 'ambiguous_candidates' if min(gap,reverse_gap)<=1e-10 or min(gap,reverse_gap)<margin
                else 'not_mutual_best' if rivals[0]['left_id']!=anchor['record_id']
                else 'source_uncertain' if best['ocr_min']<.8
                else 'below_threshold' if best['score']<threshold else 'accepted')
        status='accepted' if reason=='accepted' else 'no_link' if reason in ('no_candidate','given_name_conflict') else 'review'
        decisions.append(dict(case_id=anchor['case_id'],name=anchor['name'],status=status,reason=reason,
            right_id=best['right_id'] if status=='accepted' else '',
            best_candidate=best['right_name'] if best else '',score=best['score'] if best else None,
            margin=gap,reverse_margin=reverse_gap))
    return decisions
