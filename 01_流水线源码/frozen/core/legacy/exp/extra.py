# -*- coding: utf-8 -*-
"""补充实验：①修复阶段不与去重耦合的准确率；②关键字段强噪声下的下游敏感性"""
import os, json, random, time
from collections import Counter
import run_exp as R

BASE = os.path.dirname(os.path.abspath(__file__))
SEED = 20260601
out = {}

rows = R.load_adult()
dom = R.build_domain(rows)
bad = {k[0] for k in R.rule_scan(rows, dom)}
pool = [r for i, r in enumerate(rows) if i not in bad and all(r[c] is not None for c in R.COLS)]
rng = random.Random(SEED)
rng.shuffle(pool)
base = pool[:7000]
train_rows, test_rows = base[:4400], base[4400:6400]
medians = {c: R.pct([r[c] for r in train_rows if r[c] is not None], .5) for c in R.NUM}

# ---------- ① 逐单元修复（不去重）
rep = {}
for rate in (0.03, 0.10, 0.20):
    tag = f"{int(rate*100)}pct"
    dirty, truth, dup_of = R.inject(train_rows, dom, rate=rate, seed=SEED + int(rate * 100))
    stats = {}
    for c in R.NUM:
        xs = [r[c] for r in dirty if r[c] is not None]
        med = R.pct(xs, .5); mad = R.pct([abs(x - med) for x in xs], .5) or 1e-9
        stats[c] = {"median": med, "mad": mad, "sigma": 1.4826 * mad}
    fixed, acts = R.repair(dirty, dom, None, stats, dedup=False)
    cut = 3400
    ev = {k: v for k, v in truth.items() if cut <= k[0] < len(train_rows)}
    ok = tot = 0
    ok_by = Counter(); tot_by = Counter()
    for (i, c), t in ev.items():
        tot += 1; tot_by[t] += 1
        orig = train_rows[i][c]; now = fixed[i][c]
        good = (abs(orig - now) < 1e-6) if isinstance(orig, float) and isinstance(now, float) \
            else str(orig).strip().upper() == str(now).strip().upper()
        if good:
            ok += 1; ok_by[t] += 1
    # 修复后行级重复（过度修复的副作用）
    keys = Counter(tuple(r[c] for c in R.COLS) for r in fixed[:len(train_rows)])
    rep[tag] = {"cell_accuracy": round(ok / tot * 100, 2), "cells": tot,
                "by_type": {t: round(ok_by[t] / tot_by[t] * 100, 2) for t in tot_by},
                "actions": dict(acts.most_common(12)),
                "pseudo_dup_rows": sum(v - 1 for v in keys.values() if v > 1)}
out["repair_isolated"] = rep
print("repair", {k: v["cell_accuracy"] for k, v in rep.items()})

# ---------- ② 关键字段强噪声下的下游敏感性
KEY = ["age", "hours_per_week", "education_num"]
ylab = lambda r: 1 if r["income"] == ">50K" else 0
down = {}
for rate in (0.0, 0.10, 0.20, 0.30):
    rng2 = random.Random(SEED + int(rate * 1000))
    dirty = [dict(r) for r in train_rows]
    truth = {}
    if rate > 0:
        n = int(len(dirty) * rate * len(KEY))
        for _ in range(n):
            i = rng2.randrange(len(dirty)); c = rng2.choice(KEY)
            if (i, c) in truth:
                continue
            if c == "age":
                dirty[i][c] = 999.0
            elif c == "hours_per_week":
                dirty[i][c] = (dirty[i][c] or 40) * 1000.0
            else:
                dirty[i][c] = float(rng2.choice([1, 5, 16]))
                if dirty[i][c] == float(R.EDU2NUM.get(dirty[i]["education"], -1)):
                    dirty[i][c] = 7.0
            truth[(i, c)] = "key"
    stats = {}
    for c in R.NUM:
        xs = [r[c] for r in dirty if r[c] is not None]
        med = R.pct(xs, .5); mad = R.pct([abs(x - med) for x in xs], .5) or 1e-9
        stats[c] = {"median": med, "mad": mad, "sigma": 1.4826 * mad}
    fx, _ = R.repair(dirty, dom, None, stats, dedup=False)
    res = {}
    for nm, data in (("原始干净", train_rows), ("未清洗", dirty), ("修复后", fx)):
        pf, dim = R.train_lr([(r, ylab(r)) for r in data if r["income"]], medians)
        s = pf(test_rows)
        y = [ylab(r) for r in test_rows]
        res[nm] = R.auc(y, s)
    down[f"{int(rate*100)}pct"] = res
out["downstream_key_noise"] = down
print("downstream", down)


# ---------- ③ 事故场景：education_num 整列错位（值合法但与 education 不一致）
rng3 = random.Random(SEED + 7)
dirty = [dict(r) for r in train_rows]
for r in dirty:
    e = r.get("education")
    cand = [v for k, v in R.EDU2NUM.items() if k != e]
    r["education_num"] = float(rng3.choice(cand))
truth = {(i, "education_num") for i in range(len(dirty))}
stats = {}
for c in R.NUM:
    xs = [r[c] for r in dirty if r[c] is not None]
    med = R.pct(xs, .5); mad = R.pct([abs(x - med) for x in xs], .5) or 1e-9
    stats[c] = {"median": med, "mad": mad, "sigma": 1.4826 * mad}
fx, _ = R.repair(dirty, dom, None, stats, dedup=False)
res = {}
for nm, data in (("原始干净", train_rows), ("列错位未修复", dirty), ("列错位已修复", fx)):
    pf, dim = R.train_lr([(r, ylab(r)) for r in data if r["income"]], medians)
    res[nm] = {"auc": round(R.auc([ylab(r) for r in test_rows], pf(test_rows)), 4), "dims": dim}
res["修复命中率"] = round(sum(1 for i in range(len(fx)) if fx[i]["education_num"] == train_rows[i]["education_num"])
                       / len(fx) * 100, 2)
out["incident"] = res
print("incident", res)

json.dump(out, open(os.path.join(BASE, "..", "results3.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
