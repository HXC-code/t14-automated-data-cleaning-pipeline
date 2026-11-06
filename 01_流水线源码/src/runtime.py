"""Adapter around byte-identical J sources; labels never enter repair inputs."""
import sys,importlib.util,json
from pathlib import Path
from copy import deepcopy
import joblib
from src.paths import FINAL,WORK,CONFIG,FEATURES,NUM,sha

CORE=FINAL/'frozen/core'
sys.path.insert(0,str(CORE));sys.path.insert(0,str(CORE/'stage3'))
import common as frozen_common
from policies import PolicyReplay,inference_features
from cleaner import Cleaner,R,CAT,BOUNDS
from baseline_cleaner import Cleaner as V3Cleaner
import audit as frozen_audit
import nested_cv

spec=importlib.util.spec_from_file_location('original_v32_engine',FINAL/'frozen/V3.2/candidates.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)


def verify_candidate():
    frozen=json.loads((FINAL/'config/candidate_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(FINAL/name)==value for name,value in frozen['files'].items()),'Frozen J source/config/reference changed'


def inject(rows,reference,rate,seed):
    # The unchanged generator requires its old 15-column domain schema. This
    # constant is never a target label and is not used by any injection branch.
    dom=R.build_domain([dict(r,income='__unused_schema_token__') for r in reference])
    data,truth,_=R.inject(inference_features(rows),dom,rate,seed+int(rate*100))
    return data[:len(rows)],truth


def metadata(rows,observed):
    for fixed,raw in zip(rows,observed):
        for c in FEATURES:fixed['__missing_'+c]=raw.get('__missing_'+c,float(raw[c] is None))
    return rows


class FrozenCleaner:
    def __init__(self,seed=20260601,rate=.1,bank=None,v2_reference=None):
        self.seed=seed;self.rate=rate
        self.bank=bank or joblib.load(FINAL/f'reference/bank_{seed}.joblib')
        self.reference=deepcopy(self.bank.ref)
        assert all('income' not in r for r in self.reference)
        self.methods=json.loads((CORE/'baseline_selection.json').read_text())['missing_methods'][str(seed)]
        method_map=json.loads((CORE/'historical/v31_method_map.json').read_text())
        self.method=next(r['method'] for r in method_map if r['seed']==seed and r['rate']==rate)
        self.v2_reference=v2_reference

    def repair(self,rows,version='J'):
        observed=inference_features(rows)
        if version in ['J','A_V3.2']:
            parent=Cleaner(self.reference,self.method);engine=original.RepairEngine(parent,self.bank,self.methods,'B')
            baseline,events,flags=engine.repair(observed)
            replay=PolicyReplay(observed,events,flags,engine.last_review,parent,self.bank)
            result=replay.apply('J' if version=='J' else 'A')
            if version=='A_V3.2':assert result['rows']==baseline
            result['source_events']=events
            return result
        if version in ['V3','V3.1']:
            parent=(V3Cleaner if version=='V3' else Cleaner)(self.reference,self.method)
            fixed,events,flags=parent.repair(observed)
            return dict(rows=metadata(fixed,observed),events=events,flags=flags,review=list(getattr(parent,'last_review',[])))
        if version=='V2':
            assert self.v2_reference is not None,'V2 baseline must use frozen training-batch statistics'
            labelled=lambda rs:[dict(r,income='__unused_schema_token__') for r in rs]
            domain=R.build_domain(labelled(self.reference));events=[]
            fixed,_=R.repair(labelled(observed),domain,None,None,dedup=False,reference=labelled(self.v2_reference),audit=events)
            assert all(e.get('col')!='income' for e in events)
            return dict(rows=metadata(inference_features(fixed),observed),events=events,flags=set(R.rule_scan(labelled(observed),domain)),review=[])
        raise ValueError('Unknown frozen version '+version)

    def profile(self,rows):
        observed=inference_features(rows);scan=self.repair(observed,'J');format_cells=set();typo_cells=set();unknown=set();invalid=set();conflicts=set()
        for i,row in enumerate(observed):
            for c in CAT:
                value=row[c]
                if value is None or value in self.bank.dom[c]:continue
                choices=[v for v in self.bank.dom[c] if v.strip().casefold()==value.strip().casefold()]
                if len(choices)==1:format_cells.add((i,c));continue
                choices=[v for v in self.bank.dom[c] if R.lev(value.strip().upper(),v.upper())<=1]
                (typo_cells if len(choices)==1 else unknown).add((i,c))
            for c in NUM:
                value=row[c]
                if value is not None and (not BOUNDS[c][0]<=value<=BOUNDS[c][1] or not float(value).is_integer()):invalid.add((i,c))
            if row['education'] in R.EDU2NUM and row['education_num'] is not None and row['education_num']!=R.EDU2NUM[row['education']]:conflicts.add((i,'education_num'))
        for case in scan['semantic_cases']:
            conflicts.update((case['row'],c) for c in case['columns'])
        return dict(rows=len(observed),predictor_fields=14,missing_cells=sum(r[c] is None for r in observed for c in FEATURES),
                    missing_by_field={c:sum(r[c] is None for r in observed) for c in FEATURES},detected_cells=len(scan['flags']),
                    numeric_type_or_range_alerts=len(invalid),format_alerts=len(format_cells),spelling_alerts=len(typo_cells),unknown_category_alerts=len(unknown),
                    unit_conversion_proposals=sum(e['action']=='unit_inverse' for e in scan['source_events']),cross_field_alert_cells=len(conflicts),
                    note='Training-reference/rule alerts, not ground-truth errors; a second scan only measures remaining alerts and is not applied')
