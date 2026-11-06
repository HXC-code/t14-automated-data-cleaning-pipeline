import csv,json,tempfile,unittest,inspect
from pathlib import Path
from copy import deepcopy
from src.paths import FINAL,FEATURES,CONFIG,sha,load_json
from src.runtime import FrozenCleaner,verify_candidate,frozen_audit,nested_cv
from src.csvio import read_input,write_features
from src.auditio import enrich,forward,rollback,deduplicate,signature
from run_pipeline import run,manual_decisions


class FinalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cleaner=FrozenCleaner();cls.row=deepcopy(cls.cleaner.reference[0])

    def test_frozen_J_matches_source_hashes(self):verify_candidate()

    def test_utf8_metadata_does_not_depend_on_Windows_locale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'metadata.json';expected={'path':'数据工程/独立特征.csv'}
            path.write_text(json.dumps(expected,ensure_ascii=False),encoding='utf-8')
            self.assertEqual(load_json(path),expected)

    def test_one_shot_scoring_claim_rejects_second_session(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('score_guard_fixture',FINAL/'tools/score_once.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'claimed.json';module.claim(marker,'synthetic-manifest-hash')
            with self.assertRaises(FileExistsError):module.claim(marker,'synthetic-manifest-hash')

    def test_acceptance_uses_only_three_mean_targets(self):
        self.assertEqual(CONFIG['acceptance']['mean_gain_pp_each_rate'],3.)
        self.assertFalse(CONFIG['acceptance']['CI_requirement'])

    def test_classifier_budget_and_threshold_unchanged(self):
        for name in ['C_grid','class_weight_grid','max_iter','tol','threshold']:
            self.assertEqual(CONFIG[name],nested_cv.CONFIG[name])

    def test_repair_does_not_accept_truth(self):
        self.assertEqual(list(inspect.signature(FrozenCleaner.repair).parameters),['self','rows','version'])

    def test_income_cannot_change_output(self):
        row=dict(self.row,age=None)
        a=self.cleaner.repair([dict(row,income='private-a')]);b=self.cleaner.repair([dict(row,income='private-b')])
        self.assertEqual(a['rows'],b['rows']);self.assertNotIn('income',a['rows'][0])

    def test_categorical_missing_and_numeric_missing_stay_missing(self):
        r=self.cleaner.repair([dict(self.row,age=None,occupation=None,workclass=None,native_country=None)])['rows'][0]
        for c in ['age','occupation','workclass','native_country']:self.assertIsNone(r[c]);self.assertEqual(r['__missing_'+c],1.)

    def test_fnlwgt_overwrite_reviewed(self):
        r=self.cleaner.repair([dict(self.row,fnlwgt=99999999.)])
        self.assertEqual(r['rows'][0]['fnlwgt'],99999999.);self.assertTrue(any(q['col']=='fnlwgt' for q in r['review']))

    def test_legal_capital_tail_survives(self):
        for value in [114.,999.,99999.]:self.assertEqual(self.cleaner.repair([dict(self.row,capital_gain=value)])['rows'][0]['capital_gain'],value)

    def test_role_is_not_absolute_sex_constraint(self):
        r=self.cleaner.repair([dict(self.row,sex='Male',relationship='Wife',marital_status='Married-civ-spouse')])
        self.assertEqual(r['rows'][0]['sex'],'Male');self.assertTrue(r['semantic_cases'])

    def test_education_mapping_kept(self):
        r=self.cleaner.repair([dict(self.row,education='HS-grad',education_num=99.)])
        self.assertEqual(r['rows'][0]['education_num'],9.)

    def test_unit_module_kept(self):
        row=dict(self.row,age=self.row['age']*1000)
        self.assertEqual(self.cleaner.repair([row])['rows'][0]['age'],self.row['age'])

    def test_audit_has_required_fields(self):
        observed=[dict(self.row,age=None)];r=self.cleaner.repair(observed);events=enrich(r['audit'],['test-0'],'test-run')
        for e in events:
            for key in ['record_id','field','original_value','modified_value','reason','rule','operation_time','operation_result']:self.assertIn(key,e)

    def test_consecutive_deletions_restore_all_rows(self):
        observed=[deepcopy(self.row) for _ in range(3)];r=self.cleaner.repair(observed);events=deepcopy(r['audit'])
        kept,ids=deduplicate(r['rows'],events,['a','b','c']);disk=enrich(events,['a','b','c'],'delete')
        self.assertEqual(len(kept),1);self.assertEqual(forward(observed,disk),kept);self.assertEqual(rollback(kept,disk),observed)

    def test_modify_then_delete_reverse_order(self):
        observed=[dict(self.row,age=35000.),dict(self.row,age=35000.)];r=self.cleaner.repair(observed);events=deepcopy(r['audit'])
        kept,_=deduplicate(r['rows'],events,['a','b']);events=enrich(events,['a','b'],'sequence')
        self.assertEqual(rollback(kept,events),observed)

    def test_multiple_cell_events_same_field_ordered(self):
        observed=[dict(self.row,sex='MALE')]
        events=[frozen_audit.marker_event(observed),dict(op='cell_fix',row=0,col='sex',before='MALE',after='Male',action='format'),dict(op='cell_fix',row=0,col='sex',before='Male',after='Female',action='explicit_synthetic_review')]
        fixed=forward(observed,events);self.assertEqual(fixed[0]['sex'],'Female');self.assertEqual(rollback(fixed,events),observed)

    def test_explicit_human_decision_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'decisions.csv';p.write_text('record_id,field,decision,new_value,reason\na,age,approve,45,explicit fixture decision\n',encoding='utf-8')
            observed=[dict(self.row,age=None)];r=self.cleaner.repair(observed);events=deepcopy(r['audit']);fixed=deepcopy(r['rows'])
            resolved,count=manual_decisions(fixed,['a'],events,p)
            self.assertEqual(count,1);self.assertIn((0,'age'),resolved);self.assertEqual(rollback(fixed,events),observed)

    def test_input_label_not_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.csv'
            with p.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=FEATURES+['income']);w.writeheader();w.writerow(dict(self.row,income='never-export'))
            _,rows=read_input(p);self.assertNotIn('income',rows[0])

    def test_header_csv_retains_whitespace_until_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.csv';write_features(p,['a'],[dict(self.row,workclass=' Private')],False)
            _,rows=read_input(p);self.assertEqual(rows[0]['workclass'],' Private')
            r=self.cleaner.repair(rows);self.assertTrue(any(e['col']=='workclass' and e['before']==' Private' for e in r['events']))

    def test_invalid_schema_fails_without_editing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.csv';write_features(p,['a'],[dict(self.row,age='bad')],False);before=sha(p)
            with self.assertRaises(ValueError):read_input(p)
            self.assertEqual(sha(p),before)

    def test_one_command_artifacts_are_real_and_rollback_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.csv';out=root/'out'
            observed=[dict(self.row,age=self.row['age']*1000,fnlwgt=None)]
            write_features(source,['a'],observed,False);result=run(source,out)
            self.assertGreaterEqual(result['automatic_modified_cells'],1);self.assertTrue(result['rollback']['identical'])
            for filename in ['cleaned.csv','review.csv','audit.jsonl','repair_report.md','repair_report.json','detected_cells.csv','rolled_back.csv']:self.assertTrue((out/filename).exists())
            _,back=read_input(out/'rolled_back.csv');self.assertEqual(back,observed)
            with self.assertRaises(FileExistsError):run(source,out)


if __name__=='__main__':unittest.main(verbosity=2)
