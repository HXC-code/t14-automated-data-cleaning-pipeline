# -*- coding: utf-8 -*-
"""模型与工具函数测试：错误注入、特征编码、孤立森林、评估曲线。

运行：python run_tests.py
"""
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "exp"))

import run_exp as R
from tests.test_pipeline import mkrow, mkrows


class TestInject(unittest.TestCase):
    """错误注入：九类错误与整行重复的构造。"""

    def setUp(self):
        self.rows = mkrows(60)
        self.dom = R.build_domain(self.rows)

    def test_returns_three_values(self):
        out = R.inject(self.rows, self.dom, rate=0.05, seed=1)
        self.assertEqual(len(out), 3)

    def test_truth_not_empty(self):
        dirty, truth, dup_of = R.inject(self.rows, self.dom, rate=0.05, seed=1)
        self.assertGreater(len(truth), 0)

    def test_dirty_differs_from_clean(self):
        dirty, truth, dup_of = R.inject(self.rows, self.dom, rate=0.05, seed=1)
        diff = sum(1 for i, c in truth
                   if i < len(self.rows) and dirty[i][c] != self.rows[i][c])
        self.assertGreater(diff, 0)

    def test_duplicates_appended(self):
        dirty, truth, dup_of = R.inject(self.rows, self.dom, rate=0.05, seed=1)
        self.assertGreater(len(dirty), len(self.rows))
        self.assertGreater(len(dup_of), 0)

    def test_duplicate_rows_equal_source(self):
        dirty, truth, dup_of = R.inject(self.rows, self.dom, rate=0.05, seed=1)
        for new_i, src_i in dup_of.items():
            self.assertEqual(dirty[new_i]["age"], dirty[src_i]["age"])

    def test_seed_reproducible(self):
        a = R.inject(self.rows, self.dom, rate=0.05, seed=7)
        b = R.inject(self.rows, self.dom, rate=0.05, seed=7)
        self.assertEqual(sorted(a[1].keys()), sorted(b[1].keys()))

    def test_different_seed_differs(self):
        a = R.inject(self.rows, self.dom, rate=0.05, seed=7)
        b = R.inject(self.rows, self.dom, rate=0.05, seed=8)
        self.assertNotEqual(sorted(a[1].keys()), sorted(b[1].keys()))

    def test_income_never_modified(self):
        dirty, truth, dup_of = R.inject(self.rows, self.dom, rate=0.10, seed=3)
        self.assertFalse([k for k in truth if k[1] == "income"])

    def test_input_not_mutated(self):
        snapshot = [dict(r) for r in self.rows]
        R.inject(self.rows, self.dom, rate=0.05, seed=1)
        self.assertEqual(self.rows, snapshot)


class TestEncode(unittest.TestCase):
    """特征编码与标准化。"""

    def setUp(self):
        self.rows = mkrows(30)
        self.dom = R.build_domain(self.rows)
        self.med = {c: R.pct([r[c] for r in self.rows if r[c] is not None], .5)
                    for c in R.NUM}

    def test_shape(self):
        X = R.encode(self.rows, self.med, self.dom)
        self.assertEqual(len(X), len(self.rows))
        self.assertEqual(len(X[0]), len(R.NUM) + 2 * len(R.CAT))

    def test_standardized_mean_near_zero(self):
        X = R.encode(self.rows, self.med, self.dom)
        for j in range(len(X[0])):
            col = [row[j] for row in X]
            self.assertAlmostEqual(sum(col) / len(col), 0.0, places=6)

    def test_missing_filled_by_median(self):
        rows = [dict(r) for r in self.rows]
        rows[0]["age"] = None
        X = R.encode(rows, self.med, self.dom)
        self.assertIsInstance(X[0][0], float)

    def test_out_of_domain_flagged(self):
        rows = [dict(r) for r in self.rows]
        rows[0]["workclass"] = "Nope"
        X = R.encode(rows, self.med, self.dom)
        self.assertGreater(abs(X[0][len(R.NUM)]), 0.0)


