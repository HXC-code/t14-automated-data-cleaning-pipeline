"""Read-only package integrity and frozen-source verification."""
import sys,csv,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.paths import FINAL,sha,load_json


def main():
    with (FINAL/'SHA256SUMS.csv').open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    bad=[r['file'] for r in records if not (FINAL/r['file']).is_file() or sha(FINAL/r['file'])!=r['sha256']]
    if bad:raise SystemExit('Changed/missing delivery files: '+', '.join(bad[:12]))
    for manifest in ['candidate_freeze.json','execution_freeze.json']:
        frozen=load_json(FINAL/'config'/manifest)
        assert all(sha(FINAL/name)==value for name,value in frozen['files'].items())
    verdict=load_json(FINAL/'reports/final_verdict.json');assert verdict['overall_pass'] is False
    print(json.dumps(dict(files_verified=len(records),frozen_J_unchanged=True,formal_acceptance='NOT PASSED: medium-noise F1 below 3 pp',labels_in_public_package=False),ensure_ascii=True))


if __name__=='__main__':main()
