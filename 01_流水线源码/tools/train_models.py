"""Equal-budget final classifiers; never opens final-test labels or features."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import sys,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import joblib
from sklearn.model_selection import StratifiedKFold
from src.paths import *
from src.runtime import FrozenCleaner,inject,nested_cv,verify_candidate,CORE
from src.development import load


def main():
    verify_candidate();assert json.loads((FINAL/'reports/independence_audit.json').read_text())['passed']
    marker=PRIVATE/'training_started.json'
    with marker.open('x',encoding='utf-8') as f:json.dump(dict(start_utc=now(),protocol_sha256=sha(FINAL/'config/final_protocol.json')),f)
    trials=[];choices=[];models=[];protection=[];bank_records=[]
    for seed in CONFIG['seeds']:
        data=load(seed);labels=np.asarray(data['y']);ref=data['reference'];bank=joblib.load(FINAL/f'reference/bank_{seed}.joblib')
        assert bank.ref==ref
        missing=json.loads((CORE/'baseline_selection.json').read_text())['missing_methods'][str(seed)]
        for c,method in missing.items():
            if method=='D':bank.fit_model(c)
        bank_path=PRIVATE/f'data/fitted_bank_{seed}.joblib';joblib.dump(bank,bank_path,compress=3)
        bank_records.append(dict(seed=seed,file=str(bank_path.relative_to(PRIVATE)),sha256=sha(bank_path),ref_rows=3400,predictors_exclude_income=True))
        inner=[dict(train_positions=t.tolist(),validation_positions=v.tolist()) for t,v in StratifiedKFold(3,shuffle=True,random_state=seed+10000).split(np.arange(4400),labels)]
        save(FINAL/f'reports/training_split_{seed}.json',dict(seed=seed,raw_ids=data['raw_ids'],reference_ids=data['reference_ids'],inner=inner))
        for rate in CONFIG['rates']:
            observed1,_=inject(data['fit'],ref,rate,seed);observed2,_=inject(data['validation'],ref,rate,seed+300);observed=observed1+observed2
            cleaner=FrozenCleaner(seed,rate,bank,observed)
            results={v:cleaner.repair(observed,v) for v in ['V2','V3','V3.1','A_V3.2','J']}
            frames=dict(original=data['fit']+data['validation'],raw=observed,**{k:r['rows'] for k,r in results.items()})
            old=joblib.load(WORK/f'V3.3/stage3/inputs/cv_data_{seed}_{rate}.joblib')
            assert frames['raw']==old['frames']['raw'] and frames['J']==old['frames']['J'] and labels.tolist()==old['labels']
            protected=lambda events:{(e['row'],e['col'],e['before'],e['after'],e['action']) for e in events if e['action'] in ['unit_inverse','reliable_dependency','category_canonicalization'] or e['action'].startswith('outlier_')}
            assert protected(results['J']['events'])==protected(results['A_V3.2']['events'])
            protection.append(dict(seed=seed,rate=rate,phase3_training_J_exact=True,unit_outlier_FD_canonical_events_equal=True,external_labels_used=False))
            joblib.dump(dict(seed=seed,rate=rate,frames=frames,y=labels,raw_ids=data['raw_ids']),PRIVATE/f'data/training_{seed}_{rate}.joblib',compress=3)
            for version in CONFIG['versions']:
                frame=frames[version];winner,tt=nested_cv.select_parameters(frame,labels,inner)
                trials.extend(dict(seed=seed,rate=rate,version=version,**t) for t in tt)
                enc=nested_cv.encoder();x=enc.fit_transform(nested_cv.arrays(frame));model,info=nested_cv.model_fit(x,labels,winner['C'],winner['class_weight'])
                path=PRIVATE/f'models/{seed}_{int(rate*100)}_{version}.joblib';assert not path.exists();joblib.dump((enc,model,False),path,compress=3)
                models.append(dict(seed=seed,rate=rate,version=version,file=str(path.relative_to(PRIVATE)),sha256=sha(path)))
                choices.append(dict(seed=seed,rate=rate,version=version,C=winner['C'],class_weight=str(winner['class_weight']),inner_mean_f1=winner['inner_mean_f1'],**info))
            csvsave(FINAL/'reports/training_inner_trials.csv',trials);csvsave(FINAL/'reports/training_model_choices.csv',choices)
            csvsave(FINAL/'reports/training_protection_checks.csv',protection)
            print(json.dumps(dict(seed=seed,rate=rate,trained_versions=len(CONFIG['versions']),selected_without_test=True)),flush=True)
    assert len(models)==105 and len(trials)==1890
    csvsave(FINAL/'reports/training_bank_manifest.csv',bank_records)
    manifest=dict(time_utc=now(),models=models,banks=bank_records,inner_fits=len(trials),final_fits=len(models),external_labels_used=False,
                  candidate_freeze_sha256=sha(FINAL/'config/candidate_freeze.json'),protocol_sha256=sha(FINAL/'config/final_protocol.json'),
                  training_code_sha256=sha(Path(__file__)))
    with (FINAL/'config/model_freeze.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    save(PRIVATE/'training_completed.json',dict(time_utc=now(),models=105,inner_fits=1890,external_labels_opened=False))
    print('ALL MODELS FROZEN; independent test labels remain unopened',flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        save(PRIVATE/'training_failed.json',dict(time_utc=now(),traceback=traceback.format_exc()));raise
