"""Offline source-to-decision check: python -m unittest -v."""
import copy
from pathlib import Path
import tempfile
import unittest
from linkage import extract,select_anchors,candidate_pairs,find_matches,parse_name,given_evidence
from ocr import ROOT,validate
from run import read_csv,write_csv


class PipelineCheck(unittest.TestCase):
    def test_reviewed_cases_and_abstention(self):
        records,pages=extract()  # Verifies all source/cache hashes and schemas.
        self.assertEqual(len(pages),4)
        self.assertEqual(len(records),137)
        self.assertEqual(len({r['record_id'] for r in records}),len(records))
        anchors=select_anchors(records,read_csv(ROOT/'data/anchors.csv'))
        earlier=[r for r in records if r['period']=='earlier']
        self.assertEqual(len(earlier),77)
        self.assertEqual(sum(r['period']=='later' for r in records),60)
        pairs=candidate_pairs(earlier,records)
        self.assertEqual(len(pairs),15)
        self.assertEqual(sum(p['left_id'] in {a['record_id'] for a in anchors} for p in pairs),3)
        decisions=find_matches(anchors,pairs)
        a,b=decisions
        self.assertEqual((a['status'],a['best_candidate']),('accepted','Aug. Huber'))
        self.assertEqual((b['status'],b['reason']),('no_link','given_name_conflict'))
        self.assertEqual(b['right_id'],'')
        self.assertAlmostEqual(a['margin'],.32)
        self.assertAlmostEqual(a['reverse_margin'],.31428571428571417)
        self.assertEqual((a['candidate_count'],a['reverse_candidate_count']),(2,2))
        self.assertEqual(a['reverse_runner_up_id'],'sample-a-before:016')
        self.assertIsNone(b['margin'])
        self.assertIsNone(b['reverse_margin'])
        self.assertEqual((b['candidate_count'],b['reverse_candidate_count']),(1,1))
        self.assertEqual(decisions,find_matches(anchors,list(reversed(pairs))))
        winner=next(p for p in pairs if p['left_id']==anchors[0]['record_id'] and p['right_name']=='Aug. Huber')
        tied=copy.deepcopy(winner)
        tied['right_id']+='-other-person'
        self.assertEqual(find_matches(anchors,pairs+[tied],margin=0)[0]['status'],'review')
        # Competing anchors cannot both acquire the same later record.
        rival=copy.deepcopy(anchors[0]); rival['case_id']='C'; rival['record_id']+='-rival'
        competition=copy.deepcopy(winner); competition['case_id']='C'; competition['left_id']=rival['record_id']
        competing=find_matches(anchors+[rival],pairs+[competition])
        self.assertTrue(all(d['status']!='accepted' for d in competing if d['case_id'] in ('A','C')))
        # A rival need not be a focal anchor to block the proposed link.
        competition['score']=.97
        blocked=find_matches(anchors,pairs+[competition])[0]
        self.assertEqual(blocked['reason'],'not_mutual_best')
        self.assertAlmostEqual(blocked['reverse_margin'],-.02)
        single,absent=find_matches(anchors,[winner])
        self.assertEqual(single['status'],'accepted')
        self.assertIsNone(single['margin'])
        self.assertIsNone(single['reverse_margin'])
        self.assertEqual((absent['reason'],absent['candidate_count']),('no_candidate',0))
        self.assertIsNone(absent['score'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'decisions.csv'
            write_csv(path,[single,absent])
            exported=read_csv(path)
            self.assertEqual(exported[0]['margin'],'')
            self.assertEqual(exported[0]['reverse_runner_up_score'],'')
        # The explicit conflict rule still rejects at a lower score threshold.
        self.assertEqual(find_matches(anchors,pairs,threshold=.60)[1]['reason'],'given_name_conflict')
        self.assertEqual(parse_name('Huber August','surname_first'),parse_name('August Huber','given_first'))
        self.assertEqual(given_evidence('august','aug'),('abbreviation',.8))
        self.assertEqual(given_evidence('rupert','roman'),('conflict',0.))
        with self.assertRaises(ValueError): find_matches(anchors,pairs+[pairs[0]])
        with self.assertRaises(ValueError): find_matches(anchors,pairs,threshold=float('nan'))
        with self.assertRaises(ValueError): validate({'entries':[]})


if __name__=='__main__':
    unittest.main()
