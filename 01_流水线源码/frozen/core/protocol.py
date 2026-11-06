"""Shared training/validation protocol. No final-label reader in this module."""
import csv,json,warnings
from pathlib import Path
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,roc_auc_score
from sklearn.exceptions import ConvergenceWarning
from cleaner import ROOT,R,FEATURES,CAT,BOUNDS,Cleaner
import sys
sys.path.insert(0,str(ROOT/'legacy'))
import dq_audit as A
CFG=json.loads((ROOT/'config.json').read_text());OUT=ROOT/'results'


def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf-8')


def csvsave(name,rows):
    if not rows:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def scores(y,p,threshold=.5):
    pred=np.array(p)>=threshold
    return dict(accuracy=accuracy_score(y,pred),precision=precision_score(y,pred,zero_division=0),recall=recall_score(y,pred,zero_division=0),
                f1=f1_score(y,pred,zero_division=0),auc=roc_auc_score(y,p))


def arrays(rows,all_indicators=False):
    indicator_cols=FEATURES if all_indicators else list(R.NUM)
    return np.array([[r[c] if r[c] is not None else np.nan if c in R.NUM else '?' for c in FEATURES]+
                     [r.get('__missing_'+c,float(r[c] is None)) for c in indicator_cols] for r in rows],dtype=object)


def fit_classifier(fit,val,all_indicators=False,grid=True):
    num=[FEATURES.index(c) for c in R.NUM];cat=[FEATURES.index(c) for c in CAT]
    count=len(FEATURES) if all_indicators else len(R.NUM)
    enc=ColumnTransformer([('num',make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler()),num),
                           ('cat',OneHotEncoder(handle_unknown='ignore'),cat),
                           ('missing','passthrough',list(range(len(FEATURES),len(FEATURES)+count)))])
    x=enc.fit_transform(arrays(fit,all_indicators));xv=enc.transform(arrays(val,all_indicators))
    y=[int(r['income']=='>50K') for r in fit];yv=[int(r['income']=='>50K') for r in val]
    best=None;trials=[]
    for c in CFG['C_grid'] if grid else [1.]:
        for weight in CFG['class_weight_grid'] if grid else [None]:
            m=LogisticRegression(C=c,class_weight=weight,max_iter=1000,tol=1e-6,solver='lbfgs')
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always',ConvergenceWarning);m.fit(x,y)
            p=m.predict_proba(xv)[:,1];s=scores(yv,p)
            trials.append(dict(C=c,class_weight=str(weight),val_f1=s['f1'],iterations=int(m.n_iter_[0]),converged=not any(issubclass(w.category,ConvergenceWarning) for w in caught)))
            if best is None or s['f1']>best[0]:best=(s['f1'],enc,m,s)
    return (best[1],best[2],all_indicators),best[3],trials


def predict(bundle,rows):
    enc,model,flags=bundle
    return model.predict_proba(enc.transform(arrays(rows,flags)))[:,1]


def parts(seed):
    raw=R.load_adult();ids=json.loads((ROOT/f'data/development_split_{seed}.json').read_text())['raw_ids']
    return {k:[raw[i] for i in v] for k,v in ids.items()}


def corrupt(rows,ref,rate,seed):
    data,truth,_=R.inject(rows,R.build_domain(ref),rate,seed+int(rate*100))
    return data[:len(rows)],truth


def valid(c,value,bank):
    if value is None:return False
    return BOUNDS[c][0]<=value<=BOUNDS[c][1] and float(value).is_integer() if c in R.NUM else value in bank.dom[c]


def repair_quality(clean,dirty,fixed,truth,flags,bank,seed,rate,version,typ=None):
    keys={k for k,t in truth.items() if typ is None or t==typ}
    changed={(i,c) for i in range(len(clean)) for c in FEATURES if dirty[i][c]!=fixed[i][c]}
    mod=keys&changed;strict=sum(fixed[i][c]==clean[i][c] for i,c in keys)
    exact_modified=sum(fixed[i][c]==clean[i][c] for i,c in mod)
    clean_keys={(i,c) for i in range(len(clean)) for c in FEATURES if (i,c) not in truth}
    reasonable=sum(fixed[i][c]!=clean[i][c] and valid(c,fixed[i][c],bank) for i,c in mod)
    cleanwrong=sum(fixed[i][c]!=clean[i][c] for i,c in changed&clean_keys)
    return dict(seed=seed,rate=rate,version=version,type=typ or 'all',injected=len(keys),detected=len(keys&flags),modified=len(mod),
                strict_restored=strict,reasonable_only=reasonable,wrong_modifications=len(mod)-exact_modified,
                auto_precision=exact_modified/max(1,len(mod)),restoration_rate=strict/max(1,len(keys)),
                clean_modified=cleanwrong,clean_cells=len(clean_keys),clean_misrepair_rate=cleanwrong/max(1,len(clean_keys)),
                total_modified='',total_wrong='',total_precision='')
