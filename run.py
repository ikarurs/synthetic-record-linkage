"""Replay real OCR results offline and trace two reviewed matching examples."""
import csv
import json
from ocr import ROOT
from linkage import extract,select_anchors,candidate_pairs,find_matches


def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path,rows):
    if not rows:
        raise ValueError(f'No rows to export: {path.name}')
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def run():
    records,pages=extract()
    anchors=select_anchors(records,read_csv(ROOT/'data/anchors.csv'))
    anchor_cases={a['record_id']:a['case_id'] for a in anchors}
    earlier=[dict(r,case_id=anchor_cases.get(r['record_id'],'')) for r in records if r['period']=='earlier']
    pool=candidate_pairs(earlier,records)
    pairs=[p for p in pool if p['left_id'] in anchor_cases]
    decisions=find_matches(anchors,pool)
    # Reviewed outcomes enter only here, after matching.
    reviews=read_csv(ROOT/'data/reviewed_pairs.csv')
    compared=[]
    for review in reviews:
        decision=next(d for d in decisions if d['case_id']==review['case_id'])
        compared.append(dict(**decision,reviewed_decision=review['reviewed_decision'],review_evidence=review['evidence']))
    out=ROOT/'outputs'
    out.mkdir(exist_ok=True)
    for name,rows in [('records',records),('pages',pages),('comparison_pool',pool),
                      ('candidates',pairs),('matches',decisions),('review_comparison',compared)]:
        write_csv(out/f'{name}.csv',rows)
    return records,pages,anchors,pairs,decisions


if __name__=='__main__':
    result=run()
    print(json.dumps(result[-1],indent=2,ensure_ascii=True))
