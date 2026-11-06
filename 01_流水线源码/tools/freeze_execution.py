"""Final code/model/protocol freeze before the first independent label read."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.paths import *


def main():
    assert not (PRIVATE/'evaluation_started.json').exists()
    assert load_json(FINAL/'reports/test_results.json')['success']
    assert load_json(FINAL/'reports/independence_audit.json')['passed']
    assert (PRIVATE/'prediction_freeze.json').exists()
    paths=[]
    for directory in ['src','frozen','config','reference','tests','tools']:
        paths.extend(p for p in (FINAL/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='execution_freeze.json')
    paths.extend(FINAL/name for name in ['run_pipeline.py','run_tests.py','requirements.txt','requirements-lock.txt'])
    manifest=dict(time_utc=now(),files={str(p.relative_to(FINAL)):sha(p) for p in paths},
                  model_freeze_sha256=sha(FINAL/'config/model_freeze.json'),prediction_freeze_sha256=sha(PRIVATE/'prediction_freeze.json'),
                  candidate_policy='J exactly as phase3',test_labels_opened=False,acceptance='three per-noise means >=3 pp; no extra CI condition')
    with (FINAL/'config/execution_freeze.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    print('Final execution frozen before test labels:',len(paths),'files')


if __name__=='__main__':main()
