"""Audit both cell changes and no-change decisions, including marker metadata."""
from copy import deepcopy
from common import FEATURES,full_signature,A,digest


def marker_event(rows):
    return dict(op='missing_indicators',action='preserve_original_missing_state',columns=FEATURES,
                missing_cells=[[i,c] for i,r in enumerate(rows) for c in FEATURES if r[c] is None],
                existing={str(i):{k:v for k,v in r.items() if k.startswith('__missing_')} for i,r in enumerate(rows) if any(k.startswith('__missing_') for k in r)})


def set_markers(rows,event):
    missing={tuple(k) for k in event['missing_cells']}
    for i,r in enumerate(rows):
        before=event['existing'].get(str(i),{})
        for c in event['columns']:r['__missing_'+c]=before.get('__missing_'+c,float((i,c) in missing))


def replay(rows,events):
    out=deepcopy(rows)
    for e in events:
        if e['op']=='missing_indicators':set_markers(out,e)
        elif e['op']=='cell_fix':
            assert out[e['row']][e['col']]==e['before'];out[e['row']][e['col']]=e['after']
        elif e['op']=='review':
            assert out[e['row']][e['col']]==e['before']==e['after']
        elif e['op']=='semantic_case':
            assert all(out[e['row']][c]==v for c,v in e['snapshot'].items())
        else:raise AssertionError('Unexpected audit operation: '+e['op'])
    return out


def rollback(rows,events):
    out=deepcopy(rows)
    for e in reversed(events):
        if e['op']=='cell_fix':
            assert out[e['row']][e['col']]==e['after'];out[e['row']][e['col']]=e['before']
        elif e['op']=='missing_indicators':
            for i,r in enumerate(out):
                for c in e['columns']:r.pop('__missing_'+c,None)
                r.update(e['existing'].get(str(i),{}))
    return out


def persist(path,dirty,result):
    A.write_log(result['audit'],path);events=A.read_log(path)
    assert replay(dirty,events)==result['rows']
    restored=rollback(result['rows'],events);assert restored==dirty
    source_ids=[e['source_seq'] for e in events if e.get('source_seq') is not None]
    assert len(source_ids)==len(set(source_ids))
    return dict(file=path.name,events=len(events),cell_fixes=sum(e['op']=='cell_fix' for e in events),reviews=sum(e['op']=='review' for e in events),
                original_sha256=full_signature(dirty),rollback_sha256=full_signature(restored),identical=True,
                audit_sha256=digest(path),metadata_restored=True,duplicate_source_events=0)
