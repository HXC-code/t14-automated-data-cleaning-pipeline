"""Reproducible paired experiments. Run from V3: python run_v3.py."""
import csv
import hashlib
import itertools
import json
import random
import statistics
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from cleaner import Cleaner, R, ROOT, FEATURES, CAT
sys.path.insert(0, str(ROOT/'legacy'))
import dq_audit as A
import pipeline2 as P

CFG = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
OUT = ROOT/'results'
OUT.mkdir(exist_ok=True)


def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=lambda x: x.item()), encoding='utf-8')


def csvsave(name, rows):
    if rows:
        with (OUT/name).open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def metrics(y, p, threshold=.5):
    pred = np.array(p) >= threshold
    return dict(accuracy=accuracy_score(y, pred), precision=precision_score(y, pred, zero_division=0),
                recall=recall_score(y, pred, zero_division=0), f1=f1_score(y, pred, zero_division=0),
                auc=roc_auc_score(y, p))


def split(raw, seed):
    seen, pool = set(), []
    for i, r in enumerate(raw):
        key = tuple(r[c] for c in R.COLS)
        if key in seen:
            continue
        seen.add(key)
        if all(r[c] is not None for c in R.COLS) and R.EDU2NUM.get(r['education']) == r['education_num']:
            pool.append((i, r))
    random.Random(seed).shuffle(pool)
    parts, offset = {}, 0
    for name, n in CFG['partitions'].items():
        parts[name] = pool[offset:offset+n]; offset += n
    assert offset <= len(pool)
    checks = []
    for a, b in itertools.combinations(parts, 2):
        ids = set(i for i, _ in parts[a]) & set(i for i, _ in parts[b])
        keys = set(tuple(r[c] for c in R.COLS) for _, r in parts[a]) & set(tuple(r[c] for c in R.COLS) for _, r in parts[b])
        assert not ids and not keys
        checks.append(dict(a=a, b=b, index_intersection=len(ids), full_record_intersection=len(keys)))
    save(f'split_{seed}.json', dict(pool_size=len(pool), raw_ids={k: [i for i, _ in v] for k, v in parts.items()}, intersections=checks))
    return {k: [r for _, r in v] for k, v in parts.items()}


def inject(rows, dom, rate, seed, keep=None, omit=None):
    dirty, truth, duplicates = R.inject(rows, dom, rate, seed)
    dirty = dirty[:len(rows)]
    # Keep exactly the same mixed-injection cells for paired isolation/ablation.
    if keep is not None or omit is not None:
        for (i, c), typ in list(truth.items()):
            if (keep is not None and typ != keep) or typ == omit:
                dirty[i][c] = rows[i][c]; del truth[i, c]
    return dirty, truth, duplicates


def arrays(rows):
    return np.array([[np.nan if r[c] is None and c in R.NUM else '?' if r[c] is None else r[c]
                      for c in FEATURES] + [r.get('__missing_'+c, float(r[c] is None)) for c in R.NUM]
                     for r in rows], dtype=object)


def encoder(rows):
    # All statistics and category vocabularies fitted only on inner training rows.
    num = [FEATURES.index(c) for c in R.NUM]; cat = [FEATURES.index(c) for c in CAT]
    enc = ColumnTransformer([
        ('num', make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler()), num),
        ('cat', OneHotEncoder(handle_unknown='ignore'), cat),
        ('original_missing', 'passthrough', list(range(len(FEATURES), len(FEATURES)+len(R.NUM))))])
    return enc.fit(arrays(rows))


