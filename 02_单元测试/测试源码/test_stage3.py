import inspect,unittest
from copy import deepcopy
import numpy as np
from sklearn.model_selection import StratifiedKFold
from common import *
from policies import PolicyReplay,inference_features,fnlwgt_target
from audit import marker_event,set_markers,replay,rollback
from nested_cv import encoder,select_parameters
from quality import quality


class Stage3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=parts(20260601);cls.reference=inference_features(cls.p['reference']);cls.bank=CandidateBank(cls.reference,20260601)
        cls.parent=Cleaner(cls.reference);cls.row=dict(cls.reference[0])

    def event(self,c,b,a,action):return dict(op='cell_fix',row=0,col=c,before=b,after=a,action=action)

    def engine(self,row,events,bank=None):return PolicyReplay([row],events,{(0,e['col']) for e in events},[],self.parent,bank or self.bank)

    def test_inference_discards_income(self):
        a=inference_features([dict(self.row,income='>50K')]);b=inference_features([dict(self.row,income='<=50K')])
        self.assertEqual(a,b);self.assertNotIn('income',a[0])

    def test_no_truth_in_inference_signature(self):
        self.assertNotIn('truth',inspect.signature(PolicyReplay).parameters)
        self.assertEqual(list(inspect.signature(PolicyReplay.apply).parameters),['self','policy'])

    def test_A_preserves_all_source_actions(self):
        row=dict(self.row,age=None,fnlwgt=None)
        events=[self.event('age',None,35.,'global_missing'),self.event('fnlwgt',None,123456.5,'global_missing')]
        result=self.engine(row,events).apply('A')
        self.assertEqual(len(result['events']),2);self.assertEqual(result['rows'][0]['fnlwgt'],123456.5)

    def test_B_preserves_numeric_missing(self):
        row=dict(self.row,age=None);r=self.engine(row,[self.event('age',None,35.,'global_missing')]).apply('B')
        self.assertIsNone(r['rows'][0]['age']);self.assertEqual(r['rows'][0]['__missing_age'],1.)

    def test_B_preserves_categorical_missing(self):
        row=dict(self.row,occupation=None);r=self.engine(row,[self.event('occupation',None,'Sales','conditional_mode')]).apply('B')
        self.assertIsNone(r['rows'][0]['occupation']);self.assertEqual(r['rows'][0]['__missing_occupation'],1.)

    def test_B_keeps_cover_repair(self):
        row=dict(self.row,age=999.);r=self.engine(row,[self.event('age',999.,35.,'v32_overwrite_G')]).apply('B')
        self.assertEqual(r['rows'][0]['age'],35.)

    def test_H_rejects_fractional_estimate(self):
        row=dict(self.row,fnlwgt=None);r=self.engine(row,[self.event('fnlwgt',None,123456.5,'global_missing')]).apply('H')
        self.assertIsNone(r['rows'][0]['fnlwgt']);self.assertEqual(len(r['withheld']),1)

    def test_H_rejects_legal_but_unsupported_integer(self):
        row=dict(self.row,fnlwgt=99999999.);r=self.engine(row,[self.event('fnlwgt',99999999.,123456.,'v32_overwrite_G')]).apply('H')
        self.assertEqual(r['rows'][0]['fnlwgt'],99999999.)

    def test_H_covers_old_invalid_range(self):
        row=dict(self.row,fnlwgt=1038553000.);r=self.engine(row,[self.event('fnlwgt',1038553000.,210371.5,'conditional_invalid_range')]).apply('H')
        self.assertEqual(r['rows'][0]['fnlwgt'],1038553000.)

    def test_H_does_not_round(self):
        row=dict(self.row,fnlwgt=None);r=self.engine(row,[self.event('fnlwgt',None,123456.5,'global_missing')]).apply('H')
        self.assertFalse(r['events']);self.assertFalse(r['withheld'][0]['evidence']['integer_and_range_valid'])

    def test_H_allows_supported_integer_candidate(self):
        class EvidenceBank:
            def __init__(self,base):self.__dict__.update(base.__dict__);self.base=base
            def reliable(self,c,v):return self.base.reliable(c,v)
            def statistic(self,row,c,conditional=True):return dict(value=150000.,lower_bound=.95,n=100,source='conditional' if conditional else 'global')
        row=dict(self.row,fnlwgt=None);r=self.engine(row,[self.event('fnlwgt',None,150000.,'global_missing')],EvidenceBank(self.bank)).apply('H')
        self.assertEqual(r['rows'][0]['fnlwgt'],150000.);self.assertFalse(r['events'][0]['strict_restoration_claim'])

    def test_H_keeps_explicit_outlier_module(self):
        row=dict(self.row,fnlwgt=3000.1);e=self.event('fnlwgt',3000.1,150000.,'outlier_global')
        self.assertFalse(fnlwgt_target(e));self.assertEqual(self.engine(row,[e]).apply('H')['rows'][0]['fnlwgt'],150000.)

    def test_I_rejects_role_as_absolute_sex_constraint(self):
        row=dict(self.row,sex='Male',relationship='Wife',marital_status='Married-civ-spouse')
        r=self.engine(row,[self.event('sex','Male','Female','reliable_logic')]).apply('I')
        self.assertEqual(r['rows'][0]['sex'],'Male');self.assertTrue(r['semantic_cases'])

    def test_I_keeps_unique_format_normalization(self):
        row=dict(self.row,sex=' FEMALE ',relationship='Husband',marital_status='Married-civ-spouse')
        es=[self.event('sex',' FEMALE ','Female','category_canonicalization'),self.event('sex','Female','Male','reliable_logic')]
        r=self.engine(row,es).apply('I');self.assertEqual(r['rows'][0]['sex'],'Female')
        self.assertIn((0,'sex'),{(x['row'],x['col']) for x in r['review']})

    def test_I_reviews_role_marital_conflict(self):
        row=dict(self.row,sex='Male',relationship='Husband',marital_status='Divorced');r=self.engine(row,[]).apply('I')
        self.assertEqual(r['rows'][0]['marital_status'],'Divorced')
        self.assertIn('role_marital_status_direction_unknown',r['semantic_cases'][0]['reasons'])

    def test_I_unknown_semantics_remain_unknown(self):
        row=dict(self.row,sex=None,relationship='Husband',marital_status=None);r=self.engine(row,[]).apply('I')
        self.assertIsNone(r['rows'][0]['sex']);self.assertIsNone(r['rows'][0]['marital_status'])

    def test_I_invalidates_model_using_withdrawn_sex(self):
        row=dict(self.row,age=None,sex='Male',relationship='Wife',marital_status='Married-civ-spouse')
        es=[self.event('sex','Male','Female','reliable_logic'),self.event('age',None,35.,'v32_missing_D')]
        r=self.engine(row,es).apply('I');self.assertIsNone(r['rows'][0]['age'])
        self.assertIn('upstream_dependency_withdrawn',r['withheld'][1]['reasons'])

    def test_J_coalesces_overlapping_rejection(self):
        row=dict(self.row,fnlwgt=None);r=self.engine(row,[self.event('fnlwgt',None,123456.5,'global_missing')]).apply('J')
        source=[e for e in r['audit'] if e.get('source_seq')==1]
        self.assertEqual(len(source),1);self.assertEqual(len(source[0]['reasons']),2)

    def test_reliable_education_mapping_preserved(self):
        for policy in CONFIG['policies']:
            row=dict(self.row,education='HS-grad',education_num=None)
            r=self.engine(row,[self.event('education_num',None,9.,'reliable_dependency')]).apply(policy)
            self.assertEqual(r['rows'][0]['education_num'],9.)

    def test_unit_and_capital_outliers_preserved_all_policies(self):
        row=dict(self.row,age=35000.,capital_loss=3000.1)
        es=[self.event('age',35000.,35.,'unit_inverse'),self.event('capital_loss',3000.1,0.,'outlier_global')]
        for policy in CONFIG['policies']:
            r=self.engine(row,es).apply(policy)
            self.assertEqual(r['rows'][0]['age'],35.);self.assertEqual(r['rows'][0]['capital_loss'],0.)

    def test_legal_low_capital_gains_not_zeroed(self):
        for value in [114.,999.,99999.]:
            row=dict(self.row,capital_gain=value)
            for policy in CONFIG['policies']:self.assertEqual(self.engine(row,[]).apply(policy)['rows'][0]['capital_gain'],value)

    def test_full_audit_forward_and_backward(self):
        row=dict(self.row,sex='MALE',relationship='Wife',age=None)
        es=[self.event('sex','MALE','Male','category_canonicalization'),self.event('sex','Male','Female','reliable_logic'),self.event('age',None,35.,'global_missing')]
        for policy in CONFIG['policies']:
            r=self.engine(row,es).apply(policy)
            self.assertEqual(replay([row],r['audit']),r['rows']);self.assertEqual(rollback(r['rows'],r['audit']),[row])

    def test_existing_missing_metadata_survives_rollback(self):
        row=dict(self.row,__missing_age=1.);r=self.engine(row,[]).apply('J')
        self.assertEqual(r['rows'][0]['__missing_age'],1.);self.assertEqual(rollback(r['rows'],r['audit']),[row])

    def test_quality_rejects_plausible_estimate_as_exact(self):
        clean=dict(self.row,fnlwgt=111111.);row=dict(self.row,fnlwgt=None)
        r=self.engine(row,[self.event('fnlwgt',None,150000.,'global_missing')]).apply('A')
        q=quality([clean],[row],r,{(0,'fnlwgt'):'missing'},self.bank)
        self.assertEqual(q['reasonable_only'],1);self.assertEqual(q['strict_modified'],0);self.assertEqual(q['wrong_modified'],1)

    def test_preserved_missing_not_restored_by_classifier(self):
        clean=dict(self.row,age=35.);row=dict(self.row,age=None)
        r=self.engine(row,[self.event('age',None,35.,'global_missing')]).apply('B')
        q=quality([clean],[row],r,{(0,'age'):'missing'},self.bank)
        self.assertEqual(q['strict_restored'],0);self.assertEqual(q['auto_modified'],0)

    def test_selector_cannot_receive_outer_data(self):
        self.assertEqual(list(inspect.signature(select_parameters).parameters),['train_rows','y_train','inner_splits'])

    def test_scaler_and_encoder_fit_training_only(self):
        fit=[dict(self.row,age=20.),dict(self.row,age=40.)];outer=[dict(self.row,age=999999.,workclass='never_seen_outer')]
        enc=encoder();enc.fit(arrays(fit));enc.transform(arrays(outer))
        scaler=enc.named_transformers_['num'].named_steps['standardscaler']
        self.assertEqual(scaler.mean_[list(R.NUM).index('age')],30.)
        self.assertNotIn('never_seen_outer',set(v for block in enc.named_transformers_['cat'].categories_ for v in block))

    def test_inner_grid_has_equal_eighteen_fits(self):
        original=self.p['downstream_fit'][:90];rows=inference_features(original);y=[int(r['income']=='>50K') for r in original]
        splits=[dict(train_positions=t.tolist(),validation_positions=v.tolist()) for t,v in StratifiedKFold(3,shuffle=True,random_state=20260601).split(rows,y)]
        winner,trials=select_parameters(rows,y,splits)
        self.assertEqual(len(trials),18);self.assertIn(winner['C'],CONFIG['C_grid'])

    def test_candidate_plan_is_predeclared_J(self):
        self.assertEqual(CONFIG['primary_candidate'],'J');self.assertFalse(CONFIG['outer_results_may_tune_rules'])


if __name__=='__main__':unittest.main(verbosity=2)
