# -*- coding: utf-8 -*-
"""流水线核心与审计模块的单元测试。

运行：python run_tests.py
"""
import io
import json
import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "exp"))

import run_exp as R
import dq_audit as A


def mkrow(**kw):
    """构造一行合法的 Adult 记录，再按需覆盖字段。"""
    r = {
        "age": 40.0, "workclass": "Private", "fnlwgt": 200000.0,
        "education": "Bachelors", "education_num": 13.0,
        "marital_status": "Married-civ-spouse", "occupation": "Exec-managerial",
        "relationship": "Husband", "race": "White", "sex": "Male",
        "capital_gain": 0.0, "capital_loss": 0.0, "hours_per_week": 45.0,
        "native_country": "United-States", "income": "<=50K",
    }
    r.update(kw)
    return r


def mkrows(n=3, **kw):
    """构造 n 行互不相同的合法记录（否则会被去重逻辑当成重复行删掉）。"""
    out = []
    for i in range(n):
        r = mkrow(**kw)
        if "age" not in kw:
            r["age"] = 20.0 + i % 60
        if "fnlwgt" not in kw:
            r["fnlwgt"] = 200000.0 + i
        out.append(r)
    return out


class TestQuantile(unittest.TestCase):
    """分位数：插值口径与边界。"""

    def test_median_odd(self):
        self.assertEqual(R.pct([1, 2, 3], 0.5), 2)

    def test_median_even(self):
        self.assertEqual(R.pct([1, 2, 3, 4], 0.5), 2.5)

    def test_low_quantile(self):
        self.assertEqual(R.pct([1, 2, 3, 4], 0.0), 1)

    def test_high_quantile(self):
        self.assertEqual(R.pct([1, 2, 3, 4], 1.0), 4)

    def test_single_value(self):
        self.assertEqual(R.pct([7], 0.5), 7)

    def test_unsorted_input(self):
        self.assertEqual(R.pct([4, 1, 3, 2], 0.5), 2.5)


class TestEditDistance(unittest.TestCase):
    """编辑距离：拼写纠正的判据。"""

    def test_identical(self):
        self.assertEqual(R.lev("PRIVATE", "PRIVATE"), 0)

    def test_one_insert(self):
        self.assertEqual(R.lev("PRIVAT", "PRIVATE"), 1)

    def test_one_sub(self):
        self.assertEqual(R.lev("PRIVPTE", "PRIVATE"), 1)

    def test_length_gap_exceeds_cap(self):
        # 长度差超过 cap 时直接返回 cap+1，不进入 DP
        self.assertGreater(R.lev("A", "ABCDEF", cap=3), 3)

    def test_symmetric(self):
        self.assertEqual(R.lev("COLOR", "COLOUR"), R.lev("COLOUR", "COLOR"))


class TestMetrics(unittest.TestCase):
    """精确率、召回率、F1 与 AUC。"""

    def test_prf_perfect(self):
        self.assertEqual(R.prf(5, 0, 0), (1.0, 1.0, 1.0))

    def test_prf_all_wrong(self):
        p, r, f = R.prf(0, 5, 5)
        self.assertEqual((p, r, f), (0.0, 0.0, 0.0))

    def test_prf_zero_division(self):
        self.assertEqual(R.prf(0, 0, 0), (0.0, 0.0, 0.0))

    def test_prf_half(self):
        p, r, f = R.prf(5, 5, 5)
        self.assertAlmostEqual(p, 0.5)
        self.assertAlmostEqual(r, 0.5)
        self.assertAlmostEqual(f, 0.5)

    def test_auc_perfect_ranking(self):
        self.assertAlmostEqual(R.auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]), 1.0)

    def test_auc_reversed(self):
        self.assertAlmostEqual(R.auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]), 0.0)

    def test_auc_ties_are_half(self):
        self.assertAlmostEqual(R.auc([1, 0], [0.5, 0.5]), 0.5)

    def test_auc_single_class(self):
        # 只有一类时无排序意义，返回 0.5
        self.assertAlmostEqual(R.auc([1, 1], [0.1, 0.9]), 0.5)


