# -*- coding: utf-8 -*-
"""单元测试与语句覆盖率入口。

覆盖率用标准库 trace 采集执行行，再用 ast 取语句起始行作分母，
不依赖 coverage 包。实验驱动 main() 不计入（它跑真实数据，不属单元测试范围）。

用法: python run_tests.py
"""
import ast
import io
import os
import sys
import trace
import unittest

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "exp"))

TARGETS = [
    ("dq_audit.py", "审计与回滚"),
    ("exp/run_exp.py", "检测、修复、下游模型"),
]


def stmt_lines(path, omit_main=False):
    """用 ast 收集语句起始行；omit_main 时排除 main() 及其后。"""
    with io.open(path, encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    stop = None
    if omit_main:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                stop = node.lineno
                break
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and isinstance(
                node, (ast.Assign, ast.Expr, ast.Return, ast.If, ast.For, ast.While,
                       ast.With, ast.Try, ast.Raise, ast.AugAssign, ast.FunctionDef,
                       ast.ClassDef, ast.Import, ast.ImportFrom, ast.Pass, ast.Break,
                       ast.Continue, ast.Assert)):
            if stop is not None and node.lineno >= stop:
                continue
            lines.add(node.lineno)
    return lines


def main():
    print("=" * 62)
    print("单元测试与覆盖率报告")
    print("=" * 62)

    suite = unittest.defaultTestLoader.discover(
        os.path.join(BASE, "tests"), top_level_dir=BASE)
    runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)

    tracer = trace.Trace(count=1, trace=0)
    result = tracer.runfunc(runner.run, suite)
    counts = tracer.results().counts

    executed = {}
    for (fn, lineno), n in counts.items():
        executed.setdefault(os.path.abspath(fn), set()).add(lineno)

    print()
    print("%-26s %8s %8s %9s" % ("模块", "语句数", "已覆盖", "覆盖率"))
    print("-" * 62)
    tot_s = tot_c = 0
    for rel, desc in TARGETS:
        path = os.path.join(BASE, rel)
        stmts = stmt_lines(path, omit_main=True)
        hit = executed.get(os.path.abspath(path), set()) & stmts
        s, c = len(stmts), len(hit)
        tot_s += s
        tot_c += c
        pct = 100.0 * c / s if s else 0.0
        print("%-24s %8d %8d %8.1f%%" % (rel, s, c, pct))
    print("-" * 62)
    pct_all = 100.0 * tot_c / tot_s if tot_s else 0.0
    print("%-24s %8d %8d %8.1f%%" % ("合计", tot_s, tot_c, pct_all))
    print()
    print("说明：统计口径为核心模块的语句覆盖，排除实验驱动 main()。")

    out = os.path.join(BASE, "output")
    if not os.path.isdir(out):
        os.makedirs(out)
    with io.open(os.path.join(out, "coverage.txt"), "w", encoding="utf-8",
                 newline="\n") as f:
        f.write("模块\t语句数\t已覆盖\t覆盖率\n")
        for rel, _ in TARGETS:
            path = os.path.join(BASE, rel)
            stmts = stmt_lines(path, omit_main=True)
            hit = executed.get(os.path.abspath(path), set()) & stmts
            f.write("%s\t%d\t%d\t%.1f%%\n"
                    % (rel, len(stmts), len(hit),
                       100.0 * len(hit) / len(stmts) if stmts else 0))
        f.write("合计\t%d\t%d\t%.1f%%\n" % (tot_s, tot_c, pct_all))

    ok = result.wasSuccessful()
    print()
    print("用例：%d 项，失败 %d 项，错误 %d 项 → %s"
          % (result.testsRun, len(result.failures), len(result.errors),
             "全部通过" if ok else "存在失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
