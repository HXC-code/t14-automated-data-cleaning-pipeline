"""Single independent-label read, after all models and predictions are frozen."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,csv,json,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.paths import *
from src.runtime import verify_candidate
from protocol import scores


def claim(marker,prediction_freeze_sha):
    with Path(marker).open('x',encoding='utf-8') as f:
        json.dump(dict(start_utc=now(),prediction_freeze_sha256=prediction_freeze_sha,purpose='One frozen independent scoring session; no retuning'),f,indent=2)


def main():
    verify_candidate();execution=load_json(FINAL/'config/execution_freeze.json')
    assert all(sha(FINAL/name)==value for name,value in execution['files'].items()),'Frozen execution source changed'
    tests=load_json(FINAL/'reports/test_results.json');assert tests['success'] and tests['skipped']==0
    freeze=load_json(PRIVATE/'prediction_freeze.json');model_freeze=load_json(FINAL/'config/model_freeze.json')
    assert all(sha(PRIVATE/r['file'])==r['sha256'] for r in freeze['files'])
    assert all(sha(PRIVATE/r['file'])==r['sha256'] for r in model_freeze['models']+model_freeze['banks'])
    claim(PRIVATE/'evaluation_started.json',sha(PRIVATE/'prediction_freeze.json'))
    locations=load_json(PRIVATE/'data/fresh_group_locations.json');labelmaps={};label_checks=[]
    # This is the only reader of real final income tokens in the release.
    for seed in CONFIG['seeds']:
        location=locations[str(seed)];path=Path(location['labels'])
        assert sha(path)==location['expected_labels_sha256']
        mapping={}
        with path.open(encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                token=row['original_label_token'].strip().rstrip('.')
                assert token in ['<=50K','>50K'];mapping[int(row['source_row_id'])]=int(token=='>50K')
        assert len(mapping)==1600;labelmaps[seed]=mapping
        label_checks.append(dict(seed=seed,n=1600,source_sha256=sha(path),matches_presealed_hash=True))
    runs=[]
    for rec in freeze['files']:
        with np.load(PRIVATE/rec['file']) as saved:
            ids=saved['source_row_ids'];p=saved['probabilities']
        mapping=labelmaps[rec['seed']];assert set(map(int,ids))==set(mapping)
        y=[mapping[int(i)] for i in ids]
        runs.append(dict(seed=rec['seed'],rate=rec['rate'],version=rec['version'],n=len(y),threshold=.5,**scores(y,p,.5)))
    csvsave(FINAL/'reports/independent_runs.csv',runs)
    paired=[];summary=[];baseline=[]
    for rate in CONFIG['rates']:
        for seed in CONFIG['seeds']:
            get=lambda v:next(r for r in runs if r['seed']==seed and r['rate']==rate and r['version']==v)
            raw=get('raw');j=get('J')
            paired.append(dict(seed=seed,rate=rate,n=1600,**{'raw_'+m:raw[m] for m in ['accuracy','precision','recall','f1','auc']},
                               **{'J_'+m:j[m] for m in ['accuracy','precision','recall','f1','auc']},gain_pp=100*(j['f1']-raw['f1'])))
        group=[r for r in paired if r['rate']==rate];gains=[r['gain_pp'] for r in group]
        row=dict(rate=rate,**{'gain_'+str(r['seed']):r['gain_pp'] for r in group},mean_gain_pp=statistics.mean(gains),sample_sd_pp=statistics.stdev(gains),meets_3pp=statistics.mean(gains)>=3.)
        summary.append(row)
        for version in CONFIG['versions']:
            values=[r for r in runs if r['rate']==rate and r['version']==version]
            delta=[100*(r['f1']-next(x['f1'] for x in runs if x['rate']==rate and x['seed']==r['seed'] and x['version']=='raw')) for r in values]
            br=dict(rate=rate,version=version,mean_gain_pp=statistics.mean(delta),sample_sd_pp=statistics.stdev(delta))
            for metric in ['accuracy','precision','recall','f1','auc']:
                br[metric+'_mean']=statistics.mean(r[metric] for r in values);br[metric+'_sample_sd']=statistics.stdev(r[metric] for r in values)
            baseline.append(br)
    csvsave(FINAL/'reports/五次独立实验结果.csv',paired);csvsave(FINAL/'reports/下游F1验收对比表.csv',summary);csvsave(FINAL/'reports/全部基准同步重测.csv',baseline)
    decision=dict(time_utc=now(),formal_threshold_pp=3.0,three_rates=summary,classification_pass=all(r['meets_3pp'] for r in summary),
                  no_rounding_before_decision=True,old_development_CI_gate_used=False,unique_test_records=8000,nonoverlapping_groups=5,per_group=1600,one_scoring_session=True,
                  label_hash_checks=label_checks,labels_exported=False,truth_exported=False,source_sha256=sha(Path(__file__)))
    save(FINAL/'reports/F1_acceptance_decision.json',decision)
    with (PRIVATE/'evaluation_completed.json').open('x',encoding='utf-8') as f:
        json.dump(dict(end_utc=now(),metrics_sha256=sha(FINAL/'reports/independent_runs.csv'),decision_sha256=sha(FINAL/'reports/F1_acceptance_decision.json'),retuning_forbidden=True),f,indent=2)
    for row in summary:print(json.dumps(row),flush=True)
    print('ONE INDEPENDENT SCORING SESSION COMPLETE; retain all results, do not retune',flush=True)


if __name__=='__main__':main()