class TestProfile(unittest.TestCase):
    """画像：行数、缺失、重复。"""

    def test_rows_and_cells(self):
        p = R.profile(mkrows(4))
        self.assertEqual(p["rows"], 4)
        self.assertEqual(p["cols"], len(R.COLS))
        self.assertEqual(p["cells"], 4 * len(R.COLS))

    def test_missing_counted(self):
        rows = mkrows(3)
        rows[0]["age"] = None
        rows[1]["age"] = None
        p = R.profile(rows)
        col = [c for c in p["columns"] if c["name"] == "age"][0]
        self.assertEqual(col["missing"], 2)
        self.assertAlmostEqual(col["missing_rate"], 66.667, places=2)

    def test_no_missing(self):
        p = R.profile(mkrows(2))
        self.assertEqual(sum(c["missing"] for c in p["columns"]), 0)

    def test_duplicate_rows_counted(self):
        rows = [mkrow(), mkrow(), mkrow(age=55.0)]
        p = R.profile(rows)
        self.assertEqual(p["dup_rows"], 1)

    def test_numeric_stats(self):
        rows = [mkrow(age=20.0), mkrow(age=40.0), mkrow(age=60.0)]
        col = [c for c in R.profile(rows)["columns"] if c["name"] == "age"][0]
        self.assertEqual(col["min"], 20.0)
        self.assertEqual(col["max"], 60.0)
        self.assertEqual(col["median"], 40.0)


class TestDomain(unittest.TestCase):
    """取值域构建。"""

    def test_collects_all_values(self):
        rows = [mkrow(sex="Male"), mkrow(sex="Female")]
        dom = R.build_domain(rows)
        self.assertEqual(dom["sex"], {"Male", "Female"})

    def test_skips_none(self):
        rows = [mkrow(sex=None), mkrow(sex="Male")]
        dom = R.build_domain(rows)
        self.assertNotIn(None, dom["sex"])

    def test_income_in_domain(self):
        dom = R.build_domain(mkrows(2))
        self.assertIn("<=50K", dom["income"])


class TestRuleScan(unittest.TestCase):
    """规则引擎：11 条断言的命中与不误报。"""

    def setUp(self):
        self.rows = mkrows(2)
        self.dom = R.build_domain(self.rows)

    def test_clean_rows_have_no_hits(self):
        self.assertEqual(dict(R.rule_scan(self.rows, self.dom)), {})

    def test_r0_missing(self):
        self.rows[0]["age"] = None
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R0", hit[(0, "age")])

    def test_r1_age_out_of_range(self):
        self.rows[0]["age"] = 200.0
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R1", hit[(0, "age")])

    def test_r1_age_lower_bound(self):
        self.rows[0]["age"] = 10.0
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R1", hit[(0, "age")])

    def test_r2_hours_out_of_range(self):
        self.rows[0]["hours_per_week"] = 200.0
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R2", hit[(0, "hours_per_week")])

    def test_r3_capital_gain_impossible(self):
        self.rows[0]["capital_gain"] = 100.0
        hit = R.rule_scan(self.rows, self.dom)
        self.assertNotIn((0, "capital_gain"), hit)
        self.assertIn("R3", R.warning_scan(self.rows)[(0, "capital_gain")])

    def test_r3_zero_is_fine(self):
        self.rows[0]["capital_gain"] = 0.0
        self.assertNotIn((0, "capital_gain"), R.rule_scan(self.rows, self.dom))

    def test_r4_education_mismatch(self):
        self.rows[0]["education_num"] = 1.0
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R4", hit[(0, "education_num")])

    def test_r5_sex_conflict(self):
        self.rows[0]["sex"] = "Female"
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R5", hit[(0, "sex")])

    def test_r6_relationship_conflict(self):
        self.rows[0]["relationship"] = "Own-child"
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R6", hit[(0, "relationship")])

    def test_r7_value_outside_domain(self):
        self.rows[0]["workclass"] = "Federa1-gov"
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R7", hit[(0, "workclass")])

    def test_r8_workclass_missing_but_occupation_present(self):
        self.rows[0]["workclass"] = None
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R8", hit[(0, "workclass")])

    def test_r9_fnlwgt_out_of_range(self):
        self.rows[0]["fnlwgt"] = 99999999.0
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R9", hit[(0, "fnlwgt")])

    def test_r10_income_outside_labels(self):
        self.rows[0]["income"] = ">50k"
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R10", hit[(0, "income")])

    def test_multiple_rules_same_cell(self):
        self.rows[0]["age"] = None
        hit = R.rule_scan(self.rows, self.dom)
        self.assertIn("R0", hit[(0, "age")])


class TestStatScan(unittest.TestCase):
    """统计检测：稳健 z 与低频取值。"""

    def test_returns_hits_and_stats(self):
        rows = mkrows(50)
        rows[0]["age"] = 999.0
        hit, stats = R.stat_scan(rows)
        self.assertIn("age", stats)
        self.assertTrue(any(k[1] == "age" for k in hit))

    def test_constant_column_no_crash(self):
        rows = mkrows(20, age=40.0)
        hit, stats = R.stat_scan(rows)
        self.assertIn("age", stats)

    def test_missing_values_skipped(self):
        rows = mkrows(20)
        rows[0]["age"] = None
        hit, stats = R.stat_scan(rows)
        self.assertNotIn(((0), "age"), [k for k in hit if k[1] == "age"])