def tune(data, inner, validation, test, label, seed, rate, trials):
    fitrows = [data[i] for i in inner]; valrows = [data[i] for i in validation]
    enc = encoder(fitrows)
    x, xv, xt = enc.transform(arrays(fitrows)), enc.transform(arrays(valrows)), enc.transform(arrays(test))
    y = np.array([int(r['income'] == '>50K') for r in fitrows])
    yv = [int(r['income'] == '>50K') for r in valrows]
    best = None
    for c, weight in itertools.product(CFG['C_grid'], CFG['class_weight_grid']):
        model = LogisticRegression(C=c, class_weight=weight, max_iter=CFG['max_iter'], tol=CFG['tol'], solver='lbfgs')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', ConvergenceWarning); model.fit(x, y)
        probs = model.predict_proba(xv)[:, 1]
        score = f1_score(yv, probs >= .5, zero_division=0)
        trials.append(dict(seed=seed, rate=rate, version=label, C=c, class_weight=str(weight),
                           val_f1=score, n_iter=int(model.n_iter_[0]), converged=not any(issubclass(w.category, ConvergenceWarning) for w in caught)))
        if best is None or score > best[0]:
            best = (score, model, probs, c, weight)
    _, model, probs, c, weight = best
    threshold = max(CFG['validation_threshold_grid'], key=lambda t: f1_score(yv, probs >= t, zero_division=0))
    yt = [int(r['income'] == '>50K') for r in test]
    pt = model.predict_proba(xt)[:, 1]
    return [dict(seed=seed, rate=rate, version=label, protocol=protocol, threshold=th, C=c,
                 class_weight=str(weight), **metrics(yt, pt, th))
            for protocol, th in [('fixed_0.5', .5), ('validation_threshold', threshold)]], (enc, model)


def repair_stats(clean, dirty, fixed, truth, flags, seed, rate, version):
    changed = {(i, c) for i in range(len(clean)) for c in FEATURES if dirty[i][c] != fixed[i][c]}
    rows = []
    for typ in R.TYPES[:-1]+['clean']:
        kk = {k for k, t in truth.items() if t == typ} if typ != 'clean' else {(i, c) for i in range(len(clean)) for c in FEATURES if (i, c) not in truth}
        mod = changed & kk
        restored = sum(fixed[i][c] == clean[i][c] for i, c in kk)
        wrong = sum(fixed[i][c] != clean[i][c] for i, c in mod)
        rows.append(dict(seed=seed, rate=rate, version=version, type=typ, cells=len(kk),
                         detected=len(kk & flags), modified=len(mod), wrong_repairs=wrong, restored=restored,
                         restoration_rate=restored/max(1, len(kk)), repair_precision=(len(mod)-wrong)/max(1, len(mod))))
    return rows


def detector(ref, val, ev, dom, rate, seed):
    dt, truth, _ = inject(ref, dom, rate, seed+int(rate*100))
    dv, tv, _ = inject(val, dom, rate, seed+100+int(rate*100))
    de, te, _ = inject(ev, dom, rate, seed+200+int(rate*100))
    _, stats = R.stat_scan(ref)
    def feats(rows):
        return P.cell_features(rows, dom, {}, stats, R.EDU2NUM, reference=ref)[0]
    def labels(rows, t):
        return [int((i, c) in t) for i in range(len(rows)) for c in R.COLS]
    model = HistGradientBoostingClassifier(max_iter=60, max_depth=3, learning_rate=.18, random_state=seed).fit(feats(dt), labels(dt, truth))
    pv = model.predict_proba(feats(dv))[:, 1]; yv = labels(dv, tv)
    alert_threshold = max(np.linspace(.05, .95, 37), key=lambda t: f1_score(yv, pv >= t, zero_division=0))
    pe = model.predict_proba(feats(de))[:, 1]; ye = labels(de, te)
    rh = R.rule_scan(de, dom)
    union = np.array([int((i, c) in rh) for i in range(len(de)) for c in R.COLS]) | (pe >= alert_threshold)
    return dict(seed=seed, rate=rate, alert_threshold=float(alert_threshold), auto_repair_threshold=CFG['auto_repair_threshold'],
                **metrics(ye, pe, alert_threshold), union_precision=precision_score(ye, union, zero_division=0),
                union_fp=int(sum((union == 1) & (np.array(ye) == 0))), classifier_fp=int(sum((pe >= alert_threshold) & (np.array(ye) == 0))))


def legacy_eval(data, test, seed, rate, version):
    med = {c: R.pct([r[c] for r in data if r[c] is not None], .5) for c in R.NUM}
    fn, _ = R.train_lr([(r, int(r['income'] == '>50K')) for r in data], med)
    return dict(seed=seed, rate=rate, version=version, protocol='legacy_22_fixed_0.5', threshold=.5,
                C='', class_weight='', **metrics([int(r['income'] == '>50K') for r in test], expit(fn(test))))


