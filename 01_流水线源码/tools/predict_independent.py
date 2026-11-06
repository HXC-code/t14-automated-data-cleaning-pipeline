"""Read fresh feature-only groups and freeze every probability before labels."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import joblib
from src.paths import *
from src.runtime import FrozenCleaner,inject,nested_cv,verify_candidate
from src.csvio import write_features


def main():
    verify_candidate();assert not (PRIVATE/'prediction_freeze.json').exists()
    freeze=json.loads((FINAL/'config/model_freeze.json').read_text())
    assert all(sha(PRIVATE/r['file'])==r['sha256'] for r in freeze['models']+freeze['banks'])
    locations=load_json(PRIVATE/'data/fresh_group_locations.json');files=[];protected=[]
    for seed in CONFIG['seeds']:
        ids,clean=feature_rows(locations[str(seed)]['features']);assert len(clean)==1600
        bank=joblib.load(PRIVATE/f'data/fitted_bank_{seed}.joblib')
        for rate in CONFIG['rates']:
            dirty,truth=inject(clean,bank.ref,rate,seed+600)
            training=joblib.load(PRIVATE/f'data/training_{seed}_{rate}.joblib')
            cleaner=FrozenCleaner(seed,rate,bank,training['frames']['raw'])
            result={v:cleaner.repair(dirty,v) for v in ['V2','V3','V3.1','A_V3.2','J']}
            frames=dict(original=clean,raw=dirty,**{k:r['rows'] for k,r in result.items()})
            signature=lambda events:{(e['row'],e['col'],e['before'],e['after'],e['action']) for e in events if e['action'] in ['unit_inverse','reliable_dependency','category_canonicalization'] or e['action'].startswith('outlier_')}
            assert signature(result['J']['events'])==signature(result['A_V3.2']['events'])
            protected.append(dict(seed=seed,rate=rate,reference_only=True,unit_outlier_FD_canonical_preserved=True,test_rows=1600,labels_opened=False))
            # Private only: clean counterpart / injected truth may be used later for offline quality.
            joblib.dump(dict(seed=seed,rate=rate,ids=ids,clean=clean,dirty=dirty,truth=truth,J=result['J']),PRIVATE/f'data/test_quality_{seed}_{rate}.joblib',compress=3)
            for version in CONFIG['versions']:
                rec=next(r for r in freeze['models'] if r['seed']==seed and r['rate']==rate and r['version']==version)
                enc,model,_=joblib.load(PRIVATE/rec['file']);prob=model.predict_proba(enc.transform(nested_cv.arrays(frames[version])))[:,1]
                path=PRIVATE/f'predictions/{seed}_{int(rate*100)}_{version}.npz';assert not path.exists();np.savez_compressed(path,source_row_ids=np.asarray(ids),probabilities=prob)
                files.append(dict(seed=seed,rate=rate,version=version,file=str(path.relative_to(PRIVATE)),sha256=sha(path),n=1600))
            if seed==CONFIG['demo_seed'] and rate==CONFIG['demo_rate']:
                write_features(FINAL/'examples/independent_dirty.csv',[f'adult.test:{i}' for i in ids],dirty,indicators=False)
            print(json.dumps(dict(seed=seed,rate=rate,predicted=True,labels_opened=False)),flush=True)
    csvsave(FINAL/'reports/independent_protection_checks.csv',protected)
    with (PRIVATE/'prediction_freeze.json').open('x',encoding='utf-8') as f:json.dump(dict(time_utc=now(),files=files,model_freeze_sha256=sha(FINAL/'config/model_freeze.json'),external_labels_opened=False),f,indent=2)
    save(FINAL/'reports/prediction_freeze_summary.json',dict(time_utc=now(),prediction_files=len(files),rows_per_file=1600,unique_test_rows=8000,
              private_prediction_manifest_sha256=sha(PRIVATE/'prediction_freeze.json'),external_labels_opened=False))
    print('ALL INDEPENDENT PREDICTIONS FROZEN; no label file opened')


if __name__=='__main__':main()
