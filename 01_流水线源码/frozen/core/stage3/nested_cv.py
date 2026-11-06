"""Inner-only model selection; outer labels never enter select_parameters()."""
import warnings
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from common import CONFIG,FEATURES,CAT,R,arrays,scores


def encoder():
    return ColumnTransformer([
        ('num',make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler()),[FEATURES.index(c) for c in R.NUM]),
        ('cat',OneHotEncoder(handle_unknown='ignore'),[FEATURES.index(c) for c in CAT]),
        ('missing','passthrough',list(range(14,20)))])


def model_fit(x,y,c,weight):
    model=LogisticRegression(C=c,class_weight=weight,max_iter=CONFIG['max_iter'],tol=CONFIG['tol'],solver=CONFIG['solver'])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(x,y)
    return model,dict(iterations=int(model.n_iter_[0]),converged=not any(issubclass(w.category,ConvergenceWarning) for w in caught))


def select_parameters(train_rows,y_train,inner_splits):
    # No outer rows, labels, probabilities, or injected ground truth accepted here.
    matrix=arrays(train_rows);y=np.asarray(y_train);trials=[]
    for k,fold in enumerate(inner_splits):
        fit=np.asarray(fold['train_positions']);val=np.asarray(fold['validation_positions'])
        enc=encoder();x=enc.fit_transform(matrix[fit]);xv=enc.transform(matrix[val])
        for c in CONFIG['C_grid']:
            for weight in CONFIG['class_weight_grid']:
                model,info=model_fit(x,y[fit],c,weight);s=scores(y[val],model.predict_proba(xv)[:,1],CONFIG['threshold'])
                trials.append(dict(inner_fold=k,C=c,class_weight=str(weight),**s,**info))
    candidates=[]
    for c in CONFIG['C_grid']:
        for weight in CONFIG['class_weight_grid']:
            selected=[t for t in trials if t['C']==c and t['class_weight']==str(weight)]
            assert len(selected)==CONFIG['inner_folds']
            candidates.append(dict(C=c,class_weight=weight,inner_mean_f1=float(np.mean([t['f1'] for t in selected]))))
    winner=max(candidates,key=lambda x:x['inner_mean_f1'])
    return winner,trials


def predict_outer(train_rows,y_train,outer_rows,winner):
    enc=encoder();x=enc.fit_transform(arrays(train_rows));xv=enc.transform(arrays(outer_rows))
    model,info=model_fit(x,y_train,winner['C'],winner['class_weight'])
    return model.predict_proba(xv)[:,1],info
