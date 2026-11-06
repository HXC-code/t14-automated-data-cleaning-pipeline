"""Frozen training reference. No ground-truth or income argument enters repair."""
import sys
from pathlib import Path
from collections import Counter
import numpy as np
from sklearn.impute import KNNImputer
from sklearn.preprocessing import OneHotEncoder
from outlier_guard import OutlierGuard

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'legacy' / 'exp'))
import run_exp as R

FEATURES = [c for c in R.COLS if c != 'income']
CAT = [c for c in R.CAT if c != 'income']
BOUNDS = {'age': (17, 90), 'hours_per_week': (1, 99),
          'fnlwgt': (1, 1500000), 'education_num': (1, 16),
          'capital_gain': (0, 99999), 'capital_loss': (0, 4356)}
GROUPS = {'age': ['education', 'marital_status'],
          'hours_per_week': ['occupation', 'workclass'],
          'fnlwgt': ['native_country', 'race'],
          'capital_gain': ['education', 'occupation'],
          'capital_loss': ['education', 'occupation'],
          'education_num': ['education']}


class Cleaner:
    def __init__(self, reference, method='conditional', unit_rule='new', threshold=.995,
                 outlier_policy='D', candidate_confidence=.90):
        self.method, self.unit_rule, self.threshold = method, unit_rule, threshold
        self.outlier_policy=outlier_policy
        self.guard=OutlierGuard(reference, candidate_confidence, knn=outlier_policy=='C_knn')
        self.last_review=[]
        self.dom = {c: {r[c] for r in reference if r[c] is not None} for c in CAT}
        self.support = {c: set(r[c] for r in reference if r[c] is not None) for c in R.NUM}
        # Medians must preserve empirical frequency, especially the capital zero mass.
        self.medians = {c: float(np.median([r[c] for r in reference if r[c] is not None])) for c in R.NUM}
        self.scales = {c: max(float(np.percentile([r[c] for r in reference if r[c] is not None], 75)
                                      - np.percentile([r[c] for r in reference if r[c] is not None], 25)), 1.) for c in R.NUM}
        self.counts = {c: Counter(r[c] for r in reference) for c in FEATURES}
        self.groups = {}
        for c in FEATURES:
            gc = GROUPS.get(c, ['education', 'workclass'])
            grouped = {}
            for r in reference:
                if r[c] is not None:
                    grouped.setdefault(tuple(r[g] for g in gc if g != c), []).append(r[c])
            self.groups[c] = (gc, {k: (float(np.median(v)) if c in R.NUM else Counter(v).most_common(1)[0][0])
                                      for k, v in grouped.items() if len(v) >= 20})
        self.reference = [{c: r[c] for c in FEATURES} for r in reference]
        self.encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False).fit(
            [[r[c] or '?' for c in CAT] for r in reference])
        if method == 'knn':
            self.imputer = KNNImputer(n_neighbors=5, weights='distance').fit(self.matrix(reference))

    def matrix(self, rows):
        nums = np.array([[np.nan if r[c] is None else (r[c]-self.medians[c])/self.scales[c]
                          for c in R.NUM] for r in rows])
        cats = self.encoder.transform([[r[c] or '?' for c in CAT] for r in rows])
        return np.column_stack([nums, cats])

    def repair(self, rows):
        out = [dict(r) for r in rows]
        for before, after in zip(rows, out):
            for c in R.NUM:
                after['__missing_'+c] = float(before[c] is None)
        events, alerts, candidates = [], set(), {}

        def set_value(i, c, value, action, confidence=1.):
            alerts.add((i, c))
            if confidence < self.threshold or out[i][c] == value:
                return
            events.append(dict(op='cell_fix', row=i, col=c, before=out[i][c],
                               after=value, action=action, confidence=confidence))
            out[i][c] = value

        for i, r in enumerate(out):
            uncertain = set()
            # Canonicalize first, then apply dependencies; ambiguous edits are review-only.
            for c in CAT:
                v = r[c]
                if v is None:
                    alerts.add((i, c))
                    continue
                if v in self.dom[c]:
                    continue
                alerts.add((i, c))
                exact = [s for s in sorted(self.dom[c]) if s.strip().casefold() == v.strip().casefold()]
                choices = exact or [s for s in sorted(self.dom[c]) if R.lev(v.strip().upper(), s.upper()) <= 1]
                if len(choices) == 1:
                    set_value(i, c, choices[0], 'category_canonicalization')
                    if c == 'education':
                        uncertain.add(c)
                else:
                    uncertain.add(c)
            for c, (lo, hi) in BOUNDS.items():
                v = r[c]
                if v is None:
                    candidates[i, c] = 'missing'; alerts.add((i, c)); continue
                x = v / 1000
                valid = lo <= v <= hi
                # Integer conversions + field range; high-cardinality fnlwgt needn't match a donor exactly.
                convertible = lo <= x <= hi and x.is_integer()
                if self.unit_rule == 'old':
                    convert = not valid and x in self.support[c]
                else:
                    supported = x in self.support[c] or (c == 'fnlwgt' and
                                abs(x-self.medians[c])/self.scales[c] <= 5)
                    convert = c != 'education_num' and not valid and convertible and supported
                    # In-range capital values remain untouched unless conversion has strong distribution evidence.
                    if c in ('capital_gain', 'capital_loss') and valid:
                        convert = (v not in self.support[c] and convertible and x > 0 and
                                   self.counts[c][x] >= 3 and v > max(self.support[c]))
                if convert:
                    set_value(i, c, x, 'unit_inverse')
                elif not valid:
                    alerts.add((i, c)); candidates[i, c] = 'invalid_range'
                elif v not in self.support[c]:
                    robust_z = abs(v-self.medians[c])/self.scales[c]
                    # 999 is not inherently invalid for capital fields; require no training support and large deviation.
                    if c in ('capital_gain', 'capital_loss'):
                        suspicious = (v == 999 and self.counts[c][v] == 0 and
                                      sum(z > 0 for z in self.counts[c] if z is not None) >= 10)
                    else:
                        suspicious = robust_z > 8 and not float(v).is_integer()
                    if suspicious:
                        candidates[i, c] = 'distribution_evidence'; alerts.add((i, c))
            e, en = r['education'], r['education_num']
            if e in R.EDU2NUM and en != R.EDU2NUM[e]:
                alerts.add((i, 'education_num'))
                # Two individually legal conflicting values do not identify the corrupted side.
                if ('education' not in uncertain and self.counts['education'][e] >= 20
                        and (en is None or not 1 <= en <= 16)):
                    set_value(i, 'education_num', float(R.EDU2NUM[e]), 'reliable_dependency')
                    candidates.pop((i, 'education_num'), None)
            rel, sex = r['relationship'], r['sex']
            if (rel, sex) in [('Husband', 'Female'), ('Wife', 'Male')]:
                # Donor consistency provides confidence; both fields must be recognized.
                donor = [q['sex'] for q in self.reference if q['relationship'] == rel]
                target = 'Male' if rel == 'Husband' else 'Female'
                conf = donor.count(target)/max(1, len(donor))
                if not {'relationship', 'sex'} & uncertain:
                    set_value(i, 'sex', target, 'reliable_logic', conf)
            for c in CAT:
                if r[c] is None and self.method != 'global':
                    gc, values = self.groups[c]
                    value = values.get(tuple(r[g] for g in gc if g != c))
                    if value is not None:
                        set_value(i, c, value, 'conditional_mode')

        # Unit conversion and FD keep priority; no second rule changes the same cell.
        handled={(e['row'],e['col']) for e in events}
        overrides={}
        self.last_review=[]
        knn_values=self.guard.knn_values(out) if self.outlier_policy=='C_knn' else {}
        if self.outlier_policy!='A':
            for i,r in enumerate(out):
                for c in NUM_GUARD:
                    if (i,c) in handled or r[c] is None:
                        continue
                    ev=self.guard.evidence(r,c)
                    if ev['alert']:
                        alerts.add((i,c))
                    # B is an alarm-only comparison; its repaired values equal V3.
                    if self.outlier_policy=='B':
                        continue
                    if c in ('capital_gain','capital_loss') and float(r[c]).is_integer() and BOUNDS[c][0]<=r[c]<=BOUNDS[c][1]:
                        candidates.pop((i,c),None)
                        if ev['alert']:
                            self.last_review.append(dict(row=i,col=c,reason='legal_integer_tail',value=r[c],evidence=ev))
                        continue
                    # Integral out-of-range values retain the existing V3 overwrite path.
                    if float(r[c]).is_integer():
                        if ev['alert'] and (i,c) not in candidates:
                            self.last_review.append(dict(row=i,col=c,reason='statistical_alert_only',value=r[c],evidence=ev))
                        continue
                    alerts.add((i,c))
                    context=dict(r)
                    for g in GROUPS[c]:
                        if (i,g) in handled:
                            context[g]=None
                    if self.outlier_policy=='D':
                        proposal,why=self.guard.conservative(context,c)
                        if proposal is None:
                            candidates.pop((i,c),None)
                            self.last_review.append(dict(row=i,col=c,reason=why,value=r[c],evidence=ev))
                            continue
                    elif self.outlier_policy=='C_knn':
                        proposal=dict(value=knn_values[i,c],lower_bound=None,n=5,source='knn')
                    else:
                        proposal=self.guard.candidate(context,c,self.outlier_policy.removeprefix('C_'))
                    candidates[i,c]='outlier_guard'
                    overrides[i,c]=proposal

        # Only candidates with structural evidence reach imputation, never all statistical alerts.
        masked = [dict(r) for r in out]
        for i, c in candidates:
            masked[i][c] = None
        if self.method == 'knn' and candidates:
            mat = self.matrix(masked)
            # Chunk to keep distance matrices bounded; fitted donors remain training-only.
            filled = np.vstack([self.imputer.transform(mat[k:k+256]) for k in range(0, len(mat), 256)])
        for (i, c), reason in candidates.items():
            if (i,c) in overrides:
                proposal=overrides[i,c]
                set_value(i,c,proposal['value'],'outlier_'+proposal['source'])
                if events and events[-1]['row']==i and events[-1]['col']==c:
                    events[-1]['candidate_evidence']=proposal
                continue
            value = self.medians[c]
            if self.method == 'conditional':
                gc, vals = self.groups[c]
                value = vals.get(tuple(out[i][g] for g in gc if g != c), value)
            elif self.method == 'knn':
                value = float(filled[i, list(R.NUM).index(c)]*self.scales[c]+self.medians[c])
                value = float(round(value))
            set_value(i, c, value, self.method+'_'+reason)
        return out, events, alerts


# Coding errors in education_num remain owned by the existing dependency path.
NUM_GUARD=[c for c in R.NUM if c!='education_num']