class TestRepair(unittest.TestCase):
    """修复算子：每类错误的处置与动作记录。"""

    def setUp(self):
        self.rows = mkrows(30)
        self.dom = R.build_domain(self.rows)

    def _repair(self, rows):
        audit = []
        fixed, acts = R.repair(rows, self.dom, None, None, audit=audit)
        return fixed, acts, audit

    def test_clean_data_untouched(self):
        fixed, acts, audit = self._repair(self.rows)
        self.assertEqual(len(audit), 0)
        self.assertEqual(sum(acts.values()), 0)

    def test_missing_numeric_filled(self):
        self.rows[0]["age"] = None
        fixed, acts, audit = self._repair(self.rows)
        self.assertIsNotNone(fixed[0]["age"])
        self.assertIn("训练中位数填补", acts)

    def test_missing_categorical_filled(self):
        self.rows[0]["workclass"] = None
        fixed, acts, audit = self._repair(self.rows)
        self.assertIsNone(fixed[0]["workclass"])

    def test_unit_rollback(self):
        self.rows[0]["hours_per_week"] = 45000.0     # 45 被乘了 1000
        fixed, acts, audit = self._repair(self.rows)
        self.assertTrue(1 <= fixed[0]["hours_per_week"] <= 99)
        self.assertIn("单位回退", acts)

    def test_functional_dependency(self):
        self.rows[0]["education_num"] = 1.0
        fixed, acts, audit = self._repair(self.rows)
        self.assertEqual(fixed[0]["education_num"], 13.0)
        self.assertIn("函数依赖回填", acts)

    def test_logic_conflict_fixed(self):
        self.rows[0]["sex"] = "Female"
        fixed, acts, audit = self._repair(self.rows)
        self.assertEqual(fixed[0]["sex"], "Male")

    def test_typo_corrected(self):
        self.rows[0]["workclass"] = "Privte"
        fixed, acts, audit = self._repair(self.rows)
        self.assertEqual(fixed[0]["workclass"], "Private")
        self.assertIn("编辑距离纠正", acts)

    def test_capital_gain_threshold(self):
        self.rows[0]["capital_gain"] = 100.0
        fixed, acts, audit = self._repair(self.rows)
        self.assertEqual(fixed[0]["capital_gain"], 100.0)

    def test_duplicate_rows_dropped(self):
        rows = mkrows(5)
        rows.append(dict(rows[2]))          # 复制第 3 行
        fixed, acts, audit = self._repair(rows)
        self.assertEqual(len(fixed), 5)
        self.assertEqual(acts["重复行删除"], 1)

    def test_input_not_mutated(self):
        self.rows[0]["age"] = None
        before = dict(self.rows[0])
        self._repair(self.rows)
        self.assertEqual(self.rows[0], before)


class TestAuditTrail(unittest.TestCase):
    """审计日志：事件内容、可撤销性、回滚一致性。"""

    def setUp(self):
        self.rows = mkrows(40)
        self.rows[0]["age"] = None
        self.rows[0]["workclass"] = "Privte"
        self.rows[1]["hours_per_week"] = 45000.0
        self.dom = R.build_domain(mkrows(40))
        self.audit = []
        self.fixed, self.acts = R.repair(self.rows, self.dom, None, None,
                                        audit=self.audit)

    def test_events_recorded(self):
        self.assertGreater(len(self.audit), 0)

    def test_cell_event_has_before_after(self):
        e = [x for x in self.audit if x["op"] == "cell_fix"][0]
        for k in ("row", "col", "before", "after", "action"):
            self.assertIn(k, e)

    def test_before_differs_from_after(self):
        for e in self.audit:
            if e["op"] == "cell_fix":
                self.assertNotEqual(e["before"], e["after"])

    def test_rollback_restores_bytes(self):
        back = A.rollback(self.fixed, self.audit)
        self.assertTrue(A.verify(self.rows, back, R.COLS)["identical"])

    def test_rollback_without_drop(self):
        rows = mkrows(10)
        rows[0]["age"] = None
        dom = R.build_domain(mkrows(10))
        audit = []
        fixed, _ = R.repair(rows, dom, None, None, audit=audit)
        back = A.rollback(fixed, audit)
        self.assertTrue(A.verify(rows, back, R.COLS)["identical"])

    def test_row_drop_rollback(self):
        rows = mkrows(6)
        rows.append(dict(rows[1]))
        dom = R.build_domain(mkrows(6))
        audit = []
        fixed, _ = R.repair(rows, dom, None, None, audit=audit)
        self.assertEqual(len(fixed), 6)
        back = A.rollback(fixed, audit)
        self.assertEqual(len(back), 7)
        self.assertTrue(A.verify(rows, back, R.COLS)["identical"])

    def test_summarize_counts(self):
        s = A.summarize(self.audit)
        self.assertEqual(s["total"], len(self.audit))
        self.assertEqual(s["reversible"], len(self.audit))
        self.assertIn("by_action", s)

    def test_signature_stable(self):
        self.assertEqual(A.signature(self.rows, R.COLS),
                         A.signature([dict(r) for r in self.rows], R.COLS))

    def test_signature_detects_change(self):
        other = [dict(r) for r in self.rows]
        other[5]["age"] = 99.0
        self.assertNotEqual(A.signature(self.rows, R.COLS),
                            A.signature(other, R.COLS))


