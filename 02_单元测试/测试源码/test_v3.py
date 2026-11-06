import unittest
from cleaner import Cleaner, R
from run_v3 import split, CFG
from legacy.tests.test_pipeline import mkrows
import dq_audit as A


class V3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = R.load_adult()
        cls.parts = split(cls.raw, CFG['seeds'][0])
        cls.ref = cls.parts['detector_train']

    def test_partitions(self):
        self.assertEqual({k: len(v) for k,v in self.parts.items()}, CFG['partitions'])

    def test_low_capital_preserved(self):
        rows = [dict(self.ref[0], capital_gain=v) for v in [114., 401., 1000., 5000.]]
        fixed, _, _ = Cleaner(self.ref).repair(rows)
        self.assertEqual([r['capital_gain'] for r in fixed], [114., 401., 1000., 5000.])

    def test_illegal_overwrite_filled(self):
        row = dict(self.ref[0], age=999., fnlwgt=99999999.)
        fixed, events, _ = Cleaner(self.ref).repair([row])
        self.assertTrue(17 <= fixed[0]['age'] <= 90)
        self.assertLess(fixed[0]['fnlwgt'], 1500000)
        self.assertTrue(A.verify([row], A.rollback(fixed, events), R.COLS)['identical'])

    def test_label_never_changes(self):
        a = dict(self.ref[0], age=None, income='<=50K')
        b = dict(a, income='>50K')
        cleaner = Cleaner(self.ref)
        fa = cleaner.repair([a])[0][0]; fb = cleaner.repair([b])[0][0]
        self.assertEqual(fa.pop('income'), '<=50K'); self.assertEqual(fb.pop('income'), '>50K')
        self.assertEqual(fa, fb)

    def test_dual_education_uncertain(self):
        row = dict(self.ref[0], education='HS-GRAD', education_num=16.)
        fixed, _, alerts = Cleaner(self.ref).repair([row])
        self.assertEqual(fixed[0]['education_num'], 16.)
        self.assertIn((0, 'education_num'), alerts)

    def test_legal_conflict_review(self):
        row = dict(self.ref[0], education='HS-grad', education_num=16.)
        fixed, _, alerts = Cleaner(self.ref).repair([row])
        self.assertEqual(fixed[0]['education_num'], 16.)
        self.assertIn((0, 'education_num'), alerts)

    def test_no_self_reference(self):
        cleaner = Cleaner(self.ref)
        target = dict(self.ref[0], age=None)
        a = cleaner.repair([target])[0][0]
        b = cleaner.repair([target]+[dict(target, age=888888.)]*20)[0][0]
        self.assertEqual(a, b)

    def test_new_high_cardinality_unit(self):
        row = dict(self.ref[0], fnlwgt=234567000.)
        fixed, _, _ = Cleaner(self.ref).repair([row])
        self.assertEqual(fixed[0]['fnlwgt'], 234567.)

    def test_missing_indicator_survives_filling(self):
        row = dict(self.ref[0], age=None)
        fixed, _, _ = Cleaner(self.ref, 'knn').repair([row])
        self.assertIsNotNone(fixed[0]['age'])
        self.assertEqual(fixed[0]['__missing_age'], 1.)

    def test_reference_labels_excluded(self):
        without_labels=[{c:r[c] for c in r if c!='income'} for r in self.ref]
        row=dict(self.ref[0],age=None)
        self.assertEqual(Cleaner(self.ref).repair([row])[0],Cleaner(without_labels).repair([row])[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
