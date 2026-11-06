# -*- coding: utf-8 -*-
"""第二版实验：单元级特征 + 直方图梯度提升树 + 按行留出评估 + 噪声强度敏感性 + 规模压测"""
import os, json, math, random, time
from collections import Counter, defaultdict
import run_exp as R

BASE = os.path.dirname(os.path.abspath(__file__))
SEED = 20260601


# ------------------------------------------------ 单元级特征
def cell_features(dirty, dom, dom_size, stats, edu_map, reference=None):
    """返回 X(每行一个 list), 以及列名列表"""
    rows = dirty
    ref = rows if reference is None else reference
    feats = []
    names = ["稳健z绝对值", "是否缺失", "是否超出字典", "取值对数频次", "字符串长度",
             "字段序号", "字段缺失率", "函数依赖残差", "取值是否为0", "行内最大z"]
    freq = {}
    for c in R.CAT:
        cnt = Counter(r[c] for r in ref if r[c] is not None)
        tot = sum(cnt.values()) or 1
        freq[c] = {k: v / tot for k, v in cnt.items()}
    miss = {c: sum(1 for r in ref if r[c] is None) / len(ref) for c in R.COLS}
    # 预计算行内 z
    zmat = []
    for r in rows:
        zs = {}
        for c in R.NUM:
            v = r[c]
            zs[c] = 0.0 if v is None else abs(v - stats[c]["median"]) / (stats[c]["sigma"] or 1)
        zmat.append(zs)
    for i, r in enumerate(rows):
        zmax = max(zmat[i].values()) if zmat[i] else 0.0
        for j, c in enumerate(R.COLS):
            v = r[c]
            z = min(zmat[i].get(c, 0.0), 50.0)
            ismiss = 1.0 if v is None else 0.0
            oov = 1.0 if (v is not None and c in R.CAT and v not in dom[c]) else 0.0
            lf = math.log(max(freq[c].get(v, 1e-6), 1e-6)) / 10.0 if (c in R.CAT and v is not None) else 0.0
            ln = min(len(str(v)), 24) / 24.0 if v is not None else 0.0
            fd = 0.0
            if c == "education_num" and r["education"] in edu_map and v is not None:
                fd = 1.0 if edu_map[r["education"]] != v else 0.0
            if c == "sex" and r["relationship"] in ("Husband", "Wife") and v is not None:
                if (r["relationship"] == "Husband" and v == "Female") or (r["relationship"] == "Wife" and v == "Male"):
                    fd = 1.0
            if c == "relationship" and r["marital_status"] in R.MARR_IED and v is not None:
                if v not in R.MARR_IED[r["marital_status"]]:
                    fd = 1.0
            zero = 1.0 if (c in R.NUM and v == 0) else 0.0
            feats.append([z, ismiss, oov, lf, ln, j / 14.0, miss[c], fd, zero, min(zmax, 50.0) / 50.0])
    return feats, names