class TestAuditIO(unittest.TestCase):
    """日志落盘与读取。"""

    def test_write_and_read_roundtrip(self):
        events = [{"op": "cell_fix", "row": 0, "col": "age",
                   "before": None, "after": 30.0, "action": "填补"},
                  {"op": "row_drop", "row": 3, "snapshot": {"age": 1.0}}]
        d = tempfile.mkdtemp()
        p = os.path.join(d, "a.jsonl")
        n = A.write_log(events, p)
        self.assertEqual(n, 2)
        back = A.read_log(p)
        self.assertEqual(len(back), 2)
        self.assertEqual(back[0]["seq"], 1)
        self.assertEqual(back[0]["col"], "age")
        self.assertEqual(back[1]["snapshot"]["age"], 1.0)

    def test_jsonl_one_record_per_line(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "b.jsonl")
        A.write_log([{"op": "cell_fix", "row": i} for i in range(3)], p)
        with io.open(p, encoding="utf-8") as f:
            lines = [x for x in f.read().splitlines() if x]
        self.assertEqual(len(lines), 3)
        for ln in lines:
            json.loads(ln)

    def test_read_skips_blank_lines(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "c.jsonl")
        with io.open(p, "w", encoding="utf-8") as f:
            f.write('{"op":"cell_fix"}\n\n')
        self.assertEqual(len(A.read_log(p)), 1)


class TestRollbackEdge(unittest.TestCase):
    """回滚的边界情况。"""

    def test_empty_events(self):
        rows = mkrows(3)
        back = A.rollback(rows, [])
        self.assertTrue(A.verify(rows, back, R.COLS)["identical"])

    def test_row_index_out_of_range_ignored(self):
        rows = mkrows(2)
        back = A.rollback(rows, [{"op": "cell_fix", "row": 99,
                                  "col": "age", "before": 1.0}])
        self.assertEqual(len(back), 2)

    def test_rollback_preserves_input(self):
        rows = mkrows(3)
        rows[0]["age"] = None
        dom = R.build_domain(mkrows(3))
        audit = []
        fixed, _ = R.repair(rows, dom, None, None, audit=audit)
        snapshot = [dict(r) for r in fixed]
        A.rollback(fixed, audit)
        self.assertEqual(fixed, snapshot)


class TestDownstream(unittest.TestCase):
    """下游分类器：能训练、能出分、维度随取值域扩展。"""

    def test_train_and_predict(self):
        rows = [mkrow(age=float(20 + i), income=">50K" if i % 2 else "<=50K")
                for i in range(40)]
        medians = {c: R.pct([r[c] for r in rows if r[c] is not None], .5)
                   for c in R.NUM}
        pr_fn, dim = R.train_lr([(r, 1 if r["income"] == ">50K" else 0) for r in rows],
                                medians)
        s = pr_fn(rows[:5])
        self.assertEqual(len(s), 5)
        # predict 返回 logit（sigmoid 之前），只需是有限实数
        self.assertTrue(all(isinstance(x, float) for x in s))
        self.assertTrue(all(-1e6 < x < 1e6 for x in s))
        self.assertGreater(dim, 0)

    def test_sigmoid_maps_to_unit_interval(self):
        import math
        rows = [mkrow(age=float(20 + i), income=">50K" if i % 2 else "<=50K")
                for i in range(40)]
        medians = {c: R.pct([r[c] for r in rows if r[c] is not None], .5)
                   for c in R.NUM}
        pr_fn, _ = R.train_lr([(r, 1 if r["income"] == ">50K" else 0) for r in rows],
                              medians)
        probs = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
                 for z in pr_fn(rows[:5])]
        self.assertTrue(all(0.0 <= p <= 1.0 for p in probs))

    def test_dirty_categories_inflate_dims(self):
        clean = [mkrow() for _ in range(30)]
        dirty = [dict(r) for r in clean]
        dirty[0]["workclass"] = "Privatee"
        medians = {c: R.pct([r[c] for r in clean if r[c] is not None], .5)
                   for c in R.NUM}
        _, dim_clean = R.train_lr([(r, 0) for r in clean], medians)
        _, dim_dirty = R.train_lr([(r, 0) for r in dirty], medians)
        self.assertGreater(dim_dirty, dim_clean)


if __name__ == "__main__":
    unittest.main(verbosity=2)
