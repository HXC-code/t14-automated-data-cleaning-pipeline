"""Post-score quality/engineering evidence; never tunes or scores classifiers."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,csv
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import joblib
from src.paths import *
from src.runtime import FrozenCleaner,verify_candidate
from src.csvio import write_features,read_input
from src.auditio import signature,forward,rollback
from run_pipeline import run


def quality(data,bank):
    clean=data['clean'];dirty=data['dirty'];r=data['J'];fixed=r['rows'];truth=data['truth'];keys=set(truth)
    changed={(i,c) for i in range(len(dirty)) for c in FEATURES if dirty[i][c]!=fixed[i][c]}
    exact=sum(fixed[i][c]==clean[i][c] for i,c in changed)
    wrong_clean=sum(fixed[i][c]!=clean[i][c] for i,c in changed-keys)
    strict=sum(fixed[i][c]==clean[i][c] for i,c in keys)
    reasonable=sum(fixed[i][c]!=clean[i][c] and bank.reliable(c,fixed[i][c]) for i,c in changed&keys)
    return dict(n=len(clean),injected=len(keys),detected=len(keys&r['flags']),automatic_modified=len(changed),strict_modified=exact,strict_restored=strict,
                reasonable_only=reasonable,wrong_modified=len(changed)-exact,clean_misrepair=wrong_clean,clean_cells=len(clean)*14-len(keys),
                automatic_precision=exact/len(changed) if changed else None,restoration_rate=strict/len(keys),clean_misrepair_rate=wrong_clean/(len(clean)*14-len(keys)),
                manual_review=len(r['review']),semantic_cases=len(r['semantic_cases']))


def verify_run(input_path,out,expected=None):
    info=load_json(out/'repair_report.json');ids,original=read_input(input_path);new_ids,fixed=read_input(out/'cleaned.csv')
    with (out/'audit.jsonl').open(encoding='utf-8') as f:events=[json.loads(line) for line in f if line.strip()]
    assert forward(original,events)==fixed
    restored=rollback(fixed,events);assert restored==original
    assert signature(original)==signature(restored)==info['rollback']['original_sha256']
    if expected is not None:assert fixed==expected
    for e in events:
        for field in ['record_id','field','original_value','modified_value','reason','rule','operation_time','operation_result']:assert field in e
    source=[e['source_seq'] for e in events if e.get('source_seq') is not None];assert len(source)==len(set(source))
    return dict(output=str(out.relative_to(FINAL)),input_rows=len(original),output_rows=len(fixed),auto_modified=info['automatic_modified_cells'],review=info['manual_review_cells'],
                deleted=info['deleted_rows'],original_sha256=signature(original),rollback_sha256=signature(restored),identical=True,event_count=len(events),duplicate_source_events=0,
                full_J_prediction_view_equal=expected is not None,audit_sha256=sha(out/'audit.jsonl'),elapsed_seconds=info['elapsed_seconds'])


def main():
    assert (PRIVATE/'evaluation_completed.json').exists();verify_candidate()
    quality_rows=[];profile_rows=[];type_rows=[];rollbacks=[];locations=[]
    for seed in CONFIG['seeds']:
        for rate in CONFIG['rates']:
            data=joblib.load(PRIVATE/f'data/test_quality_{seed}_{rate}.joblib');cleaner=FrozenCleaner(seed,rate)
            q=quality(data,cleaner.bank);quality_rows.append(dict(seed=seed,rate=rate,**q))
            input_path=PRIVATE/f'data/pipeline_input_{seed}_{rate}.csv'
            write_features(input_path,[f'adult.test:{i}' for i in data['ids']],data['dirty'],False)
            out=FINAL/'outputs/demo' if seed==20260601 and rate==.1 else FINAL/f'outputs/acceptance_{seed}_{int(rate*100)}'
            if not (out/'run_completed.json').exists():run(input_path,out,seed,rate)
            check=verify_run(input_path,out,data['J']['rows']);rollbacks.append(dict(seed=seed,rate=rate,scope='independent features',**check))
            report=load_json(out/'repair_report.json');original=cleaner.profile(data['clean'])
            for state,p in [('original',original),('dirty',report['before']),('J',report['after'])]:
                profile_rows.append(dict(seed=seed,rate=rate,state=state,n=1600,missing_cells=p['missing_cells'],detected_alert_cells=p['detected_cells'],
                                         numeric_type_range_alerts=p['numeric_type_or_range_alerts'],spelling_alerts=p['spelling_alerts'],format_alerts=p['format_alerts'],unknown_category_alerts=p['unknown_category_alerts'],
                                         unit_conversion_proposals=p['unit_conversion_proposals'],cross_field_alert_cells=p['cross_field_alert_cells'],
                                         auto_modified=q['automatic_modified'] if state=='J' else 0,manual_review=q['manual_review'] if state=='J' else 0,
                                         clean_misrepair=q['clean_misrepair'] if state=='J' else 0,strict_restored=q['strict_restored'] if state=='J' else 0,reasonable_only=q['reasonable_only'] if state=='J' else 0))
            for typ in sorted(set(data['truth'].values())):
                keys={k for k,t in data['truth'].items() if t==typ};fixed=data['J']['rows'];changed={k for k in keys if data['dirty'][k[0]][k[1]]!=fixed[k[0]][k[1]]}
                exact=sum(fixed[i][c]==data['clean'][i][c] for i,c in changed)
                type_rows.append(dict(seed=seed,rate=rate,type=typ,injected=len(keys),detected=len(keys&data['J']['flags']),modified=len(changed),strict_restored=exact,
                                      remaining_injected_errors=sum(fixed[i][c]!=data['clean'][i][c] for i,c in keys),
                                      reasonable_only=sum(fixed[i][c]!=data['clean'][i][c] and cleaner.bank.reliable(c,fixed[i][c]) for i,c in changed),wrong_modified=len(changed)-exact))
            locations.append(dict(seed=seed,rate=rate,output=str(out.relative_to(FINAL)),input_rows=1600))
            csvsave(FINAL/'reports/independent_repair_quality.csv',quality_rows);csvsave(FINAL/'reports/修复前后质量统计.csv',profile_rows)
            csvsave(FINAL/'reports/各错误类型修复统计.csv',type_rows);csvsave(FINAL/'reports/rollback_cases.csv',rollbacks)
            print(json.dumps(dict(seed=seed,rate=rate,engineering_and_quality_verified=True)),flush=True)
    # Actual deletion capability run on a labelled-as-synthetic feature fixture;
    # independent F1 records are never deleted.
    cleaner=FrozenCleaner();row=cleaner.reference[0];sample=[dict(row,age=row['age']*1000.) for _ in range(3)]+[dict(row,age=45. if row['age']!=45. else 46.)]
    source=FINAL/'examples/deletion_fixture.csv';write_features(source,['fixture-a','fixture-b','fixture-c','fixture-d'],sample,False)
    out=FINAL/'outputs/deletion_validation';run(source,out,dedup=True);ck=verify_run(source,out);assert ck['deleted']==2
    rollbacks.append(dict(seed=20260601,rate=.1,scope='synthetic deletion capability',**ck))
    source2=FINAL/'examples/review_fixture.csv';write_features(source2,['review-fixture'],[dict(row,age=None)],False)
    decisions=FINAL/'examples/review_decisions_fixture.csv';decisions.write_text('record_id,field,decision,new_value,reason\nreview-fixture,age,approve,45,explicit synthetic review fixture; not independent data\n',encoding='utf-8')
    out2=FINAL/'outputs/review_validation';run(source2,out2,decisions=decisions);ck=verify_run(source2,out2)
    rollbacks.append(dict(seed=20260601,rate=.1,scope='synthetic manual review capability',**ck))
    csvsave(FINAL/'reports/rollback_cases.csv',rollbacks);csvsave(FINAL/'reports/pipeline_runs.csv',locations)
    # Prove the standalone clean environment used exactly the frozen J view.
    _,host=read_input(FINAL/'outputs/demo/cleaned.csv');_,cleanenv=read_input(FINAL/'outputs/clean_environment_run/cleaned.csv');assert host==cleanenv
    assert sha(FINAL/'outputs/demo/cleaned.csv')==sha(FINAL/'outputs/clean_environment_run/cleaned.csv')
    save(FINAL/'reports/engineering_acceptance.json',dict(time_utc=now(),independent_feature_cases=15,rows_per_case=1600,all_frozen_J_views_equal=True,
                rollback_cases=len(rollbacks),all_rollback_pass=True,real_delete_restore_pass=True,deletion_fixture_rows=4,deleted_restored_rows=2,
                human_review_interface_pass=True,review_fixture_not_real_human_validation=True,clean_environment_pipeline_match=True,
                clean_environment_cleaned_sha256=sha(FINAL/'outputs/clean_environment_run/cleaned.csv'),real_test_labels_used_in_pipeline=False))
    # Real timestamped sample, not a fabricated illustration.
    with (FINAL/'outputs/demo/audit.jsonl').open(encoding='utf-8') as f:events=[json.loads(line) for line in f if line.strip()]
    selected=[e for e in events if e['op']=='cell_fix'][:8]+[e for e in events if e['op']=='review'][:4]
    with (FINAL/'reports/audit_log_sample.jsonl').open('w',encoding='utf-8') as f:
        for e in selected:f.write(json.dumps(e,ensure_ascii=False)+'\n')
    print('Quality and all 17 actual persisted rollback cases completed; no classifier re-scored')


if __name__=='__main__':main()