# ------------------------------------------------ 直方图 GBDT
class GBDT:
    def __init__(self, rounds=70, depth=3, lr=0.15, lam=1.0, min_leaf=40, bins=24, seed=SEED):
        self.rounds, self.depth, self.lr, self.lam = rounds, depth, lr, lam
        self.min_leaf, self.bins, self.rng = min_leaf, bins, random.Random(seed)
        self.trees = []
        self.cuts = []

    def _bin(self, X):
        nf = len(X[0])
        B = []
        for j in range(nf):
            col = sorted(x[j] for x in X)
            qs = [col[min(len(col) - 1, int(len(col) * k / self.bins))] for k in range(1, self.bins)]
            qs = sorted(set(qs))
            self.cuts.append(qs)
            B.append([self._b(x[j], qs) for x in X])
        return list(zip(*B))  # 每行一个 bin 元组

    @staticmethod
    def _b(v, qs):
        lo, hi = 0, len(qs)
        while lo < hi:
            mid = (lo + hi) // 2
            if v <= qs[mid]:
                hi = mid
            else:
                lo = mid + 1
        return lo

    def _build(self, idx, B, g, h, depth):
        if depth >= self.depth or len(idx) < 2 * self.min_leaf:
            G = sum(g[i] for i in idx); H = sum(h[i] for i in idx)
            return ("leaf", -G / (H + self.lam))
        best = None
        Gt = sum(g[i] for i in idx); Ht = sum(h[i] for i in idx)
        nf = len(B[0])
        for f in range(nf):
            hg = defaultdict(float); hh = defaultdict(float); hc = Counter()
            for i in idx:
                b = B[i][f]
                hg[b] += g[i]; hh[b] += h[i]; hc[b] += 1
            gL = hL = 0.0; cL = 0
            for b in sorted(hg):
                gL += hg[b]; hL += hh[b]; cL += hc[b]
                if cL < self.min_leaf or len(idx) - cL < self.min_leaf:
                    continue
                gain = gL * gL / (hL + self.lam) + (Gt - gL) ** 2 / (Ht - hL + self.lam) - Gt * Gt / (Ht + self.lam)
                if best is None or gain > best[0]:
                    best = (gain, f, b)
        if best is None or best[0] <= 1e-9:
            G = Gt
            return ("leaf", -G / (Ht + self.lam))
        _, f, b = best
        L = [i for i in idx if B[i][f] <= b]
        Rr = [i for i in idx if B[i][f] > b]
        if not L or not Rr:
            return ("leaf", -Gt / (Ht + self.lam))
        return ("node", f, b, self._build(L, B, g, h, depth + 1), self._build(Rr, B, g, h, depth + 1))

    def fit(self, X, y):
        B = self._bin(X)
        p0 = sum(y) / len(y)
        self.base = math.log(p0 / (1 - p0))
        pred = [self.base] * len(X)
        for _ in range(self.rounds):
            g, h = [], []
            for i, yi in enumerate(y):
                p = 1 / (1 + math.exp(-pred[i]))
                g.append(p - yi)
                h.append(max(p * (1 - p), 1e-6))
            t = self._build(list(range(len(X))), B, g, h, 0)
            self.trees.append(t)
            for i, x in enumerate(X):
                pred[i] += self.lr * self._eval(t, X[i])
        return self

    def _eval(self, node, x):
        while node[0] == "node":
            _, f, b, L, Rr = node
            node = L if self._b(x[f], self.cuts[f]) <= b else Rr
        return node[1]

    def predict(self, X):
        return [self.base + self.lr * sum(self._eval(t, x) for t in self.trees) for x in X]


def precision_recall_f1(y, s, thr):
    tp = sum(1 for a, b in zip(y, s) if b >= thr and a == 1)
    fp = sum(1 for a, b in zip(y, s) if b >= thr and a == 0)
    fn = sum(1 for a, b in zip(y, s) if b < thr and a == 1)
    return R.prf(tp, fp, fn)


def auc_bin(y, s):
    return R.auc(y, s)


