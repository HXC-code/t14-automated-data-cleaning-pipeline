"""Mechanical reproduction of the already-scored test, never a new acceptance."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import sys,argparse,json,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import joblib
from sklearn.model_selection import StratifiedKFold
from src.paths import *
from src.runtime import FrozenCleaner,inject,nested_cv,verify_candidate,CORE
from protocol import scores


def labels_at(path,wanted):
    result={};i=0
    with Path(path).open('rb') as f:
        for line in f:
            if len(line.split(b','))!=15:continue
            if i in wanted:
                token=line.rsplit(b',',1)[1].strip().rstrip(b'.')
                assert token in [b'<=50K',b'>50K'];result[i]=int(token==b'>50K')
            i+=1
    assert set(result)==set(wanted)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adult-train',type=Path,required=True);p.add_argument('--adult-test',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    assert out!=FINAL and FINAL not in out.parents,'Reproduction/private data must remain outside the public delivery'
    assert all(FINAL not in path.resolve().parents for path in [a.adult_train,a.adult_test])
    verify_candidate();source=load_json(FINAL/'config/dataset_sources.json')
    assert sha(a.adult_train)==source['adult_train_sha256'] and sha(a.adult_test)==source['adult_test_sha256']
    out.mkdir(parents=True,exist_ok=False)
    save(out/'REPRODUCTION_ONLY.json',dict(time_utc=now(),notice='Previously scored known test records. Mechanical reproduction only; not fresh independence or new acceptance.',protocol_sha256=sha(FINAL/'config/final_protocol.json')))
    _,training=feature_rows(a.adult_train,uci=True);_,external=feature_rows(a.adult_test,uci=True)
    splits={seed:load_json(CORE/f'data/development_split_{seed}.json')['raw_ids'] for seed in CONFIG['seeds']}
    wanted={i for split in splits.values() for name in ['downstream_fit','classifier_validation'] for i in split[name]}
    training_labels=labels_at(a.adult_train,wanted)
    with (FINAL/'reports/independent_test_assignment.csv').open(encoding='utf-8-sig') as f:assign=list(csv.DictReader(f))
    predictions=[];model_choices=[]
    for seed in CONFIG['seeds']:
        split=splits[seed];fit=[training[i] for i in split['downstream_fit']];val=[training[i] for i in split['classifier_validation']]
        ids=split['downstream_fit']+split['classifier_validation'];y=np.asarray([training_labels[i] for i in ids]);ref=[training[i] for i in split['reference']]
        bank=joblib.load(FINAL/f'reference/bank_{seed}.joblib');assert bank.ref==ref
        missing=load_json(CORE/'baseline_selection.json')['missing_methods'][str(seed)]
        for c,method in missing.items():
            if method=='D':bank.fit_model(c)
        inner=[dict(train_positions=t.tolist(),validation_positions=v.tolist()) for t,v in StratifiedKFold(3,shuffle=True,random_state=seed+10000).split(np.arange(4400),y)]
        group=sorted([r for r in assign if int(r['seed'])==seed],key=lambda r:int(r['position']));test_ids=[int(r['source_row_id']) for r in group]
        clean=[external[i] for i in test_ids]
        assert len(test_ids)==1600 and all(feature_hash(r)==g['feature_sha256'] for r,g in zip(clean,group))
        for rate in CONFIG['rates']:
            d1,_=inject(fit,ref,rate,seed);d2,_=inject(val,ref,rate,seed+300);dirty=d1+d2;test_dirty,_=inject(clean,ref,rate,seed+600)
            cleaner=FrozenCleaner(seed,rate,bank,dirty)
            train_frames=dict(original=fit+val,raw=dirty);test_frames=dict(original=clean,raw=test_dirty)
            for version in ['V2','V3','V3.1','A_V3.2','J']:
                train_frames[version]=cleaner.repair(dirty,version)['rows'];test_frames[version]=cleaner.repair(test_dirty,version)['rows']
            for version in CONFIG['versions']:
                best,_=nested_cv.select_parameters(train_frames[version],y,inner);enc=nested_cv.encoder();x=enc.fit_transform(nested_cv.arrays(train_frames[version]));model,info=nested_cv.model_fit(x,y,best['C'],best['class_weight'])
                probability=model.predict_proba(enc.transform(nested_cv.arrays(test_frames[version])))[:,1]
                predictions.append(dict(seed=seed,rate=rate,version=version,ids=test_ids,p=probability))
                model_choices.append(dict(seed=seed,rate=rate,version=version,C=best['C'],weight=str(best['class_weight']),**info))
            print('Reproduced frozen fits, without test labels:',seed,rate,flush=True)
    csvsave(out/'training_choices.csv',model_choices)
    save(out/'predictions_completed_before_labels.json',dict(time_utc=now(),cases=len(predictions)))
    # Only now decode the 8000 test labels, solely to reproduce frozen metrics.
    target=labels_at(a.adult_test,{i for r in predictions for i in r['ids']});runs=[]
    for r in predictions:runs.append(dict(seed=r['seed'],rate=r['rate'],version=r['version'],n=1600,threshold=.5,**scores([target[i] for i in r['ids']],r['p'],.5)))
    csvsave(out/'reproduced_runs.csv',runs)
    with (FINAL/'reports/independent_runs.csv').open(encoding='utf-8-sig') as f:original=list(csv.DictReader(f))
    differences=[]
    for r in runs:
        old=next(x for x in original if int(x['seed'])==r['seed'] and float(x['rate'])==r['rate'] and x['version']==r['version'])
        differences.append(max(abs(r[m]-float(old[m])) for m in ['accuracy','precision','recall','f1','auc']))
    save(out/'reproduction_result.json',dict(time_utc=now(),cases=105,max_metric_difference=max(differences),matches_within_1e_12=max(differences)<=1e-12,
            independent_new_acceptance=False,retuning_performed=False,labels_exported=False))
    print('Mechanical reproduction finished; no independent-new-test claim. Max metric difference:',max(differences))


if __name__=='__main__':main()
