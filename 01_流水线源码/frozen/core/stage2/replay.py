"""Withdraw audit events and invalidated dependencies, without using clean values."""
from copy import deepcopy
from common import R,FEATURES,BOUNDS,CONFIG,RepairEngine
from cleaner import GROUPS


def family(e):
    action=e['action'];c=e['col']
    if action=='unit_inverse':return 'unit'
    if e['before'] is None:return 'missing'
    if action.startswith('v32_overwrite') or (c in BOUNDS and RepairEngine.overwrite_candidate({c:e['before']},c)):return 'overwrite'
    if action.startswith('outlier_') or ('invalid_range' in action and c in BOUNDS):return 'outlier'
    if action=='reliable_logic':return 'logic'
    return 'canonical_or_dependency'


class AuditReplay:
    def __init__(self,dirty,source_events,source_flags,source_review,parent,bank):
        self.dirty=deepcopy(dirty);self.events=deepcopy(source_events);self.flags=set(source_flags)
        self.source_review=deepcopy(source_review);self.parent=parent;self.bank=bank
        self.full=deepcopy(dirty)
        for e in self.events:
            assert self.full[e['row']][e['col']]==e['before'],'Baseline audit chain is inconsistent'
            self.full[e['row']][e['col']]=e['after']
        protected={(e['row'],e['col']) for e in self.events if e['action'] in ['unit_inverse','reliable_dependency'] or e['action'].startswith('outlier_')}
        # V3.2 model candidates see parent output, with originally missing/overwrite fields masked.
        self.model_context=[{c:r[c] for c in FEATURES} for r in self.full]
        for i,row in enumerate(self.dirty):
            for c in FEATURES:
                if row[c] is None or (RepairEngine.overwrite_candidate(row,c) and (i,c) not in protected):self.model_context[i][c]=None
        self.dependencies=[];state=deepcopy(dirty)
        for e in self.events:
            i,c=e['row'],e['col'];action=e['action'];dep={};unknown=False
            context=self.model_context[i] if action.startswith('v32_') else state[i]
            if action.endswith('_D') or any(action.endswith('_'+k) for k in ['K3','K5','K11']):
                dep={g:context[g] for g in FEATURES if g!=c and self.bank.reliable(g,context[g])}
            elif action=='reliable_logic':dep={'relationship':context['relationship']}
            elif action=='reliable_dependency':dep={'education':context['education']}
            elif action.startswith('v32_') and action.endswith(('_B','_C')):
                proposal=self.bank.statistic(context,c,True)
                if proposal['source']=='conditional':dep={g:context[g] for g in self.bank.groups[c][0]}
            elif action=='outlier_conditional':dep={g:context[g] for g in GROUPS[c]}
            elif action.startswith('conditional_'):
                gc,groups=self.parent.groups[c];gc=[g for g in gc if g!=c]
                if tuple(context[g] for g in gc) in groups:dep={g:context[g] for g in gc}
                elif e['after']!=(self.parent.medians[c] if c in R.NUM else None):
                    # An opaque superseded conditional source cannot authorize a new gate.
                    unknown=any(context[g] is None for g in gc)
            self.dependencies.append((dep,unknown))
            state[i][c]=e['after']

    def legal(self,c,v):
        if v is None:return False
        if c in R.NUM:return BOUNDS[c][0]<=v<=BOUNDS[c][1] and float(v).is_integer()
        return v in self.bank.dom[c]

    def confident(self,row,c,value,threshold,agreement=False):
        if not self.legal(c,value):return False
        proposals=[self.bank.statistic(row,c,False),self.bank.statistic(row,c,True)]
        if agreement and not all(p['value']==value for p in proposals):return False
        return any(p['value']==value and p['lower_bound']>=threshold for p in proposals)

    def apply(self,policy='A',disabled_field=None):
        rows=deepcopy(self.dirty);events=[];flags=set(self.flags);withdrawn=[];review=deepcopy(self.source_review)
        for r,before in zip(rows,self.dirty):
            for c in FEATURES:r['__missing_'+c]=before.get('__missing_'+c,float(before[c] is None))
        disable={'B':'missing','C':'overwrite','D':'outlier','E':'unit'}.get(policy)
        for seq,(source,(dep,unknown)) in enumerate(zip(self.events,self.dependencies),1):
            e=deepcopy(source);i,c=e['row'],e['col'];kind=family(e);reason=None
            if c==disabled_field:reason='field_withdrawal'
            elif kind==disable:reason='operation_withdrawal_'+kind
            elif policy in ['F','G'] and kind=='logic':reason='ambiguous_legal_semantic_conflict'
            elif policy=='fnl_review' and c=='fnlwgt' and kind in ['missing','overwrite']:reason='fnlwgt_review_control'
            if reason is None:
                changed=[g for g,expected in dep.items() if rows[i][g]!=expected]
                if rows[i][c]!=e['before']:changed.append(c)
                if changed:reason='upstream_dependency_withdrawn'
                elif unknown and policy in ['F','G','fnl_gate']:reason='conditional_provenance_unknown'
            else:changed=[]
            if reason is None and ((policy in ['F','G'] and kind in ['missing','overwrite','outlier']) or
                                   (policy=='fnl_gate' and c=='fnlwgt' and kind in ['missing','overwrite'])):
                if e['action']!='reliable_dependency':
                    evidence=e.get('candidate_evidence',{})
                    if policy=='F' and evidence.get('lower_bound') is not None:
                        accepted=evidence['lower_bound']>=CONFIG['high_confidence_wilson_lower'] and self.legal(c,e['after'])
                    else:
                        threshold=CONFIG['narrow_gate_wilson_lower'] if policy=='G' else CONFIG['high_confidence_wilson_lower']
                        accepted=self.confident(rows[i],c,e['after'],threshold,agreement=policy=='G')
                    if not accepted:reason='candidate_support_or_stability_insufficient'
            if reason is not None:
                flags.add((i,c));item=dict(source_seq=seq,row=i,col=c,reason=reason,dependencies=dep,
                                          changed_dependencies=changed,observed=self.dirty[i][c],retained_value=rows[i][c])
                withdrawn.append(item);review.append(item);continue
            if policy=='fnl_integer' and c=='fnlwgt' and kind in ['missing','overwrite']:
                value=float(round(e['after']))
                if value!=e['after']:e.update(unprojected_candidate=e['after'],integer_projection='nearest_even',after=value,strict_restoration_claim=False)
            assert rows[i][c]==e['before']
            rows[i][c]=e['after'];e['source_seq']=seq;events.append(e)
        modified={(i,c) for i in range(len(rows)) for c in FEATURES if rows[i][c]!=self.dirty[i][c]}
        detail={(r['row'],r['col']):r for r in review}
        # Pending semantic/dependency review survives even if another action normalized the same cell.
        pending={(r['row'],r['col']) for r in withdrawn}
        queue=[detail.get((i,c),dict(row=i,col=c,reason='retained_alert',retained_value=rows[i][c])) for i,c in sorted((flags-modified)|pending)]
        return dict(rows=rows,events=events,flags=flags,review=queue,withdrawn=withdrawn)
