import inspect,json,unittest
from pathlib import Path
from candidates import CandidateBank,RepairEngine
from protocol import ROOT,R,A,FEATURES,Cleaner,parts,CFG


class V32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=parts(CFG['seeds'][0]);cls.ref=cls.p['reference'];cls.row=dict(cls.p['downstream_fit'][0]);cls.bank=CandidateBank(cls.ref,20260601)

    def engine(self,methods=None,overwrite='A'):
        return RepairEngine(Cleaner(self.ref,'conditional'),self.bank,methods,overwrite)

    def test_protected_sources_byte_identical(self):
        for name in ['cleaner.py','outlier_guard.py','baseline_cleaner.py']:
            self.assertEqual((ROOT/name).read_bytes(),(ROOT.parent/'V3.1'/name).read_bytes())

    def test_reference_and_matrix_exclude_income(self):
        self.assertTrue(all('income' not in r for r in self.bank.ref))
        a=self.bank.model_matrix([dict(self.row,income='>50K')],'age')
        b=self.bank.model_matrix([dict(self.row,income='<=50K')],'age')
        self.assertEqual(a.tolist(),b.tolist())

    def test_inference_has_no_truth_argument(self):
        self.assertEqual(list(inspect.signature(RepairEngine.repair).parameters),['self','rows'])

    def test_target_is_not_a_model_predictor(self):
        a=self.bank.model_matrix([dict(self.row,age=20.)],'age')
        b=self.bank.model_matrix([dict(self.row,age=80.)],'age')
        self.assertEqual(a.tolist(),b.tolist())

    def test_preserve_all_original_missing_indicators(self):
        row=dict(self.row,workclass=None,age=None,capital_loss=None)
        fixed,_,_=self.engine({'workclass':'B','age':'B','capital_loss':'B'}).repair([row])
        for c in FEATURES:self.assertEqual(fixed[0]['__missing_'+c],float(row[c] is None))

    def test_missing_indicator_survives_second_pass(self):
        engine=self.engine({'age':'B','workclass':'B'})
        first=engine.repair([dict(self.row,age=None,workclass=None)])[0]
        second=engine.repair(first)[0]
        self.assertEqual(second[0]['__missing_age'],1.)
        self.assertEqual(second[0]['__missing_workclass'],1.)

    def test_estimate_is_never_claimed_as_original(self):
        fixed,events,_=self.engine({'age':'B'}).repair([dict(self.row,age=None)])
        event=next(e for e in events if e['action'].startswith('v32_missing'))
        self.assertFalse(event['strict_restoration_claim'])
        self.assertEqual(event['candidate_kind'],'approximate_imputation')

    def test_unreliable_overwrite_is_reviewed(self):
        engine=self.engine(overwrite='E');row=dict(self.row,fnlwgt=99999999.)
        fixed,_,flags=engine.repair([row])
        self.assertEqual(fixed[0]['fnlwgt'],99999999.)
        self.assertIn((0,'fnlwgt'),flags)
        self.assertTrue(any(r['col']=='fnlwgt' for r in engine.last_review))

    def test_field_specific_overwrite(self):
        self.assertTrue(RepairEngine.overwrite_candidate(dict(self.row,age=999.),'age'))
        self.assertFalse(RepairEngine.overwrite_candidate(dict(self.row,capital_gain=999.),'capital_gain'))
        self.assertFalse(RepairEngine.overwrite_candidate(dict(self.row,fnlwgt=999.),'fnlwgt'))

    def test_all_legal_positive_capital_values_preserved(self):
        raw=R.load_adult()
        for c in ['capital_gain','capital_loss']:
            values=sorted({r[c] for r in raw if r[c] is not None and r[c]>0}|{999.,114.})
            rows=[dict(self.row,**{c:v}) for v in values];fixed,_,_=self.engine(overwrite='E').repair(rows)
            self.assertEqual([r[c] for r in fixed],values)

    def test_unit_and_outlier_cells_unchanged(self):
        rows=[dict(self.row,age=self.row['age']*1000),dict(self.row,capital_loss=3000.1),dict(self.row,age=123.4)]
        expected,ee,_=Cleaner(self.ref).repair(rows);actual,ev,_=self.engine({'age':'D'},'E').repair(rows)
        for i in range(len(rows)):
            for c in FEATURES:self.assertEqual(actual[i][c],expected[i][c])
        unit=lambda e:[x for x in e if x['action']=='unit_inverse' or x['action'].startswith('outlier_')]
        self.assertEqual(unit(ev),unit(ee))

    def test_existing_audit_chain_rolls_back(self):
        row=dict(self.row,sex='MALE',relationship='Wife')
        fixed,events,_=self.engine().repair([row])
        self.assertGreaterEqual(len([e for e in events if e['col']=='sex']),2)
        self.assertTrue(A.verify([row],A.rollback(fixed,events),R.COLS)['identical'])

    def test_new_actions_do_not_duplicate_protected_actions(self):
        row=dict(self.row,age=self.row['age']*1000,fnlwgt=99999999.,occupation=None)
        _,events,_=self.engine({'occupation':'D'},'C').repair([row])
        old={(e['row'],e['col']) for e in events if e['action']=='unit_inverse' or e['action'].startswith('outlier_')}
        new={(e['row'],e['col']) for e in events if e['action'].startswith('v32_')}
        self.assertFalse(old&new)

    def test_frozen_reference_not_target_batch(self):
        row=dict(self.row,age=None);engine=self.engine({'age':'B'})
        a=engine.repair([row])[0][0]
        b=engine.repair([row]+[dict(self.row,age=999.)]*20)[0][0]
        self.assertEqual(a,b)

    def test_sparse_conditional_falls_back(self):
        row=dict(self.row,education=None,marital_status=None)
        candidate=self.bank.statistic(row,'age',True)
        self.assertEqual(candidate['source'],'global')
        self.assertGreaterEqual(candidate['n'],100)

    def test_knn_neighbors_supported(self):
        self.assertEqual(set(self.bank.knn),{3,5,11})
        row=dict(self.row,age=None)
        for method in ['K3','K5','K11']:
            value=self.bank.predict([row],'age',method)[0]
            self.assertTrue(17<=value<=90)

    def test_predictor_does_not_depend_on_input_income(self):
        a=self.bank.predict([dict(self.row,age=None,income='>50K')],'age','D')
        b=self.bank.predict([dict(self.row,age=None,income='<=50K')],'age','D')
        self.assertEqual(a,b)

    def test_development_validation_never_old_test(self):
        usage=json.loads((ROOT/'history_usage.json').read_text());raw=R.load_adult()
        old={tuple(raw[i][c] for c in FEATURES) for i in usage['historical_test_ids']}
        for seed in CFG['seeds']:
            ids=json.loads((ROOT/f'data/development_split_{seed}.json').read_text())['raw_ids']
            for name in ['repair_validation','classifier_validation']:
                self.assertFalse(old&{tuple(raw[i][c] for c in FEATURES) for i in ids[name]})

    def test_external_manifest_sufficient_and_blind(self):
        m=json.loads((ROOT/'data/data_manifest.json').read_text())
        self.assertGreaterEqual(m['external_eligible'],8000)
        self.assertEqual(m['test_groups'],5)
        self.assertFalse(m['sealed_label_tokens_inspected_for_statistics'])


if __name__=='__main__':unittest.main(verbosity=2)