class TestIForest(unittest.TestCase):
    """孤立森林：异常点得分应高于正常点。"""

    def _xy(self, n=60, with_outlier=True):
        X = [[float(i % 10), float(i // 10)] for i in range(n)]
        if with_outlier:
            X.append([500.0, 500.0])
        return X

    def test_fit_returns_self(self):
        f = R.IForest(n_trees=8, psi=32, seed=1)
        self.assertIs(f.fit(self._xy()), f)

    def test_score_length(self):
        X = self._xy()
        s = R.IForest(n_trees=8, psi=32, seed=1).fit(X).score(X)
        self.assertEqual(len(s), len(X))

    def test_outlier_scores_higher(self):
        X = self._xy()
        s = R.IForest(n_trees=30, psi=64, seed=1).fit(X).score(X)
        self.assertGreater(s[-1], sum(s[:-1]) / len(s[:-1]))

    def test_c_factor_bounds(self):
        f = R.IForest(n_trees=4, psi=16, seed=1)
        self.assertEqual(f._c(1), 1.0)
        self.assertGreater(f._c(100), 1.0)

    def test_single_point_tree(self):
        f = R.IForest(n_trees=2, psi=8, seed=1)
        t = f._tree([[1.0, 2.0]])
        self.assertEqual(t[0], "leaf")


class TestEvalCells(unittest.TestCase):
    """检测评估：命中、误报、漏报。"""

    def test_perfect(self):
        truth = {(0, "age"): "missing", (1, "sex"): "logic"}
        pred = {(0, "age"): ["R0"], (1, "sex"): ["R5"]}
        p, r, f = R.eval_cells(truth, pred)
        self.assertEqual((p, r, f), (1.0, 1.0, 1.0))

    def test_all_false_positive(self):
        truth = {(0, "age"): "missing"}
        pred = {(5, "sex"): ["R5"]}
        p, r, f = R.eval_cells(truth, pred)
        self.assertEqual((p, r, f), (0.0, 0.0, 0.0))

    def test_partial(self):
        truth = {(0, "age"): "a", (1, "age"): "a", (2, "age"): "a"}
        pred = {(0, "age"): ["R0"], (1, "age"): ["R0"]}
        p, r, f = R.eval_cells(truth, pred)
        self.assertEqual(p, 1.0)
        self.assertAlmostEqual(r, 0.6667, places=3)

    def test_empty_pred(self):
        p, r, f = R.eval_cells({(0, "age"): "a"}, {})
        self.assertEqual((p, r, f), (0.0, 0.0, 0.0))


class TestCurves(unittest.TestCase):
    """ROC 与 PR 曲线的点位。"""

    def setUp(self):
        self.y = [1, 1, 0, 0, 1, 0]
        self.s = [0.9, 0.8, 0.7, 0.3, 0.6, 0.1]

    def test_roc_returns_points(self):
        pts = R.roc_curve(self.y, self.s)
        self.assertGreater(len(pts), 1)

    def test_roc_endpoints(self):
        pts = R.roc_curve(self.y, self.s)
        self.assertAlmostEqual(pts[0][0], 0.0)
        self.assertAlmostEqual(pts[-1][0], 1.0)

    def test_roc_monotone_fpr(self):
        pts = R.roc_curve(self.y, self.s)
        fprs = [p[0] for p in pts]
        self.assertEqual(fprs, sorted(fprs))

    def test_pr_returns_points(self):
        pts = R.pr_curve(self.y, self.s)
        self.assertGreater(len(pts), 1)

    def test_pr_recall_in_range(self):
        for _, r in R.pr_curve(self.y, self.s):
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)


class TestLoadMushroom(unittest.TestCase):
    """第二个数据集：能读入则校验结构，缺文件则跳过。"""

    def setUp(self):
        path = os.path.join(BASE, "data", "mushroom.data")
        if not os.path.isfile(path):
            self.skipTest("mushroom.data 不存在")

    def test_loads_rows(self):
        rows = R.load_mushroom()
        self.assertGreater(len(rows), 0)

    def test_rows_are_sequences(self):
        rows = R.load_mushroom()
        # mushroom 按位置返回每行字段列表，行内元素为字符串
        self.assertIsInstance(rows[0], (list, tuple))
        self.assertTrue(all(isinstance(x, str) for x in rows[0]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
