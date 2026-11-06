"""Timestamped audit and reversible optional end-of-pipeline row deletion."""
from copy import deepcopy
import json,hashlib
from src.paths import now,FEATURES
from src.runtime import frozen_audit


def signature(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def enrich(events,record_ids,run_id):
    out=[]
    for seq,source in enumerate(events,1):
        e=deepcopy(source);row=e.get('row')
        e.update(seq=seq,event_id=run_id+':'+str(seq),run_id=run_id,record_id=record_ids[row] if row is not None else '__dataset__',
                 field=e.get('col',e.get('columns',[])),original_value=e.get('before',e.get('snapshot',e.get('existing'))),
                 modified_value=e.get('after',e.get('snapshot')),reason=e.get('reasons',[e.get('action','audit')]),rule=e.get('action',e['op']),operation_time=now(),
                 operation_result='modified' if e['op']=='cell_fix' else 'deleted' if e['op']=='row_drop' else 'metadata_initialized' if e['op']=='missing_indicators' else 'review_required')
        if e['op']=='missing_indicators':e['record_order']=list(record_ids)
        out.append(e)
    return out


def forward(rows,events):
    data=frozen_audit.replay(rows,[e for e in events if e['op']!='row_drop'])
    drops={e['row']:e for e in events if e['op']=='row_drop'}
    for i,e in drops.items():assert data[i]==e['snapshot']
    return [r for i,r in enumerate(data) if i not in drops]


def rollback(rows,events):
    drops={e['row']:e['snapshot'] for e in events if e['op']=='row_drop'}
    restored=[];position=0
    for i in range(len(rows)+len(drops)):
        if i in drops:restored.append(deepcopy(drops[i]))
        else:restored.append(deepcopy(rows[position]));position+=1
    return frozen_audit.rollback(restored,[e for e in events if e['op']!='row_drop'])


def deduplicate(rows,events,record_ids):
    seen=set();kept=[];ids=[]
    for i,r in enumerate(rows):
        key=tuple(r[c] for c in FEATURES)
        if key in seen:events.append(dict(op='row_drop',row=i,snapshot=deepcopy(r),action='explicit_duplicate_removal'))
        else:seen.add(key);kept.append(r);ids.append(record_ids[i])
    return kept,ids
