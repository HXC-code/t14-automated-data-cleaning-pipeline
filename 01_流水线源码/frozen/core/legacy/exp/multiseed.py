# -*- coding: utf-8 -*-
"""下游任务的多种子评估：5 次独立划分 × 3 档注入强度。

单次划分的 F1 波动可达 ±2 个百分点，不足以支撑"提升不少于 3 个百分点"的结论。
本脚本固定阈值 0.5、固定训练/测试规模，仅改变划分与注入的随机种子，报告
均值与标准差，用于判断提升是否稳定。

用法: python exp/multiseed.py
输出: multiseed.json
"""
import json
import math
import os
import random
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import run_exp as R

OUT = os.path.join(BASE, "..", "multiseed.json")
SEEDS = [20260601, 20260602, 20260603, 20260604, 20260605]
RATES = [(0.03, "3pct"), (0.10, "10pct"), (0.20, "20pct")]
N_TRAIN, N_VAL, N_TEST = 8000, 0, 12000


def f1_of(y, s, thr=0.5):
    tp = sum(1 for a, b in zip(y, s) if b >= thr and a == 1)
    fp = sum(1 for a, b in zip(y, s) if b >= thr and a == 0)
    fn = sum(1 for a, b in zip(y, s) if b < thr and a == 1)
    return R.prf(tp, fp, fn)[2]


def best_thr(y, s, lo=0.05, hi=0.95, step=0.01):
    """在干净验证集上选 F1 最大化的判定阈值。

    脏数据训练出的模型概率分布会整体偏移，固定 0.5 会把这种偏移算进 F1，
    与分类能力本身无关。三个模型（干净/未清洗/修复后）用同一份验证集、
    同一套搜法，口径一致。
    """
    best, bt = -1.0, 0.5
    t = lo
    while t <= hi + 1e-9:
        f = f1_of(y, s, t)
        if f > best:
            best, bt = f, round(t, 2)
        t += step
    return bt, best


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def std(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def main():
    t0 = time.time()
    base = R.load_adult()
    print("载入 %d 行" % len(base))
    dom = R.build_domain(base)
    ylab = lambda r: 1 if r["income"] == ">50K" else 0

    out = {"seeds": SEEDS, "n_train": N_TRAIN, "n_val": N_VAL, "n_test": N_TEST,
           "threshold": 0.5, "by_rate": {}}

    for rate, tag in RATES:
        rows = []
        for seed in SEEDS:
            rng = random.Random(seed)
            pool = list(base)
            rng.shuffle(pool)
            train_rows = pool[:N_TRAIN]
            test_rows = pool[N_TRAIN:N_TRAIN + N_TEST]
            medians = {c: R.pct([r[c] for r in train_rows if r[c] is not None], .5)
                       for c in R.NUM}

            dirty, truth, dup_of = R.inject(train_rows, dom, rate=rate,
                                            seed=seed + int(rate * 100))
            audit = []
            fixed, acts = R.repair(dirty, dom, None, None, audit=audit)

            y = [ylab(r) for r in test_rows]
            rec = {"seed": seed, "injected_cells": len(truth),
                   "audit_events": len(audit),
                   "n_after_repair": len(fixed)}
            for nm, data in (("干净", train_rows),
                             ("未清洗", dirty[:len(train_rows)]),
                             ("修复后", fixed[:len(train_rows)])):
                pr_fn, dim = R.train_lr(
                    [(r, ylab(r)) for r in data if r["income"]], medians)
                s = pr_fn(test_rows)
                sp = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))) for z in s]
                rec["auc_" + nm] = round(R.auc(y, s), 4)
                rec["f1_" + nm] = round(f1_of(y, sp), 4)
                rec["dim_" + nm] = dim
            rec["gain_auc"] = round((rec["auc_修复后"] - rec["auc_未清洗"]) * 100, 2)
            rec["gain_f1"] = round((rec["f1_修复后"] - rec["f1_未清洗"]) * 100, 2)
            rows.append(rec)
            print("  %s seed=%d  F1 %.4f→%.4f (%+.2fpp)  AUC %+.2fpp"
                  % (tag, seed, rec["f1_未清洗"], rec["f1_修复后"],
                     rec["gain_f1"], rec["gain_auc"]))

        agg = {}
        for k in ("auc_干净", "auc_未清洗", "auc_修复后",
                  "f1_干净", "f1_未清洗", "f1_修复后",
                  "gain_auc", "gain_f1"):
            xs = [r[k] for r in rows]
            agg[k] = {"mean": round(mean(xs), 4), "std": round(std(xs), 4),
                      "min": min(xs), "max": max(xs)}
        agg["wins_f1"] = sum(1 for r in rows if r["gain_f1"] > 0)
        agg["wins_auc"] = sum(1 for r in rows if r["gain_auc"] > 0)
        out["by_rate"][tag] = {"rows": rows, "agg": agg}
        print("  %s 均值: F1 %+.2f±%.2fpp（%d/%d 正）  AUC %+.2f±%.2fpp（%d/%d 正）"
              % (tag,
                 agg["gain_f1"]["mean"], agg["gain_f1"]["std"], agg["wins_f1"], len(rows),
                 agg["gain_auc"]["mean"], agg["gain_auc"]["std"], agg["wins_auc"], len(rows)))
        print()

    out["wall_seconds"] = round(time.time() - t0, 1)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("写出", OUT, "耗时 %.1f 秒" % out["wall_seconds"])


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(BASE))
    from run_v2 import downstream
    downstream(R.load_adult())
