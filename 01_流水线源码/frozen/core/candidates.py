"""Training-reference-only feature prediction, excluding income and target field."""
from collections import Counter
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier,ExtraTreesRegressor
from sklearn.impute import SimpleImputer,KNNImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from cleaner import R,FEATURES,CAT,BOUNDS,GROUPS
from outlier_guard import wilson_lower

METHODS=['A','B','K3','K5','K11','D']


class CandidateBank:
    def __init__(self,reference,seed):
        self.ref=[{c:r[c] for c in FEATURES} for r in reference]
        self.dom={c:sorted({r[c] for r in self.ref if r[c] is not None}) for c in CAT}
        self.med={c:float(np.median([r[c] for r in self.ref])) for c in R.NUM}
        self.counts={c:Counter(r[c] for r in self.ref) for c in FEATURES}
        self.groups={};self.models={};self.seed=seed
        for c in FEATURES:
            gc=[g for g in GROUPS.get(c,['education','workclass']) if g!=c];groups={}
            for r in self.ref:groups.setdefault(tuple(r[g] for g in gc),[]).append(r[c])
            self.groups[c]=(gc,{k:v for k,v in groups.items() if len(v)>=20})
        self.cat_encoder=OneHotEncoder(handle_unknown='ignore',sparse_output=False).fit([[r[c] for c in CAT] for r in self.ref])
        self.cat_blocks={};start=len(R.NUM)
        for c,values in zip(CAT,self.cat_encoder.categories_):self.cat_blocks[c]=slice(start,start+len(values));start+=len(values)
        self.numeric_center={};self.numeric_scale={}
        for c in R.NUM:
            v=np.array([r[c] for r in self.ref]);v=np.log1p(v) if c.startswith('capital_') else v
            self.numeric_center[c]=float(np.median(v));self.numeric_scale[c]=max(1.,float(np.quantile(v,.75)-np.quantile(v,.25)))
        matrix=self.matrix(self.ref)
        self.knn={k:KNNImputer(n_neighbors=k,weights='distance').fit(matrix) for k in [3,5,11]}

    def reliable(self,c,v):
        if v is None:return False
        return (BOUNDS[c][0]<=v<=BOUNDS[c][1] and float(v).is_integer()) if c in R.NUM else v in self.dom[c]

    def matrix(self,rows):
        num=np.array([[np.nan if not self.reliable(c,r[c]) else
                       ((np.log1p(r[c]) if c.startswith('capital_') else r[c])-self.numeric_center[c])/self.numeric_scale[c]
                       for c in R.NUM] for r in rows])
        cat=self.cat_encoder.transform([[r[c] if self.reliable(c,r[c]) else self.dom[c][0] for c in CAT] for r in rows])
        for i,r in enumerate(rows):
            for c in CAT:
                if not self.reliable(c,r[c]):cat[i,self.cat_blocks[c]]=np.nan
        return np.column_stack([num,cat])

    def statistic(self,row,c,conditional=True,baseline_method='conditional'):
        gc,groups=self.groups[c]
        use=conditional and all(self.reliable(g,row[g]) for g in gc)
        vals=groups.get(tuple(row[g] for g in gc)) if use else None
        if vals is None:
            vals=[r[c] for r in self.ref];source='global'
        else:source='conditional'
        value=float(np.median(vals)) if c in R.NUM else Counter(vals).most_common(1)[0][0]
        n=len(vals);matches=sum(x==value for x in vals)
        return dict(value=value,lower_bound=wilson_lower(matches,n),n=n,source=source)

    def model_matrix(self,rows,c):
        predictors=[k for k in FEATURES if k!=c]
        return np.array([[r[k] if self.reliable(k,r[k]) else np.nan if k in R.NUM else '?' for k in predictors] for r in rows],dtype=object)

    def fit_model(self,c):
        if c in self.models:return
        predictors=[k for k in FEATURES if k!=c];nums=[i for i,k in enumerate(predictors) if k in R.NUM];cats=[i for i,k in enumerate(predictors) if k in CAT]
        enc=ColumnTransformer([('num',make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler()),nums),
                               ('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)])
        x=enc.fit_transform(self.model_matrix(self.ref,c));y=np.array([r[c] for r in self.ref])
        cls=ExtraTreesRegressor if c in R.NUM else ExtraTreesClassifier
        model=cls(n_estimators=64,max_depth=12,min_samples_leaf=5,random_state=self.seed,n_jobs=2).fit(x,y)
        zero=None
        if c.startswith('capital_'):
            zero=ExtraTreesClassifier(n_estimators=64,max_depth=10,min_samples_leaf=8,random_state=self.seed,n_jobs=2).fit(x,y==0)
        self.models[c]=(enc,model,zero)

    def predict(self,rows,c,method):
        if method in ['A','B']:
            return [self.statistic(r,c,conditional=method=='B')['value'] for r in rows]
        if method.startswith('K'):
            masked=[dict(r,**{c:None}) for r in rows];mat=self.matrix(masked)
            filled=np.vstack([self.knn[int(method[1:])].transform(mat[k:k+128]) for k in range(0,len(mat),128)])
            if c in R.NUM:
                v=filled[:,list(R.NUM).index(c)]*self.numeric_scale[c]+self.numeric_center[c]
                if c.startswith('capital_'):v=np.expm1(v)
                return [float(np.clip(round(x),*BOUNDS[c])) for x in v]
            block=self.cat_blocks[c];idx=list(CAT).index(c);values=self.cat_encoder.categories_[idx]
            return [str(values[int(np.argmax(x))]) for x in filled[:,block]]
        self.fit_model(c);enc,model,zero=self.models[c];x=enc.transform(self.model_matrix(rows,c));pred=model.predict(x)
        if zero is not None:
            prob=zero.predict_proba(x)[:,list(zero.classes_).index(True)]
            pred=np.where(prob>=.5,0,pred)
        return [float(np.clip(round(v),*BOUNDS[c])) for v in pred] if c in R.NUM else [str(v) for v in pred]


class RepairEngine:
    """Wrap frozen V3.1; replace only missing and declared field-overwrite actions."""
    def __init__(self,parent,bank,missing_methods=None,overwrite='A'):
        self.parent=parent;self.bank=bank;self.missing_methods=missing_methods or {};self.overwrite=overwrite;self.last_review=[]

    @staticmethod
    def overwrite_candidate(row,c):
        sentinels={'age':999.,'hours_per_week':999.,'fnlwgt':99999999.}
        return c in sentinels and row[c]==sentinels[c] and not BOUNDS[c][0]<=row[c]<=BOUNDS[c][1]

    def repair(self,rows):
        out,events,flags=self.parent.repair(rows);self.last_review=list(self.parent.last_review)
        owned={(e['row'],e['col']) for e in events if e['action'] in ['unit_inverse','reliable_dependency'] or e['action'].startswith('outlier_')}
        targets={};contexts=[]
        for i,(before,after) in enumerate(zip(rows,out)):
            context={c:after[c] for c in FEATURES}
            for c in FEATURES:
                after['__missing_'+c]=before.get('__missing_'+c,float(before[c] is None))
                if before[c] is None or (self.overwrite_candidate(before,c) and (i,c) not in owned):context[c]=None
                if (i,c) in owned:continue
                method=self.missing_methods.get(c,'A') if before[c] is None else self.overwrite if self.overwrite_candidate(before,c) else 'A'
                kind='missing' if before[c] is None else 'overwrite'
                if method!='A':targets[i,c]=(kind,'G' if kind=='overwrite' and method=='B' else method)
            for c in getattr(self.parent,'context_exclusions',{}).get(i,set()):
                context[c]=None
            contexts.append(context)
        # Remove superseded baseline actions before applying one replacement event.
        events=[e for e in events if (e['row'],e['col']) not in targets]
        for i,c in targets:out[i][c]=rows[i][c];flags.add((i,c))
        for c in FEATURES:
            for method in ['B','C','D','E','G','K3','K5','K11']:
                indices=[i for (i,k),(_,m) in targets.items() if k==c and m==method]
                if not indices:continue
                context=[contexts[i] for i in indices]
                if method=='E':
                    candidates=[]
                    for row in context:
                        g=self.bank.statistic(row,c,False);q=self.bank.statistic(row,c,True)
                        candidates.append(q['value'] if q['value']==g['value'] and max(q['lower_bound'],g['lower_bound'])>=.9 else None)
                else:candidates=self.bank.predict(context,c,'A' if method=='G' else 'B' if method=='C' else method)
                for i,value in zip(indices,candidates):
                    kind,_=targets[i,c]
                    if value is None:
                        self.last_review.append(dict(row=i,col=c,value=rows[i][c],reason='insufficient_candidate_confidence'));continue
                    if out[i][c]==value:continue
                    events.append(dict(op='cell_fix',row=i,col=c,before=rows[i][c],after=value,
                                       action='v32_'+kind+'_'+method,candidate_kind='approximate_imputation',strict_restoration_claim=False))
                    out[i][c]=value
        new_events=[e for e in events if e['action'].startswith('v32_')]
        assert len(new_events)==len({(e['row'],e['col']) for e in new_events})
        assert not {(e['row'],e['col']) for e in new_events}&owned
        return out,events,flags