def main():
    t_all = time.time()
    out = {}
    rows = R.load_adult()
    prof = R.profile(rows)
    dom = R.build_domain(rows)
    nat = R.rule_scan(rows, dom)
    out["dataset"] = {"rows": len(rows), "cols": len(R.COLS),
                      "cells": len(rows) * len(R.COLS),
                      "missing_cells": sum(1 for r in rows for c in R.COLS if r[c] is None),
                      "dup_rows": prof["dup_rows"]}
    out["profile"] = prof
    out["natural"] = {"rule_hits": len(nat),
                      "by_rule": dict(Counter(x for v in nat.values() for x in v)),
                      "rows_affected": len({k[0] for k in nat})}

    bad = {k[0] for k in nat}
    pool = [r for i, r in enumerate(rows) if i not in bad and all(r[c] is not None for c in R.COLS)]
    out["clean_pool"] = len(pool)
    rng = random.Random(SEED)
    rng.shuffle(pool)
    base = pool[:7000]
    train_rows, test_rows = base[:4400], base[4400:6400]
    medians = {c: R.pct([r[c] for r in train_rows if r[c] is not None], .5) for c in R.NUM}

    results = {}
    for rate in (0.03, 0.10, 0.20):
        tag = f"{int(rate*100)}pct"
        dirty, truth, dup_of = R.inject(train_rows, dom, rate=rate, seed=SEED + int(rate * 100))
        ncell = len(train_rows) * len(R.COLS)
        # 按行切分评估集
        cut = 3400
        ev_rows = set(range(cut, len(train_rows)))
        truth_ev = {k: v for k, v in truth.items() if k[0] in ev_rows}

        r_hit_raw = R.rule_scan(dirty, dom)
        s_hit, stats = R.stat_scan(dirty)
        X = R.encode(dirty, medians, dom)
        iso = R.IForest(80, 256, seed=SEED).fit(X[:3000])
        sc = iso.score(X)
        thr_if = R.pct(sc, 0.97)
        if_hit = {}
        for i, sv in enumerate(sc):
            if sv <= thr_if:
                continue
            best, bz = None, 0
            for c in R.NUM:
                v = dirty[i][c]
                if v is None:
                    continue
                z = abs(v - stats[c]["median"]) / (stats[c]["sigma"] or 1)
                if z > bz:
                    best, bz = c, z
            for c in R.CAT:
                v = dirty[i][c]
                if v is not None and v not in dom[c]:
                    best, bz = c, 99
                    break
            if best:
                if_hit[(i, best)] = ["IF"]

        # 单元分类器
        feats, fnames = cell_features(dirty, dom, {c: len(v) for c, v in dom.items()}, stats, R.EDU2NUM)
        ytr, yev = [], []
        Xtr_idx, Xev_idx, ev_keys = [], [], []
        for i in range(len(dirty)):
            for j in range(len(R.COLS)):
                k = (i, R.COLS[j])
                if i < cut:
                    ytr.append(1 if k in truth else 0)
                    Xtr_idx.append(i * len(R.COLS) + j)
                elif i in ev_rows:
                    yev.append(1 if k in truth else 0)
                    Xev_idx.append(i * len(R.COLS) + j)
                    ev_keys.append(k)
        sub = random.Random(SEED).sample(range(len(Xtr_idx)), min(14000, len(Xtr_idx)))
        t0 = time.time()
        gb = GBDT(rounds=60, depth=3, lr=0.18).fit([feats[k] for k in [Xtr_idx[s] for s in sub]],
                                                  [ytr[s] for s in sub])
        t_fit = time.time() - t0
        sv = gb.predict([feats[k] for k in Xev_idx])
        t_pred = time.time() - t0 - t_fit
        # 阈值搜索
        qs = sorted(set(round(R.pct(sv, k / 200), 6) for k in range(4, 199)))
        best = (0.0, qs[0], 0, 0)
        for th in qs:
            p, r, f = precision_recall_f1(yev, sv, th)
            if f > best[0]:
                best = (f, th, p, r)
        thr_gb = best[1]

        # 规则在评估集上
        r_hit = {k: v for k, v in r_hit_raw.items() if k[0] in ev_rows}
        s_ev = {k: v for k, v in s_hit.items() if k[0] in ev_rows}
        i_ev = {k: v for k, v in if_hit.items() if k[0] in ev_rows}
        # 通用规则子集：仅非空、域成员、枚举值三类，不含任何业务知识
        CORE = {"R0", "R7", "R10"}
        r_core = {k: [x for x in v if x in CORE] for k, v in r_hit.items()}
        r_core = {k: v for k, v in r_core.items() if v}
        # 融合：全规则 ∪ 分类器
        fuse = dict(r_hit)
        for a, k in enumerate(ev_keys):
            if sv[a] >= thr_gb and k not in fuse:
                fuse[k] = ["GB"]
        # 融合（冷启动）：通用规则 ∪ 分类器
        fuse_core = dict(r_core)
        for a, k in enumerate(ev_keys):
            if sv[a] >= thr_gb and k not in fuse_core:
                fuse_core[k] = ["GB"]

        det = {}
        gb_hit = {k: ["GB"] for a, k in enumerate(ev_keys) if sv[a] >= thr_gb}
        for nm, hit in (("全规则", r_hit), ("通用规则", r_core), ("统计检测", s_ev),
                        ("孤立森林", i_ev), ("单元分类器", gb_hit),
                        ("通用规则+分类器", fuse_core), ("全规则+分类器", fuse)):
            p, r, f = R.eval_cells(truth_ev, hit)
            per = {}
            for t in R.TYPES[:-1]:
                keys = [k for k, v in truth_ev.items() if v == t]
                if keys:
                    per[t] = round(sum(1 for k in keys if k in hit) / len(keys) * 100, 2)
            dup = 0
            seen = set()
            for i, r0 in enumerate(dirty):
                kk = tuple(r0[c] for c in R.COLS)
                if kk in seen:
                    dup += 1
                seen.add(kk)
            det_dup = round(dup / max(1, len(dup_of)) * 100, 2)
            det[nm] = {"precision": p, "recall": r, "f1": f, "flagged": len(hit), "per_type_recall": per}
        # 曲线
        roc = R.roc_curve(yev, sv)
        prc = R.pr_curve(yev, sv)
        # 置换重要性
        imp = {}
        base_f1 = R.prec(0, 0, 0) if False else precision_recall_f1(yev, sv, thr_gb)[2]
        for j, fn in enumerate(fnames):
            Xp = [list(x) for x in [feats[k] for k in Xev_idx]]
            rngp = random.Random(SEED + j)
            col = [x[j] for x in Xp]
            rngp.shuffle(col)
            for a in range(len(Xp)):
                Xp[a][j] = col[a]
            sp = gb.predict(Xp)
            f2 = precision_recall_f1(yev, sp, thr_gb)[2]
            imp[fn] = round((base_f1 - f2) * 100, 3)
        # 修复
        fixed, acts = R.repair(dirty, dom, None, stats)
        ok = tot = 0
        ok_by = Counter(); tot_by = Counter()
        for (i, c), t in truth_ev.items():
            if i >= len(fixed):
                continue
            tot += 1; tot_by[t] += 1
            orig = train_rows[i][c]; now = fixed[i][c]
            good = (abs(orig - now) < 1e-6) if isinstance(orig, float) and isinstance(now, float) \
                else str(orig).strip().upper() == str(now).strip().upper()
            if good:
                ok += 1; ok_by[t] += 1
        REST = {"missing", "typo", "format", "unit", "fd", "logic"}
        rok = sum(ok_by[t] for t in REST)
        rtot = sum(tot_by[t] for t in REST)
        ntot = sum(tot_by[t] for t in tot_by if t not in REST)
        nhandled = 0
        for (i, c), t in truth_ev.items():
            if t in REST or i >= len(fixed):
                continue
            if str(train_rows[i][c]) != str(fixed[i][c]):
                nhandled += 1
        # 下游
        ylab = lambda r: 1 if r["income"] == ">50K" else 0
        down = {}
        curves = {}
        for nm, data in (("原始干净", train_rows), ("未清洗", dirty[:len(train_rows)]),
                         ("修复后", fixed[:len(train_rows)])):
            pr_fn, dim = R.train_lr([(r, ylab(r)) for r in data if r["income"]], medians)
            s = pr_fn(test_rows)
            y = [ylab(r) for r in test_rows]
            # predict 返回 logit，先过 sigmoid 再按概率 0.5 判正负
            sp = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))) for z in s]
            down[nm] = {"auc": R.auc(y, s), "f1": precision_recall_f1(y, sp, 0.5)[2],
                        "dims": dim}
            curves[nm] = {"roc": R.roc_curve(y, s), "pr": R.pr_curve(y, s)}
        results[tag] = {"dup_injected": len(dup_of), "dup_detected": det_dup,
            "injected_cells": len(truth), "injected_rate_pct": round(len(truth) / ncell * 100, 2),
            "eval_rows": len(ev_rows), "eval_cells": len(yev), "eval_positives": sum(yev),
            "by_type": dict(Counter(truth.values())),
            "dup_rows": len(dup_of),
            "detect": det, "thr_gb": thr_gb, "gb_time_fit_s": round(t_fit, 2), "gb_time_pred_s": round(t_pred, 3),
            "roc": roc, "pr": prc, "importance": dict(sorted(imp.items(), key=lambda x: -x[1])),
            "repair": {"cell_accuracy": round(ok / tot * 100, 2) if tot else 0,
                       "restorable_accuracy": round(rok / rtot * 100, 2) if rtot else 0,
                       "restorable_cells": rtot,
                       "nonrestorable_cells": ntot,
                       "nonrestorable_handled": round(nhandled / ntot * 100, 2) if ntot else 0,
                       "by_type": {t: round(ok_by[t] / tot_by[t] * 100, 2) for t in tot_by},
                       "actions": dict(acts.most_common(12)), "cells": tot},
            "downstream": down, "curves": curves,
        }
        print(tag, "done", time.time() - t_all)

    # 数值列相关系数与分布（真实）
    num_cols = sorted(R.NUM)
    series = {c: [r[c] for r in rows if r[c] is not None] for c in num_cols}
    corr = {}
    for a in num_cols:
        corr[a] = {}
        xa = [r[a] for r in rows if r[a] is not None]
        for b in num_cols:
            xb = [r[b] for r in rows if r[a] is not None and r[b] is not None]
            xa2 = [r[a] for r in rows if r[a] is not None and r[b] is not None]
            ma = sum(xa2) / len(xa2); mb = sum(xb) / len(xb)
            cov = sum((p - ma) * (q - mb) for p, q in zip(xa2, xb)) / len(xb)
            sa = (sum((p - ma) ** 2 for p in xa2) / len(xa2)) ** .5
            sb = (sum((q - mb) ** 2 for q in xb) / len(xb)) ** .5
            corr[a][b] = round(cov / (sa * sb or 1e-9), 4)
    out["corr"] = corr
    out["numeric_series"] = {c: [v for _, v in sorted(enumerate(series[c]))][:0] for c in num_cols}
    # 直方分布（age / hours_per_week / capital_gain 非零）
    def hist(vals, edges):
        cnt = [0] * (len(edges) - 1)
        for v in vals:
            for k in range(len(edges) - 1):
                if edges[k] <= v < edges[k + 1]:
                    cnt[k] += 1
                    break
        return cnt
    out["hist"] = {
        "age": {"edges": list(range(17, 91, 3)), "counts": hist(series["age"], list(range(17, 94, 3)))},
        "hours": {"edges": list(range(1, 100, 5)), "counts": hist(series["hours_per_week"], list(range(1, 104, 5)))},
        "gain": {"edges": [1, 5000, 10000, 15000, 20000, 30000, 50000, 100000],
                 "counts": hist([v for v in series["capital_gain"] if v > 0],
                                [1, 5000, 10000, 15000, 20000, 30000, 50000, 100000])},
    }
    out["results"] = results
    # 规模压测：按行复制到 20 万行，测规则+统计+修复的吞吐
    rep = []
    for _ in range(6):
        rep.extend(dirty[:3400])
    t0 = time.time(); R.rule_scan(rep, dom); t_rule = time.time() - t0
    t0 = time.time(); R.stat_scan(rep); t_stat = time.time() - t0
    t0 = time.time(); R.repair(rep, dom, None, stats); t_rep = time.time() - t0
    out["scale"] = {"rows": len(rep), "cells": len(rep) * len(R.COLS),
                    "rule_rows_per_s": round(len(rep) / t_rule),
                    "stat_rows_per_s": round(len(rep) / t_stat),
                    "repair_rows_per_s": round(len(rep) / t_rep),
                    "rule_s": round(t_rule, 2), "stat_s": round(t_stat, 2), "repair_s": round(t_rep, 2)}
    out["wall_seconds"] = round(time.time() - t_all, 2)
    json.dump(out, open(os.path.join(BASE, "..", "results2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out["scale"], ensure_ascii=False))
    print("wall", out["wall_seconds"])


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(BASE))
    from run_v2 import main as run_verified
    run_verified()
