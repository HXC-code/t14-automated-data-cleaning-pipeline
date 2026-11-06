import csv,math
from pathlib import Path
from src.paths import FEATURES,NUM


def read_input(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:records=list(csv.reader(f))
    records=[r for r in records if any(v for v in r)]
    if not records:raise ValueError('Input has no records')
    header=all(c in records[0] for c in FEATURES)
    names=records.pop(0) if header else FEATURES+(['income'] if len(records[0])==15 else [])
    if not set(FEATURES)<=set(names):raise ValueError('Adult 14-predictor schema is required')
    out=[];ids=[]
    for line,values in enumerate(records,2 if header else 1):
        if len(values)!=len(names):raise ValueError('Column count mismatch at line '+str(line))
        raw=dict(zip(names,values));r={}
        for c in FEATURES:
            v=raw[c] if header else raw[c].strip()
            if v.strip() in ['','?']:r[c]=None
            elif c in NUM:
                try:r[c]=float(v)
                except ValueError:raise ValueError(f'Non-numeric {c} at line {line}; input was not modified')
                if not math.isfinite(r[c]):raise ValueError(f'Non-finite {c} at line {line}')
            else:r[c]=v
        for c in FEATURES:
            key='__missing_'+c
            if key in raw:r[key]=float(raw[key])
        ids.append(str(raw.get('record_id',raw.get('source_row_id','row-'+str(len(out))))));out.append(r)
    if len(set(ids))!=len(ids):raise ValueError('Record identifiers must be unique')
    return ids,out


def write_features(path,ids,rows,indicators=True):
    fields=['record_id']+FEATURES+(['__missing_'+c for c in FEATURES] if indicators else [])
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for i,r in zip(ids,rows):writer.writerow(dict(record_id=i,**r))