def run():
    raw = R.load_adult()
    results, repairs, trials, methods, detection, audit_checks, quality, effects = [], [], [], [], [], [], [], []
    for seed in CFG['seeds']:
        parts = split(raw, seed)
        ref, train, test = parts['detector_train'], parts['downstream_train'], parts['downstream_test']
        dom = R.build_domain(ref)
        inner, valid = train_test_split(np.arange(len(train)), test_size=CFG['downstream_validation_fraction'],
                                      random_state=seed, stratify=[r['income'] for r in train])
        save(f'inner_split_{seed}.json', dict(train=inner.tolist(), validation=valid.tolist()))
        for rate in CFG['rates']:
            tag = f'{seed}_{int(rate*100)}'
            dirty, truth, dup = inject(train, dom, rate, seed+int(rate*100))
            vd, vt, _ = inject(parts['detector_validation'], dom, rate, seed+100+int(rate*100))
            # Independent historical training reference: no downstream original values or labels used.
            candidates = {}
            for method in CFG['imputation_methods']:
                cleaner = Cleaner(ref, method, threshold=CFG['auto_repair_threshold'])
                vfixed, ve, vf = cleaner.repair(vd)
                # Choose using validation feature reconstruction only; validation truth stays offline.
                # All 14 fields equally weighted; no income enters filling or selection.
                correct = sum(vfixed[i][c] == parts['detector_validation'][i][c] for i in range(len(vd)) for c in FEATURES)
                loss = 0.
                for i, c in vt:
                    target = parts['detector_validation'][i][c]
                    if c in R.NUM:
                        loss += min(20., abs(vfixed[i][c]-target)/cleaner.scales[c])
                    else:
                        loss += float(vfixed[i][c] != target)
                methods.append(dict(seed=seed, rate=rate, method=method, unit_rule='new',
                                    validation_correct=correct, validation_scaled_error=loss,
                                    validation_modified=len(ve), validation_wrong=sum(vfixed[e['row']][e['col']] != parts['detector_validation'][e['row']][e['col']] for e in ve)))
                candidates[method] = (loss, cleaner)
            chosen = min(candidates, key=lambda m: candidates[m][0])
            cleaner = candidates[chosen][1]
            fixed, events, flags = cleaner.repair(dirty)
            # Old unit rule ablation on same independent validation, same imputer.
            oldfixed, oldevents, oldflags = Cleaner(ref, chosen, 'old').repair(vd)
            methods.append(dict(seed=seed, rate=rate, method=chosen, unit_rule='old',
                                validation_correct=sum(oldfixed[i][c] == parts['detector_validation'][i][c] for i in range(len(vd)) for c in FEATURES),
                                validation_scaled_error='', validation_modified=len(oldevents),
                                validation_wrong=sum(oldfixed[e['row']][e['col']] != parts['detector_validation'][e['row']][e['col']] for e in oldevents)))
            legacy_events = []
            v2, _ = R.repair(dirty, R.build_domain(train), None, None, reference=dirty, dedup=False, audit=legacy_events)
            oracle = [dict(r) for r in dirty]
            for i, c in truth:
                oracle[i][c] = train[i][c]
            assert oracle == train
            for data in [dirty, v2, fixed, oracle]:
                assert [r['income'] for r in data] == [r['income'] for r in train]
            A.write_log(events, OUT/f'audit_{tag}.jsonl')
            verification = A.verify(dirty, A.rollback(fixed, A.read_log(OUT/f'audit_{tag}.jsonl')), R.COLS)
            assert verification['identical']
            audit_checks.append(dict(seed=seed, rate=rate, method=chosen, **verification))
            save(f'review_{tag}.json', [dict(row=i, col=c, value=dirty[i][c]) for i,c in sorted(flags-set((e['row'], e['col']) for e in events))])
            versions = {'clean': train, 'dirty': dirty, 'v2': v2, 'v3': fixed, 'oracle': oracle}
            for data in [v2, fixed]:
                for original, repaired in zip(dirty, data):
                    for c in R.NUM:
                        repaired['__missing_'+c] = float(original[c] is None)
            for name, data in versions.items():
                scored, _ = tune(data, inner, valid, test, name, seed, rate, trials)
                results.extend(scored); results.append(legacy_eval(data, test, seed, rate, name))
                quality.append(dict(seed=seed, rate=rate, version=name, rule_flags=len(R.rule_scan(data, dom)),
                                    missing=sum(r[c] is None for r in data for c in FEATURES),
                                    original_cell_mismatches=sum(r[c] != train[i][c] for i,r in enumerate(data) for c in FEATURES)))
            repairs.extend(repair_stats(train, dirty, v2, truth, set(R.rule_scan(dirty, dom)), seed, rate, 'v2'))
            repairs.extend(repair_stats(train, dirty, fixed, truth, flags, seed, rate, 'v3'))
            detection.append(detector(ref, parts['detector_validation'], parts['detector_evaluation'], dom, rate, seed))
            # Fixed model parameters from independent clean inner validation, shared across all type effects.
            clean_trial = [r for r in trials if r['seed']==seed and r['rate']==rate and r['version']=='clean']
            hp = max(clean_trial, key=lambda r:r['val_f1'])
            for typ in R.TYPES[:-1]:
                for mode in ['only', 'omit']:
                    isolated, it, _ = inject(train, dom, rate, seed+int(rate*100), **({'keep':typ} if mode=='only' else {'omit':typ}))
                    isolated_fixed, _, _ = cleaner.repair(isolated)
                    for version, data in [('dirty', isolated), ('v3', isolated_fixed)]:
                        enc = encoder([data[i] for i in inner])
                        model = LogisticRegression(C=hp['C'], class_weight=None if hp['class_weight']=='None' else hp['class_weight'], max_iter=CFG['max_iter'], tol=CFG['tol'])
                        model.fit(enc.transform(arrays([data[i] for i in inner])), [int(data[i]['income']=='>50K') for i in inner])
                        prob = model.predict_proba(enc.transform(arrays(test)))[:,1]
                        effects.append(dict(seed=seed, rate=rate, type=typ, mode=mode, version=version,
                                            injected=len(it), **metrics([int(r['income']=='>50K') for r in test], prob)))
            for name, rows in [('runs.csv', results), ('repair_by_type.csv', repairs), ('tuning.csv', trials),
                               ('repair_methods.csv', methods), ('detectors.csv', detection), ('quality.csv', quality), ('type_effects.csv', effects)]:
                csvsave(name, rows)
            save('rollback_verification.json', audit_checks)
            print(f'completed seed={seed} rate={rate} method={chosen}', flush=True)
    summarize(results)


