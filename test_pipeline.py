"""Offline source-to-decision check: python -m unittest -v."""
import copy
import unittest
from linkage import extract,select_anchors,candidate_pairs,find_matches,parse_name,given_evidence
from ocr import ROOT,read_page,validate
from run import read_csv


class PipelineCheck(unittest.TestCase):
    def test_reviewed_cases_and_abstention(self):
        records,pages=extract()  # Verifies all source/cache hashes and schemas.
        self.assertEqual(len(pages),4)
        self.assertEqual(len({r['record_id'] for r in records}),len(records))
        anchors=select_anchors(records,read_csv(ROOT/'data/anchors.csv'))
        pairs=candidate_pairs(anchors,records)
        decisions=find_matches(anchors,pairs)
        a,b=decisions
        self.assertEqual((a['status'],a['best_candidate']),('accepted','Aug. Huber'))
        self.assertEqual((b['status'],b['reason']),('no_link','given_name_conflict'))
        self.assertEqual(b['right_id'],'')
        self.assertEqual(decisions,find_matches(anchors,list(reversed(pairs))))
        winner=next(p for p in pairs if p['right_name']=='Aug. Huber')
        tied=copy.deepcopy(winner)
        tied['right_id']+='-other-person'
        self.assertEqual(find_matches(anchors,pairs+[tied],margin=0)[0]['status'],'review')
        # Competing anchors cannot both acquire the same later record.
        rival=copy.deepcopy(anchors[0]); rival['case_id']='C'; rival['record_id']+='-rival'
        competition=copy.deepcopy(winner); competition['case_id']='C'; competition['left_id']=rival['record_id']
        competing=find_matches(anchors+[rival],pairs+[competition])
        self.assertTrue(all(d['status']!='accepted' for d in competing if d['case_id'] in ('A','C')))
        self.assertEqual(parse_name('Huber August','surname_first'),parse_name('August Huber','given_first'))
        self.assertEqual(given_evidence('august','aug'),('abbreviation',.8))
        self.assertEqual(given_evidence('rupert','roman'),('conflict',0.))
        with self.assertRaises(ValueError): find_matches(anchors,pairs+[pairs[0]])
        with self.assertRaises(ValueError): find_matches(anchors,pairs,threshold=float('nan'))
        with self.assertRaises(ValueError): validate({'entries':[]})


if __name__=='__main__':
    unittest.main()
