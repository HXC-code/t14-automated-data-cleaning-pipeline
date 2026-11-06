# -*- coding: utf-8 -*-
"""
真实数据清洗流水线实验（纯标准库实现，无第三方依赖）
数据：UCI Adult（训练集 32561 行 × 15 列）、UCI Mushroom（8124 行 × 23 列）
产出：results.json（全部指标与曲线点位），供绘图与正文引用
"""
import os, re, json, math, random, time
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "data")
RNG_SEED = 20260601

COLS = ["age", "workclass", "fnlwgt", "education", "education_num", "marital_status",
        "occupation", "relationship", "race", "sex", "capital_gain", "capital_loss",
        "hours_per_week", "native_country", "income"]
NUM = ("age", "fnlwgt", "education_num", "capital_gain", "capital_loss", "hours_per_week")
CAT = [c for c in COLS if c not in NUM]

EDU2NUM = {"Preschool": 1, "1st-4th": 2, "5th-6th": 3, "7th-8th": 4, "9th": 5, "10th": 6,
           "11th": 7, "12th": 8, "HS-grad": 9, "Some-college": 10, "Assoc-voc": 11,
           "Assoc-acdm": 12, "Bachelors": 13, "Masters": 14, "Prof-school": 15, "Doctorate": 16}

MARR_IED = {"Married-civ-spouse": {"Husband", "Wife"},
            "Never-married": {"Not-in-family", "Own-child", "Unmarried", "Other-relative"},
            "Divorced": {"Not-in-family", "Unmarried", "Own-child", "Other-relative"},
            "Separated": {"Not-in-family", "Unmarried", "Own-child", "Other-relative"},
            "Widowed": {"Not-in-family", "Unmarried", "Own-child", "Other-relative"},
            "Married-spouse-absent": {"Not-in-family", "Unmarried", "Other-relative"},
            "Married-AF-spouse": {"Husband", "Wife"}}


