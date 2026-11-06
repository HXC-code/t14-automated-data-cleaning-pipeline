import hashlib
import inspect
import unittest
from pathlib import Path
from cleaner import Cleaner,R,ROOT
from baseline_cleaner import Cleaner as BaselineCleaner
from run_v3 import split,CFG,A
from outlier_guard import OutlierGuard,wilson_lower


class V31Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=R.load_adult();cls.parts=split(cls.raw,CFG['seeds'][0]);cls.ref=cls.parts['detector_train']
        cls.row=dict(cls.ref[0]);cls.cleaner=Cleaner(cls.ref)

    def test_statistics_do_not_authorize_modification(self):
        row=dict(self.row,age=90.,hours_per_week=99.,fnlwgt=1400000.,capital_gain=99999.,capital_loss=4356.)
        fixed,events,flags=self.cleaner.repair([row])
        for c in ['age','hours_per_week','fnlwgt','capital_gain','capital_loss']:
            self.assertEqual(fixed[0][c],row[c])

    def test_all_known_legal_positive_capitals_survive(self):
        for c in ['capital_gain','capital_loss']:
            legal=sorted({r[c] for r in self.raw if r[c] is not None and r[c]>0})
            rows=[dict(self.row,**{c:v}) for v in legal]
            fixed,_,_=self.cleaner.repair(rows)
            self.assertEqual([r[c] for r in fixed],legal)

    def test_unseen_legal_integer_999_review(self):
        row=dict(self.row,capital_gain=999.,capital_loss=999.)
        fixed,_,_=self.cleaner.repair([row])
        self.assertEqual(fixed[0]['capital_gain'],999.);self.assertEqual(fixed[0]['capital_loss'],999.)

    def test_age_candidate_not_unique_kept(self):
        row=dict(self.row,age=123.4)
        fixed,events,flags=self.cleaner.repair([row])
        self.assertEqual(fixed[0]['age'],123.4)
        self.assertIn((0,'age'),flags)
        self.assertTrue(any(r['col']=='age' for r in self.cleaner.last_review))

    def test_high_cardinality_candidate_review(self):
        row=dict(self.row,fnlwgt=800001.3)
        fixed,_,flags=self.cleaner.repair([row])
        self.assertEqual(fixed[0]['fnlwgt'],800001.3)
        self.assertIn((0,'fnlwgt'),flags)

    def test_capital_structural_evidence_and_concentration(self):
        row=dict(self.row,capital_loss=3000.1)
        fixed,events,flags=self.cleaner.repair([row])
        self.assertEqual(fixed[0]['capital_loss'],0.)
        event=next(e for e in events if e['col']=='capital_loss')
        self.assertGreaterEqual(event['candidate_evidence']['lower_bound'],.9)

    def test_unit_conversions_exactly_match_v3(self):
        rows=[]
        for c in ['age','hours_per_week','fnlwgt','capital_gain','capital_loss']:
            donor=next(r for r in self.ref if r[c]>0)
            rows.append(dict(donor,**{c:donor[c]*1000.}))
        new,ne,_=self.cleaner.repair(rows);old,oe,_=BaselineCleaner(self.ref).repair(rows)
        unit=lambda e:[x for x in e if x['action']=='unit_inverse']
        self.assertEqual(unit(ne),unit(oe))
        self.assertEqual(len(ne),len({(e['row'],e['col']) for e in ne}))
        for e in unit(ne):self.assertEqual(new[e['row']][e['col']],old[e['row']][e['col']])

    def test_unit_code_block_unchanged(self):
        old=(ROOT/'baseline_cleaner.py').read_text(encoding='utf-8');new=(ROOT/'cleaner.py').read_text(encoding='utf-8')
        start='                x = v / 1000';end="            e, en = r['education'], r['education_num']"
        block=lambda text:text[text.index(start):text.index(end)]
        self.assertEqual(block(old),block(new))

    def test_fd_code_block_unchanged(self):
        old=(ROOT/'baseline_cleaner.py').read_text(encoding='utf-8');new=(ROOT/'cleaner.py').read_text(encoding='utf-8')
        start="            e, en = r['education'], r['education_num']";end="            rel, sex = r['relationship'], r['sex']"
        block=lambda text:text[text.index(start):text.index(end)]
        self.assertEqual(block(old),block(new))

    def test_fd_existing_reliable_path_still_works(self):
        row=dict(self.row,education='HS-grad',education_num=99.)
        fixed,events,_=self.cleaner.repair([row])
        self.assertEqual(fixed[0]['education_num'],9.)
        self.assertTrue(any(e['action']=='reliable_dependency' for e in events))

    def test_zero_mad_only_alert_not_error(self):
        row=dict(self.row,capital_gain=114.)
        ev=self.cleaner.guard.evidence(row,'capital_gain')
        self.assertFalse(ev['structural'])
        self.assertEqual(self.cleaner.repair([row])[0][0]['capital_gain'],114.)

    def test_a_b_exact_v3_values_and_events(self):
        rows=[dict(self.row,age=123.4,capital_gain=3000.1),self.row]
        old,events,_=BaselineCleaner(self.ref).repair(rows)
        for policy in ['A','B']:
            fixed,ev,_=Cleaner(self.ref,outlier_policy=policy).repair(rows)
            self.assertEqual(fixed,old);self.assertEqual(ev,events)

    def test_persisted_audit_roundtrip(self):
        rows=[dict(self.row,capital_loss=3000.1,age=123.4)]
        fixed,events,_=self.cleaner.repair(rows)
        path=ROOT/'results/test_roundtrip.jsonl';A.write_log(events,path)
        self.assertTrue(A.verify(rows,A.rollback(fixed,A.read_log(path)),R.COLS)['identical'])

    def test_reference_labels_and_input_labels_unused(self):
        rows=[dict(self.row,capital_loss=3000.1)]
        ref=[{k:v for k,v in r.items() if k!='income'} for r in self.ref]
        self.assertEqual(Cleaner(ref).repair(rows)[0],self.cleaner.repair(rows)[0])
        a=self.cleaner.repair([dict(rows[0],income='>50K')])[0][0]
        b=self.cleaner.repair([dict(rows[0],income='<=50K')])[0][0]
        a.pop('income');b.pop('income');self.assertEqual(a,b)

    def test_inference_has_no_truth_argument(self):
        self.assertEqual(list(inspect.signature(Cleaner.repair).parameters),['self','rows'])

    def test_wilson_lower_bound_is_conservative(self):
        self.assertLess(wilson_lower(5,5),.90)
        self.assertGreater(wilson_lower(990,1000),.90)
        self.assertEqual(wilson_lower(0,0),0.)


if __name__=='__main__':unittest.main(verbosity=2)
