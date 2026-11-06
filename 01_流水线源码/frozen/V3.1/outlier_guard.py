"""Field evidence and training-only candidates; no synthetic truth or income."""
from collections import Counter
import numpy as np
from sklearn.impute import KNNImputer
from sklearn.preprocessing import OneHotEncoder
from baseline_cleaner import R, FEATURES, CAT, BOUNDS, GROUPS


def wilson_lower(successes, n):
    if not n:
        return 0.
    z=1.96; p=successes/n
    return (p+z*z/(2*n)-z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)


class OutlierGuard:
    def __init__(self, reference, confidence=.90, knn=False):
        self.confidence=confidence
        self.ref=[{c:r[c] for c in FEATURES} for r in reference]
        self.stats={};self.groups={};self.dom={c:set(r[c] for r in self.ref) for c in CAT}
        for c in R.NUM:
            x=np.array([r[c] for r in self.ref if r[c] is not None]);med=float(np.median(x))
            positive=x[x>0]
            self.stats[c]=dict(median=med,mad=float(np.median(abs(x-med))),
                               q001=float(np.quantile(x,.001)),q999=float(np.quantile(x,.999)),
                               iqr=max(1.,float(np.quantile(x,.75)-np.quantile(x,.25))),
                               positive_q999=float(np.quantile(positive,.999)) if len(positive) else 0.,
                               counts=Counter(x),n=len(x),support=set(x))
            gc=GROUPS[c];groups={}
            for row in self.ref:
                groups.setdefault(tuple(row[g] for g in gc),[]).append(row[c])
            self.groups[c]={k:v for k,v in groups.items() if len(v)>=20}
        if knn:
            self.encoder=OneHotEncoder(handle_unknown='ignore',sparse_output=False).fit([[r[c] or '?' for c in CAT] for r in self.ref])
            self.knn=KNNImputer(n_neighbors=5,weights='distance').fit(self.matrix(self.ref))

    def evidence(self, row, c):
        v=row[c];s=self.stats[c];lo,hi=BOUNDS[c]
        if v is None:
            return dict(alert=False,structural=False,reason='missing')
        fractional=not float(v).is_integer()
        invalid=not lo<=v<=hi
        mad=s['mad']
        z=abs(v-s['median'])/(1.4826*mad) if mad>0 else None
        # Zero-inflated capital: positive-tail quantile is an alert, never an authorization.
        if c in ('capital_gain','capital_loss'):
            extreme=v>s['positive_q999']
        else:
            extreme=(z is not None and z>({'age':4.5,'fnlwgt':6.,'hours_per_week':4.5,'education_num':4.5}[c])) or v<s['q001'] or v>s['q999']
        return dict(alert=invalid or fractional or extreme,structural=invalid or fractional,
                    reason='invalid_range' if invalid else 'fractional_integer_field' if fractional else 'tail_review',
                    robust_z=z,reference_support=v in s['support'])

    def reliable_group(self,row,c):
        gc=GROUPS[c]
        for g in gc:
            v=row[g]
            if v is None:
                return None
            if g in R.NUM:
                lo,hi=BOUNDS[g]
                if not lo<=v<=hi or not float(v).is_integer():return None
            elif v not in self.dom[g]:return None
        return self.groups[c].get(tuple(row[g] for g in gc))

    def candidate(self,row,c,method):
        s=self.stats[c];vals=self.reliable_group(row,c) if method=='conditional' else None
        if vals is None:
            value=s['median'];count=s['counts'][value];n=s['n'];source='global'
        else:
            value=float(np.median(vals));n=len(vals);count=sum(v==value for v in vals);source='conditional'
        lower=wilson_lower(count,n) if source!='global' or n>=100 else 0.
        return dict(value=value,lower_bound=lower,support=count,n=n,source=source)

    def conservative(self,row,c):
        global_=self.candidate(row,c,'global');conditional=self.candidate(row,c,'conditional')
        if global_['value']!=conditional['value']:
            return None,'candidate_disagreement'
        best=max([global_,conditional],key=lambda r:r['lower_bound'])
        if best['lower_bound']<self.confidence:
            return None,'candidate_not_concentrated'
        return best,'concentrated_training_support'

    def matrix(self,rows):
        numeric=[]
        for row in rows:
            values=[]
            for c in R.NUM:
                v=row[c];s=self.stats[c]
                # Mask other structurally suspect features to avoid using corrupt neighbors.
                if v is None or self.evidence(row,c)['structural']:
                    values.append(np.nan)
                else:
                    # Compress heavy tails for distance calculation only; does not alter source values.
                    if c in ('capital_gain','capital_loss'):v=np.log1p(v)
                    else:v=(v-s['median'])/s['iqr']
                    values.append(v)
            numeric.append(values)
        cat=self.encoder.transform([[r[c] if r[c] in self.dom[c] else '?' for c in CAT] for r in rows])
        return np.column_stack([np.array(numeric),cat])

    def knn_values(self,rows):
        x=self.matrix(rows)
        filled=np.vstack([self.knn.transform(x[k:k+128]) for k in range(0,len(x),128)])
        out={}
        for i,row in enumerate(rows):
            for j,c in enumerate(R.NUM):
                if self.evidence(row,c)['structural']:
                    v=filled[i,j]
                    v=np.expm1(v) if c in ('capital_gain','capital_loss') else v*self.stats[c]['iqr']+self.stats[c]['median']
                    out[i,c]=float(round(v))
        return out