def summarize(rows):
    summary, gains = [], []
    for protocol in sorted(set(r['protocol'] for r in rows)):
        for rate in CFG['rates']:
            for version in ['clean','dirty','v2','v3','oracle']:
                group = [r for r in rows if r['protocol']==protocol and r['rate']==rate and r['version']==version]
                assert len(group)==5
                rec = dict(protocol=protocol, rate=rate, version=version, n=len(group))
                for m in ['accuracy','precision','recall','f1','auc']:
                    rec[m+'_mean']=statistics.mean(r[m] for r in group); rec[m+'_sample_std']=statistics.stdev(r[m] for r in group)
                summary.append(rec)
            for version in ['v2','v3','clean','oracle']:
                delta = [100*(next(r['f1'] for r in rows if r['seed']==s and r['rate']==rate and r['version']==version and r['protocol']==protocol)-
                              next(r['f1'] for r in rows if r['seed']==s and r['rate']==rate and r['version']=='dirty' and r['protocol']==protocol)) for s in CFG['seeds']]
                gains.append(dict(protocol=protocol, rate=rate, version=version, gain_pp_mean=statistics.mean(delta),
                                  gain_pp_sample_std=statistics.stdev(delta), meets_3pp=statistics.mean(delta)>=3))
    csvsave('summary.csv',summary); csvsave('gains.csv',gains)


if __name__ == '__main__':
    run()
