"""Surgical candidate gates. No income or injected-truth inputs are used."""
from copy import deepcopy
import importlib.util
from common import *
from audit import marker_event,set_markers
spec=importlib.util.spec_from_file_location('stage2_dependency_replay',ROOT/'stage2/replay.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def fnlwgt_target(e):
    if e['col']!='fnlwgt' or e['action'] in ['unit_inverse','reliable_dependency'] or e['action'].startswith('outlier_'):return False
    return e['before'] is None or e['action'].startswith('v32_overwrite') or e['action'].endswith('invalid_range') or RepairEngine.overwrite_candidate({'fnlwgt':e['before']},'fnlwgt')


class PolicyReplay(base.AuditReplay):
    def fnlwgt_evidence(self,row,e):
        value=e['after'];global_=self.bank.statistic(row,'fnlwgt',False);conditional=self.bank.statistic(row,'fnlwgt',True)
        legal=self.legal('fnlwgt',value)
        supported=legal and all(p['n']>=CONFIG['fnlwgt_min_support'] and p['value']==value for p in [global_,conditional])
        supported=supported and max(global_['lower_bound'],conditional['lower_bound'])>=CONFIG['high_confidence_wilson_lower']
        return supported,dict(integer_and_range_valid=legal,global_proposal=global_,conditional_proposal=conditional,
                              threshold=CONFIG['high_confidence_wilson_lower'],candidate_is_estimate=True,strict_restoration_claim=False)

    def apply(self,policy='A'):
        assert policy in CONFIG['policies']
        rows=deepcopy(self.dirty);events=[];flags=set(self.flags);audit=[marker_event(rows)];set_markers(rows,audit[0])
        withheld=[];review_details={};pending=set();reviewed=set()
        for seq,(source,(dependencies,unknown)) in enumerate(zip(self.events,self.dependencies),1):
            e=deepcopy(source);i,c=e['row'],e['col'];reasons=[];evidence={}
            # Deterministic education mapping remains independent of statistical missing imputation.
            if policy in ['B','J'] and e['before'] is None and e['action']!='reliable_dependency':reasons.append('B_pipeline_missing_preserved')
            if policy in ['H','J'] and fnlwgt_target(e):
                accepted,evidence=self.fnlwgt_evidence(rows[i],e)
                if not accepted:reasons.append('H_fnlwgt_candidate_not_reliably_identified')
            if policy in ['I','J'] and e['action']=='reliable_logic':
                snapshot={g:rows[i][g] for g in ['sex','relationship','marital_status']}
                evidence.update(semantic_snapshot=snapshot,conflict_class='semantic_exception_possible' if all(self.bank.reliable(g,v) for g,v in snapshot.items()) else 'direction_unknown',
                                association_is_not_absolute_constraint=True)
                reasons.append('I_legal_semantic_conflict_direction_unidentified')
            changed=[g for g,expected in dependencies.items() if rows[i][g]!=expected]
            if rows[i][c]!=e['before']:changed.append(c)
            if changed:reasons.append('upstream_dependency_withdrawn')
            if unknown and policy in ['H','J'] and fnlwgt_target(e):reasons.append('conditional_provenance_unknown')
            if reasons:
                decision=dict(op='review',row=i,col=c,before=rows[i][c],after=rows[i][c],action='retain_value_for_review',source_seq=seq,
                              source_action=e['action'],proposed_after=e['after'],reasons=reasons,dependencies=dependencies,
                              changed_dependencies=changed,evidence=evidence,strict_restoration_claim=False)
                audit.append(decision);withheld.append(decision);pending.add((i,c));flags.add((i,c));reviewed.add((i,c));review_details[i,c]=reasons
                continue
            assert rows[i][c]==e['before']
            e['source_seq']=seq;e['stage3_policy']=policy
            if fnlwgt_target(e):e.update(candidate_kind='approximate_imputation',strict_restoration_claim=False)
            rows[i][c]=e['after'];events.append(e);audit.append(e)
        semantic=[]
        if policy in ['I','J']:
            for i,r in enumerate(rows):
                snapshot={g:r[g] for g in ['sex','relationship','marital_status']};reasons=[];cols=set()
                invalid={g for g,v in snapshot.items() if not self.bank.reliable(g,v)}
                if invalid:reasons.append('semantic_fields_missing_or_unrecognized');cols|=invalid
                if r['relationship'] in ['Husband','Wife']:
                    expected='Male' if r['relationship']=='Husband' else 'Female'
                    if r['sex'] in ['Male','Female'] and r['sex']!=expected:
                        reasons.append('legal_role_sex_association_exception');cols|={'sex','relationship'}
                    if self.bank.reliable('marital_status',r['marital_status']) and r['marital_status'] not in ['Married-civ-spouse','Married-AF-spouse']:
                        reasons.append('role_marital_status_direction_unknown');cols|={'relationship','marital_status'}
                if reasons:
                    case=dict(op='semantic_case',action='review_semantic_case',row=i,columns=sorted(cols),snapshot=snapshot,reasons=reasons,automatic_change=False)
                    audit.append(case);semantic.append(case)
                    for c in cols:pending.add((i,c));flags.add((i,c));review_details.setdefault((i,c),[]).extend(reasons)
        modified={(i,c) for i,r in enumerate(rows) for c in FEATURES if r[c]!=self.dirty[i][c]}
        baseline_details={(r['row'],r['col']):r.get('reason','baseline_unresolved_alert') for r in self.source_review}
        queue=[]
        for i,c in sorted((flags-modified)|pending):
            reasons=sorted(set(review_details.get((i,c),[])+[baseline_details.get((i,c),'retained_alert')]))
            queue.append(dict(row=i,col=c,value=rows[i][c],reasons=reasons))
            if (i,c) not in reviewed:
                audit.append(dict(op='review',row=i,col=c,before=rows[i][c],after=rows[i][c],action='review_unresolved_alert',reasons=reasons))
        return dict(rows=rows,events=events,audit=audit,flags=flags,review=queue,withheld=withheld,semantic_cases=semantic)


def inference_features(rows):
    """Callers keep labels separately; a supplied income field is never propagated."""
    return [{**{c:r[c] for c in FEATURES},**{k:v for k,v in r.items() if k.startswith('__missing_')}} for r in rows]
