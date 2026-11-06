"""Restore feature rows and identifiers using cleaned output plus audit only."""
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.paths import save,load_json,now
from src.csvio import read_input,write_features
from src.auditio import rollback,signature


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cleaned',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-report',type=Path)
    args=p.parse_args();assert not args.output.exists(),'Refuse to overwrite restored data'
    _,fixed=read_input(args.cleaned)
    with args.audit.open(encoding='utf-8') as f:events=[json.loads(line) for line in f if line.strip()]
    restored=rollback(fixed,events);meta=next(e for e in events if e['op']=='missing_indicators');ids=meta['record_order']
    assert len(ids)==len(restored)
    observed_hash=signature(restored)
    if args.expected_report:assert observed_hash==load_json(args.expected_report)['rollback']['original_sha256']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    write_features(args.output,ids,restored,indicators=any(any(k.startswith('__missing_') for k in r) for r in restored))
    save(args.output.with_suffix('.verification.json'),dict(time_utc=now(),restored_rows=len(restored),restored_sha256=observed_hash,original_input_read=False,
                    used_cleaned_and_audit_only=True,expected_hash_match=True if args.expected_report else None,identifiers_restored_from_audit=True))
    print(json.dumps(dict(rows=len(restored),sha256=observed_hash,used_original_input=False)))


if __name__=='__main__':main()
