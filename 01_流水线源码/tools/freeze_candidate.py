"""Copy the actual J dependencies byte-for-byte before external evaluation."""
import csv,datetime,hashlib,json,shutil,sys
from pathlib import Path
FINAL=Path(__file__).resolve().parents[1];WORK=FINAL.parent;OLD=WORK/'V3.3'
sys.dont_write_bytecode=True


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not (FINAL/'config/candidate_freeze.json').exists()
    core=FINAL/'frozen/core';files=[]
    for name in ['cleaner.py','baseline_cleaner.py','outlier_guard.py','candidates.py','protocol.py','run_v3.py','test_v3.py','test_v31.py','test_v32.py',
                 'config.json','config_v31.json','baseline_selection.json','history_usage.json']:
        files.append((OLD/name,core/name))
    files.extend((p,core/p.relative_to(OLD)) for p in (OLD/'legacy').rglob('*.py'))
    for name in ['common.py','replay.py','config.json']:files.append((OLD/'stage2'/name,core/'stage2'/name))
    for name in ['common.py','config.json','policies.py','audit.py','nested_cv.py','quality.py','test_stage3.py']:files.append((OLD/'stage3'/name,core/'stage3'/name))
    for seed in range(20260601,20260606):
        files.append((OLD/f'data/development_split_{seed}.json',core/f'data/development_split_{seed}.json'))
        files.append((OLD/f'cache/bank_{seed}.joblib',FINAL/f'reference/bank_{seed}.joblib'))
    files.append((OLD/'data/data_manifest.json',core/'data/data_manifest.json'))
    files.append((OLD/'historical/v31_method_map.json',core/'historical/v31_method_map.json'))
    files.append((WORK/'V3.2/candidates.py',FINAL/'frozen/V3.2/candidates.py'))
    for name in ['cleaner.py','baseline_cleaner.py','outlier_guard.py']:files.append((WORK/'V3.1'/name,FINAL/'frozen/V3.1'/name))
    correspondence=[]
    for source,dest in files:
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);assert sha(source)==sha(dest)
        correspondence.append(dict(source=str(source.relative_to(WORK)),frozen=str(dest.relative_to(FINAL)),sha256=sha(dest)))
    # Original training features only; income bytes are discarded without decoding.
    names=['age','workclass','fnlwgt','education','education_num','marital_status','occupation','relationship','race','sex','capital_gain','capital_loss','hours_per_week','native_country']
    source=OLD/'legacy/data/adult.data'
    with source.open('rb') as f,(FINAL/'test_fixtures/adult_features.csv').open('w',encoding='utf-8',newline='') as out:
        writer=csv.writer(out);writer.writerow(['source_row_id']+names);i=0
        for line in f:
            if not line.strip():continue
            values=[v.strip().rstrip('.') for v in line.rsplit(b',',1)[0].decode('utf-8').split(',')]
            assert len(values)==14;writer.writerow([i]+values);i+=1
    assert i==32561
    # Check the original phase-three freeze and immutable historical sources.
    stage_freeze=json.loads((OLD/'stage3/freeze.json').read_text(encoding='utf-8'))
    assert all(sha(OLD/'stage3'/name)==value for name,value in stage_freeze['files'].items())
    historical=json.loads((OLD/'stage3/inputs/protected_entry.json').read_text(encoding='utf-8'))
    assert all(sha(Path(p))==value for p,value in historical.items())
    manifest=dict(candidate='J',time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_correspondence=correspondence,
                  files={str(p.relative_to(FINAL)):sha(p) for p in [dest for _,dest in files]+[FINAL/'test_fixtures/adult_features.csv',FINAL/'config/final_protocol.json']},
                  final_acceptance='task-book per-noise mean gain >=3 pp only; former prototype CI gate inactive',external_labels_read=False,
                  historical_files_verified=len(historical),original_phase3_freeze_sha256=sha(OLD/'stage3/freeze.json'))
    with (FINAL/'config/candidate_freeze.json').open('x',encoding='utf-8') as out:json.dump(manifest,out,ensure_ascii=False,indent=2)
    print('J source and parameter snapshot frozen:',len(files),'files; no external label opened')


if __name__=='__main__':main()