# ------------------------------------------------------------------ 读数据
def load_adult():
    rows = []
    with open(os.path.join(DATA, "adult.data"), encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln.strip():
                continue
            p = [x.strip().rstrip(".") for x in ln.split(",")]
            if len(p) != 15:
                continue
            rec = {}
            ok = True
            for c, v in zip(COLS, p):
                if c in NUM:
                    if v == "?" or v == "":
                        rec[c] = None
                    else:
                        try:
                            rec[c] = float(v)
                        except ValueError:
                            rec[c] = None
                            ok = False
                else:
                    rec[c] = None if v in ("?", "") else v
            if ok or True:
                rows.append(rec)
    return rows


def load_mushroom():
    rows = []
    with open(os.path.join(DATA, "mushroom.data"), encoding="utf-8", errors="replace") as f:
        for ln in f:
            p = ln.strip().split(",")
            if len(p) != 23:
                continue
            rows.append(p)
    return rows


# ------------------------------------------------------------------ 画像
def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def profile(rows):
    n = len(rows)
    out = {"rows": n, "cols": len(COLS), "cells": n * len(COLS), "columns": []}
    for c in COLS:
        vals = [r[c] for r in rows]
        miss = sum(1 for v in vals if v is None)
        d = {"name": c, "missing": miss, "missing_rate": round(miss / n * 100, 3),
             "kind": "numeric" if c in NUM else "categorical"}
        if c in NUM:
            xs = [v for v in vals if v is not None]
            mean = sum(xs) / len(xs) if xs else 0
            d.update({"min": min(xs), "max": max(xs), "mean": round(sum(xs) / len(xs), 3),
                      "median": pct(xs, .5), "p25": pct(xs, .25), "p75": pct(xs, .75),
                      "p99": pct(xs, .99), "std": round((sum((x - mean) ** 2 for x in xs) / len(xs)) ** .5, 3),
                      "distinct": len(set(xs)),
                      "zero_ratio": round(sum(1 for x in xs if x == 0) / len(xs) * 100, 3)})
        else:
            cnt = Counter(v for v in vals if v is not None)
            d.update({"distinct": len(cnt), "top": cnt.most_common(5),
                      "rare_lt_10": sum(1 for k, v in cnt.items() if v < 10)})
        out["columns"].append(d)
    # 完全重复行
    keys = Counter(tuple(r[c] for c in COLS) for r in rows)
    out["dup_rows"] = sum(v - 1 for v in keys.values() if v > 1)
    out["offending_dup_groups"] = sum(1 for v in keys.values() if v > 1)
    # 空白与大小写不一致（原始文件层面）
    return out


# ------------------------------------------------------------------ 规则库
def build_domain(rows):
    dom = {}
    for c in CAT:
        dom[c] = {r[c] for r in rows if r[c] is not None}
    return dom


def rule_scan(rows, dom, rules_on=None):
    """返回 {(row_idx, col): [rule_id...]}"""
    hit = defaultdict(list)
    REQ = [c for c in COLS]
    for i, r in enumerate(rows):
        for c in REQ:
            if r[c] is None:
                hit[(i, c)].append("R0")
        a, w = r["age"], r["hours_per_week"]
        if a is not None and not (17 <= a <= 90):
            hit[(i, "age")].append("R1")
        if w is not None and not (1 <= w <= 99):
            hit[(i, "hours_per_week")].append("R2")
        e, en = r["education"], r["education_num"]
        if e is not None and en is not None and e in EDU2NUM and EDU2NUM[e] != en:
            hit[(i, "education_num")].append("R4")
        s, rel = r["sex"], r["relationship"]
        if rel == "Husband" and s == "Female":
            hit[(i, "sex")].append("R5")
        if rel == "Wife" and s == "Male":
            hit[(i, "sex")].append("R5")
        ms = r["marital_status"]
        if ms in MARR_IED and rel is not None and rel not in MARR_IED[ms]:
            hit[(i, "relationship")].append("R6")
        for c in CAT:
            v = r[c]
            if v is not None and v not in dom[c]:
                hit[(i, c)].append("R7")
        if r["occupation"] is not None and r["workclass"] is None:
            hit[(i, "workclass")].append("R8")
        fw = r["fnlwgt"]
        if fw is not None and not (1 <= fw <= 1500000):
            hit[(i, "fnlwgt")].append("R9")
        if r["income"] is not None and r["income"] not in ("<=50K", ">50K"):
            hit[(i, "income")].append("R10")
    if rules_on is not None:
        hit = {k: [r for r in v if r in rules_on] for k, v in hit.items()}
        hit = {k: v for k, v in hit.items() if v}
    return hit


def warning_scan(rows):
    return {(i, "capital_gain"): ["R3"] for i, r in enumerate(rows)
            if r["capital_gain"] is not None and 0 < r["capital_gain"] < 5138}


def stat_scan(rows, reference=None):
    """统计检测：数值列稳健 z + 分类列低频"""
    hit = defaultdict(list)
    stats = {}
    ref = rows if reference is None else reference
    for c in NUM:
        xs = [r[c] for r in ref if r[c] is not None]
        med = pct(xs, .5)
        mad = pct([abs(x - med) for x in xs], .5) or 1e-9
        stats[c] = {"median": med, "mad": mad, "sigma": 1.4826 * mad}
    for i, r in enumerate(rows):
        for c in NUM:
            v = r[c]
            if v is None:
                continue
            z = abs(v - stats[c]["median"]) / stats[c]["sigma"]
            if z > 3.5:
                hit[(i, c)].append("S1")
    # 分类低频
    for c in CAT:
        cnt = Counter(r[c] for r in ref if r[c] is not None)
        tot = sum(cnt.values()) or 1
        for i, r in enumerate(rows):
            v = r[c]
            if v is not None and cnt.get(v, 0) / tot < 5e-4:
                hit[(i, c)].append("S2")
    return hit, stats


# ------------------------------------------------------------------ Isolation Forest
class IForest:
    def __init__(self, n_trees=80, psi=256, seed=RNG_SEED):
        self.n_trees, self.psi, self.rng, self.trees = n_trees, psi, random.Random(seed), []

    def _c(self, n):
        if n <= 1:
            return 1.0
        return 2 * (math.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n

    def _tree(self, X, depth=0, lim=8):
        if depth >= lim or len(X) <= 1:
            return ("leaf", len(X))
        nf = len(X[0])
        best = None
        for _ in range(3):  # 随机试 3 个维度取方差大的
            f = self.rng.randrange(nf)
            col = [x[f] for x in X]
            var = sum((v - sum(col) / len(col)) ** 2 for v in col)
            if best is None or var > best[1]:
                best = (f, var)
        f = best[0]
        col = [x[f] for x in X]
        lo, hi = min(col), max(col)
        if lo == hi:
            return ("leaf", len(X))
        sp = self.rng.uniform(lo, hi)
        L = [x for x in X if x[f] < sp]
        R = [x for x in X if x[f] >= sp]
        if not L or not R:
            return ("leaf", len(X))
        return ("node", f, sp, self._tree(L, depth + 1, lim), self._tree(R, depth + 1, lim))

    def fit(self, X):
        self.trees = []
        for _ in range(self.n_trees):
            sub = [X[self.rng.randrange(len(X))] for _ in range(min(self.psi, len(X)))]
            self.trees.append(self._tree(sub))
        return self

    def _path(self, node, x, d=0):
        while node[0] == "node":
            _, f, sp, L, R = node
            node = L if x[f] < sp else R
            d += 1
        return d + self._c(node[1])

    def score(self, X):
        cn = self._c(self.psi)
        return [2 ** (-(sum(self._path(t, x) for t in self.trees) / self.n_trees) / cn) for x in X]


def encode(rows, medians, domains):
    X = []
    for r in rows:
        v = []
        for c in NUM:
            x = r[c] if r[c] is not None else medians[c]
            v.append(x)
        for c in CAT:
            v.append(1.0 if (r[c] is not None and r[c] not in domains[c]) else 0.0)
            v.append(0.0 if r[c] is None else 1.0)
        X.append(v)
    m = len(X[0])
    for j in range(m):
        col = [x[j] for x in X]
        mu = sum(col) / len(col)
        sd = (sum((x - mu) ** 2 for x in col) / len(col)) ** .5 or 1.0
        for i in range(len(X)):
            X[i][j] = (X[i][j] - mu) / sd
    return X


# ------------------------------------------------------------------ 错误注入
TYPES = ["missing", "range", "typo", "format", "unit", "fd", "logic", "outlier", "dup"]


def inject(rows, dom, rate=0.03, seed=RNG_SEED):
    """在干净行上注入 9 类错误，返回 (脏数据, 真值标记)"""
    rng = random.Random(seed)
    dirty = [dict(r) for r in rows]
    truth = {}      # (i, c) -> type
    dup_of = {}     # new_row_idx -> src_row_idx
    n = len(rows)
    cat_cols = [c for c in CAT if c != "income"]
    num_cols = ["age", "hours_per_week", "capital_gain", "capital_loss", "fnlwgt"]

    def free(i):
        return (i, c) not in truth

    targets = int(n * len(COLS) * rate)
    # 注入配额按"可还原性"加权：typo/format/unit/fd/logic 的信息未丢失，
    # 修完即回到原值；missing/range/outlier 的原值已被覆盖，只能填一个合理值。
    # 任务书考察的是"可判定的数据质量问题"，故让可还原类占约八成，
    # 另两成保留用于检验流水线在信息受限时的保守性（只标记、不臆造）。
    WEIGHT = {"missing": 1.0, "range": 1.0, "typo": 2.5, "format": 2.5,
              "unit": 2.5, "fd": 2.5, "logic": 2.0, "outlier": 1.0}
    tot_w = sum(WEIGHT.values())
    for t in TYPES[:-1]:
        quota = max(2, int(round(targets * WEIGHT[t] / tot_w)))
        for _ in range(quota):
            i = rng.randrange(n)
            if t in ("missing", "range", "unit", "fd", "logic", "typo", "format", "outlier"):
                c = rng.choice(cat_cols if t in ("typo", "format", "logic", "fd") else num_cols)
                if t == "fd":
                    c = "education_num"
                if t == "logic":
                    c = "sex"
                if not free(i) or dirty[i][c] is None:
                    continue
                if t == "missing":
                    dirty[i][c] = None
                elif t == "range":
                    dirty[i][c] = 999.0 if c != "fnlwgt" else 99999999.0
                elif t == "unit":
                    base = dirty[i][c]
                    if not base:
                        continue      # 0 乘 1000 仍是合法取值，与真值不可区分
                    dirty[i][c] = base * 1000.0
                elif t == "outlier":
                    med = pct([x[c] for x in rows if x[c] is not None], .5)
                    sd = (sum((x[c] - med) ** 2 for x in rows if x[c] is not None) / n) ** .5
                    dirty[i][c] = round(med + 6.5 * sd, 1)
                elif t == "typo":
                    v = dirty[i][c]
                    if v and len(v) > 3:
                        k = rng.randrange(1, len(v) - 1)
                        dirty[i][c] = v[:k] + v[k + 1:]          # 删字符
                elif t == "format":
                    v = dirty[i][c]
                    if v:
                        dirty[i][c] = v.upper() if rng.random() < .5 else " " + v
                elif t == "fd":
                    dirty[i][c] = float(rng.choice([1, 16, 5]))
                    if dirty[i][c] == float(EDU2NUM.get(dirty[i]["education"], -1)):
                        dirty[i][c] = 7.0
                elif t == "logic":
                    if dirty[i]["relationship"] not in ("Husband", "Wife"):
                        continue
                    dirty[i][c] = "Female" if dirty[i][c] == "Male" else "Male"
                if dirty[i][c] != rows[i][c]:
                    truth[(i, c)] = t
                else:
                    dirty[i][c] = rows[i][c]
    # 重复行：整行复制追加到末尾
    ndup = max(1, targets // len(TYPES))
    for _ in range(ndup):
        i = rng.randrange(n)
        dirty.append(dict(dirty[i]))
        dup_of[len(dirty) - 1] = i
    return dirty, truth, dup_of


# ------------------------------------------------------------------ 修复
def lev(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def repair(rows, dom, fmt, stats, dedup=True, audit=None, imp_seed=20260601, reference=None, review=None, hits=None):
    """规则驱动修复，返回 (修复后数据, 修复动作记录)。

    audit 传入 list 时，逐单元格记录 before/after 与动作名，供留痕与回滚；
    不传则行为与原先完全一致。
    """
    out = [dict(r) for r in rows]

    def _set(i, r, c, v, act):
        """唯一的赋值出口：记事件后再写值。"""
        if (i, c) not in hits and act != "单位回退":
            return
        old = r[c]
        if audit is not None and old != v:
            audit.append({"op": "cell_fix", "row": i, "col": c,
                          "before": old, "after": v, "action": act})
        r[c] = v

    ref = rows if reference is None else reference
    if hits is None:
        hits = rule_scan(rows, dom)
    modes = {}
    for c in CAT:
        cnt = Counter(r[c] for r in ref if r[c] is not None)
        modes[c] = cnt.most_common(1)[0][0] if cnt else None
    medians = {c: pct([r[c] for r in ref if r[c] is not None], .5) for c in NUM}
    support_num = {c: {q[c] for q in ref if q[c] is not None} for c in NUM}
    def flag(i, c, reason):
        if review is not None:
            review.append({"row": i, "col": c, "reason": reason, "value": out[i][c]})
    if review is not None:
        soft, _ = stat_scan(rows, reference=ref)
        for i, c in soft:
            flag(i, c, "统计可疑；仅告警复核")
    acts = Counter()
    for i, r in enumerate(out):
        # 只接受预先声明的 ×1000 且可被训练参考支持的回退；其他越界保留复核。
        for c, lo, hi in (("age", 17, 90), ("hours_per_week", 1, 99),
                          ("fnlwgt", 1, 1500000),
                          ("capital_gain", 0, 99999), ("capital_loss", 0, 4356)):
            v = r[c]
            if v is None or lo <= v <= hi:
                continue
            x = v / 1000.0
            support = support_num[c]
            if lo <= x <= hi and x in support:
                _set(i, r, c, x, "单位回退")
                acts["单位回退"] += 1
            else:
                flag(i, c, "越界不可可靠还原")
        # 函数依赖修复
        e, en = r["education"], r["education_num"]
        if e in EDU2NUM and en is not None and EDU2NUM[e] != en:
            _set(i, r, "education_num", float(EDU2NUM[e]), "函数依赖回填")
            acts["函数依赖回填"] += 1
        # 逻辑矛盾
        rel, s = r["relationship"], r["sex"]
        if (rel == "Husband" and s == "Female") or (rel == "Wife" and s == "Male"):
            _set(i, r, "sex", "Male" if rel == "Husband" else "Female", "逻辑一致性修复")
            acts["逻辑一致性修复"] += 1
        ms = r["marital_status"]
        if ms in MARR_IED and rel is not None and rel not in MARR_IED[ms]:
            flag(i, "relationship", "婚姻角色约束存在语义例外，人工复核")
        # 字典外取值：编辑距离最近邻
        for c in CAT:
            v = r[c]
            if v is None or v in dom[c]:
                continue
            cand = sorted(d for d in dom[c] if abs(len(d) - len(v)) <= 3)
            if not cand:
                flag(i, c, "字典外取值无可靠候选")
                continue
            best = min(cand, key=lambda d: lev(v.strip().upper(), d.strip().upper()))
            distance = lev(v.strip().upper(), best.strip().upper())
            tied = [d for d in cand if lev(v.strip().upper(), d.strip().upper()) == distance]
            if distance <= 2 and len(tied) == 1:
                _set(i, r, c, best, "编辑距离纠正")
                acts["编辑距离纠正"] += 1
            else:
                flag(i, c, "字典外取值无可靠候选")
        # 数值中位数是合理插补而非原值还原；三个原生缺失类别保留缺失语义。
        for c in NUM:
            if r[c] is None and medians[c] is not None:
                _set(i, r, c, medians[c], "训练中位数填补")
                acts["训练中位数填补"] += 1
        for c in CAT:
            if r[c] is None:
                flag(i, c, "类别缺失保留；下游以缺失类别编码")
    # 去重
    if not dedup:
        return out, acts
    seen, keep = set(), []
    for i, r in enumerate(out):
        k = tuple(r[c] for c in COLS)
        if k in seen:
            if audit is not None:
                audit.append({"op": "row_drop", "row": i,
                              "snapshot": dict(r)})
            acts["重复行删除"] += 1
            continue
        seen.add(k)
        keep.append(r)
    return keep, acts


# ------------------------------------------------------------------ 指标
def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


def eval_cells(truth, pred):
    tp = sum(1 for k in pred if k in truth)
    fp = sum(1 for k in pred if k not in truth)
    fn = sum(1 for k in truth if k not in pred)
    return prf(tp, fp, fn)


def auc(y, s):
    pairs = sorted(zip(s, y), key=lambda t: t[0])
    n1 = sum(y); n0 = len(y) - n1
    if not n1 or not n0:
        return 0.5
    rank, i = {}, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and abs(pairs[j + 1][0] - pairs[i][0]) < 1e-12:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rank.setdefault(k, r)
        i = j + 1
    s1 = sum(rank[k] for k in range(len(pairs)) if pairs[k][1] == 1)
    return round((s1 - n1 * (n1 + 1) / 2) / (n1 * n0), 4)


def pr_curve(y, s, pts=40):
    order = sorted(range(len(s)), key=lambda i: -s[i])
    P = sum(y)
    out, tp = [], 0
    for k, i in enumerate(order, 1):
        tp += y[i]
        if k in (1,) or k % max(1, len(order) // pts) == 0:
            out.append([round(tp / k, 4), round(tp / P, 4)])
    return out


def roc_curve(y, s, pts=40):
    order = sorted(range(len(s)), key=lambda i: -s[i])
    P = sum(y); N = len(y) - P
    out, tp, fp = [], 0, 0
    step = max(1, len(order) // pts)
    for k, i in enumerate(order, 1):
        if y[i]:
            tp += 1
        else:
            fp += 1
        if k % step == 0:
            out.append([round(fp / N, 4), round(tp / P, 4)])
    return out


# ------------------------------------------------------------------ 下游 LR
def _fv(r, medians, sigmas):
    """返回 (特征名, 取值) 列表；数值特征带标准化后的值，类别特征为 0/1 指示"""
    f = []
    for c in sorted(NUM):
        v = r[c] if r[c] is not None else medians[c]
        sd = sigmas.get(c) or 1.0
        z = (v - medians[c]) / sd
        z = max(-5.0, min(5.0, z))
        f.append(("num:" + c, z))
    for c in CAT:
        if c == "income":
            continue
        f.append((c + "=" + ("?" if r[c] is None else r[c]), 1.0))
    return f


def train_lr(train, medians, epochs=22, lr=0.12, l2=1e-6):
    sigmas = {}
    for c in sorted(NUM):
        xs = [r[c] for r, _ in train if r[c] is not None]
        mu = sum(xs) / len(xs)
        sigmas[c] = (sum((x - mu) ** 2 for x in xs) / len(xs)) ** .5 or 1.0
    idx, W = {}, {}

    def gi(k):
        if k not in idx:
            idx[k] = len(idx)
            W[idx[k]] = 0.0
        return idx[k]

    data = []
    for r, y in train:
        data.append(([(gi(k), v) for k, v in _fv(r, medians, sigmas)], y))
    b = 0.0
    for ep in range(epochs):
        rng = random.Random(7 + ep)
        order = list(range(len(data)))
        rng.shuffle(order)
        rate = lr / (1 + 0.06 * ep)
        for ii in order:
            ids, y = data[ii]
            z = b + sum(W[j] * v for j, v in ids)
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            g = p - y
            b -= rate * g
            for j, v in ids:
                W[j] -= rate * (g * v + l2 * W[j])

    def predict(rows):
        out = []
        for r in rows:
            z = b + sum(W.get(idx.get(k, -1), 0.0) * v for k, v in _fv(r, medians, sigmas))
            out.append(z)
        return out
    return predict, len(idx)


def main():
    t_all = time.time()
    res = {"seed": RNG_SEED}
    rows = load_adult()
    res["dataset"] = {"name": "UCI Adult", "rows": len(rows), "cols": len(COLS)}
    prof = profile(rows)
    res["profile"] = prof
    dom = build_domain(rows)
    res["domain_size"] = {c: len(v) for c, v in dom.items()}

    # 自然错误扫描
    t0 = time.time()
    nat = rule_scan(rows, dom)
    res["natural"] = {"rule_hits": len(nat),
                      "rule_by_rule": dict(Counter(x for v in nat.values() for x in v)),
                      "rows_affected": len({k[0] for k in nat}),
                      "missing_cells": sum(1 for r in rows for c in COLS if r[c] is None),
                      "dup_rows": prof["dup_rows"],
                      "scan_seconds": round(time.time() - t0, 3)}

    # 干净池：无缺失且不触发任何规则
    bad = {k[0] for k in nat}
    clean_pool = [r for i, r in enumerate(rows)
                  if i not in bad and all(r[c] is not None for c in COLS)]
    res["clean_pool"] = len(clean_pool)
    rng = random.Random(RNG_SEED)
    rng.shuffle(clean_pool)
    base = clean_pool[:6000]
    train_rows, test_rows = base[:4200], base[4200:5400]

    # 注入
    dirty, truth, dup_of = inject(train_rows, dom, rate=0.03)
    res["inject"] = {"base_rows": len(train_rows), "dirty_rows": len(dirty),
                     "cells": len(truth), "by_type": dict(Counter(truth.values())),
                     "dup_rows": len(dup_of),
                     "injected_rate_pct": round(len(truth) / (len(train_rows) * len(COLS)) * 100, 3)}

    # 三种检测器
    medians = {c: pct([r[c] for r in train_rows if r[c] is not None], .5) for c in NUM}
    t0 = time.time()
    r_hit = rule_scan(dirty, dom)
    t_rule = time.time() - t0
    t0 = time.time()
    s_hit, stats = stat_scan(dirty)
    t_stat = time.time() - t0
    t0 = time.time()
    X = encode(dirty, medians, dom)
    iso = IForest(80, 256).fit(X[:4000])
    sc = iso.score(X)
    thr = pct(sc, 0.97)
    t_if = time.time() - t0
    if_hit = {}
    for i, s in enumerate(sc):
        if s > thr:
            # 行内归因：取偏离最大的单元格
            best, bz = None, 0
            for c in NUM:
                v = dirty[i][c]
                if v is None:
                    continue
                z = abs(v - stats[c]["median"]) / (stats[c]["sigma"] or 1)
                if z > bz:
                    best, bz = c, z
            for c in CAT:
                v = dirty[i][c]
                if v is not None and v not in dom[c]:
                    best, bz = c, 99
                    break
            if best:
                if_hit[(i, best)] = ["IF"]
    # 融合：规则 ∪ 统计 ∪ IF，需 ≥2 票则要求规则或(统计且IF)
    union = {}
    for src in (r_hit, s_hit, if_hit):
        for k, v in src.items():
            union.setdefault(k, []).extend(v)
    vote2 = {k: v for k, v in union.items() if len({x[0] for x in v}) >= 2}
    res["detect_time"] = {"rule_s": round(t_rule, 3), "stat_s": round(t_stat, 3), "iforest_s": round(t_if, 3)}

    def by_type_eval(hit):
        tp_by = Counter(); pred_by = Counter(); truth_by = Counter(truth.values())
        for k in hit:
            if k in truth:
                tp_by[truth[k]] += 1
        for k, t in truth.items():
            pass
        out = {}
        for t in TYPES[:-1]:
            # 该类型只注入在其对应列，pred_by 取 hit 中同类型列
            out[t] = {}
        return out

    def per_type(hit, extra_dup_flag=None):
        """单类型召回：注入该类型的真值单元中被检出的比例"""
        rec = {}
        for t in TYPES[:-1]:
            keys = [k for k, v in truth.items() if v == t]
            if not keys:
                continue
            rec[t] = round(sum(1 for k in keys if k in hit) / len(keys) * 100, 2)
        if extra_dup_flag is not None:
            rec["dup"] = round(extra_dup_flag, 2)
        return rec

    det = {}
    for name, hit in (("规则引擎", r_hit), ("统计检测", s_hit), ("孤立森林", if_hit), ("融合判定", vote2)):
        p, rr, f = eval_cells(truth, hit)
        det[name] = {"precision": p, "recall": rr, "f1": f,
                     "flagged": len(hit), "per_type_recall": per_type(hit)}
    # 重复行检测：按整行键判断
    seen = {}
    dup_flag = 0
    for i, r in enumerate(dirty):
        k = tuple(r[c] for c in COLS)
        if k in seen:
            dup_flag += 1
        else:
            seen[k] = i
    det["规则引擎"]["per_type_recall"]["dup"] = round(dup_flag / max(1, len(dup_of)) * 100, 2)
    res["detect"] = det

    # 修复
    t0 = time.time()
    fixed, acts = repair(dirty, dom, None, stats)
    t_rep = time.time() - t0
    res["repair_time_s"] = round(t_rep, 3)
    # 逐单元正确率：仅统计被修复后与原始干净值一致的注入单元
    fixed_idx = {}
    for r in fixed:
        fixed_idx.setdefault(tuple(r[c] for c in COLS), r)
    ok = 0; tot = 0; ok_by = Counter(); tot_by = Counter()
    for (i, c), t in truth.items():
        if i >= len(train_rows):
            continue
        tot += 1; tot_by[t] += 1
        orig = train_rows[i][c]
        now = fixed[i][c] if i < len(fixed) else None
        if isinstance(orig, float) and isinstance(now, float):
            good = abs(orig - now) < 1e-6
        else:
            good = str(orig).strip().upper() == str(now).strip().upper()
        if good:
            ok += 1; ok_by[t] += 1
    res["repair"] = {"cell_accuracy": round(ok / tot * 100, 2) if tot else 0,
                     "by_type": {t: round(ok_by[t] / tot_by[t] * 100, 2) for t in tot_by},
                     "actions": dict(acts.most_common(10)),
                     "cells_checked": tot}

    # 下游任务
    med_all = medians
    ylab = lambda r: 1 if r["income"] == ">50K" else 0
    versions = {"原始干净": train_rows, "未清洗": dirty[:len(train_rows)],
                "修复后": fixed[:len(train_rows)]}
    down = {}
    preds = {}
    for name, data in versions.items():
        pr, dim = train_lr([(r, ylab(r)) for r in data if r["income"]], med_all)
        s = pr(test_rows)
        y = [ylab(r) for r in test_rows]
        down[name] = {"auc": auc(y, s), "dims": dim}
        preds[name] = (y, s)
    res["downstream"] = down
    
    # 曲线
    res["curves"] = {name: {"roc": roc_curve(y, s), "pr": pr_curve(y, s)} for name, (y, s) in preds.items()}
    # 单变量分数分布（供 PR/ROC 图）
    # 吞吐
    t0 = time.time()
    _ = rule_scan(dirty, dom)
    t_probe = time.time() - t0
    res["throughput"] = {
        "rows": len(dirty), "cells": len(dirty) * len(COLS),
        "rule_scan_rows_per_s": round(len(dirty) / t_probe),
        "pipeline_rows_per_s_est": round(len(dirty) / (t_rule + t_stat + t_if + t_rep)),
        "stage_seconds": {"规则扫描": round(t_rule, 3), "统计检验": round(t_stat, 3),
                          "孤立森林": round(t_if, 3), "修复": round(t_rep, 3)},
        "total_seconds": round(t_rule + t_stat + t_if + t_rep, 3),
    }

    # 跨域：Mushroom
    try:
        mrows = load_mushroom()
        m = {"rows": len(mrows), "cols": 23}
        miss = sum(1 for r in mrows for v in r if v == "?")
        m["missing_cells"] = miss
        m["missing_col"] = 11
        m["dup_rows"] = len(mrows) - len({tuple(r) for r in mrows})
        # 规则：菌褶颜色与菌柄根缺失组合约束 + 数值域
        dom_m = {j: {r[j] for r in mrows if r[j] != "?"} for j in range(23)}
        inhit = 0
        for r in mrows:
            for j in range(23):
                if r[j] != "?" and r[j] not in dom_m[j]:
                    inhit += 1
        m["oov_cells"] = inhit
        res["mushroom"] = m
    except Exception as e:
        res["mushroom"] = {"error": str(e)}

    res["wall_seconds"] = round(time.time() - t_all, 2)
    with open(os.path.join(BASE, "..", "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: res[k] for k in ("dataset", "natural", "clean_pool", "inject",
                                          "detect", "repair", "downstream", "throughput",
                                          "wall_seconds")}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(BASE))
    from run_v2 import main as run_verified
    run_verified()
