# -*- coding: utf-8 -*-
"""修复操作的留痕与回滚。

设计要点
--------
1. 只记可逆的最小操作：
   - cell_fix：记 (行, 列, before, after, 动作名)，回滚时写回 before；
   - row_drop：记整行快照，回滚时按原索引放回。
2. 回滚**不能**靠逆序 insert：连续删除多行时（如删 i=1、i=2），逆序插入会让
   后插的行落到错误位置，还原出的表行序错乱。正确做法是用删除记录算出原始
   行数，按原始索引重建整表，再逆序把 cell_fix 的 before 写回。
3. 用 sha256 对整表做签名，回滚后与原始表逐字节比对，作为"可撤回"的硬证据。
"""
import hashlib
import io
import json

OP_CELL = "cell_fix"
OP_DROP = "row_drop"


def signature(rows, cols):
    """对整张表做确定性签名：列序固定、值按 repr 归一。"""
    h = hashlib.sha256()
    for r in rows:
        h.update(("|".join(repr(r.get(c)) for c in cols) + "\n").encode("utf-8"))
    return h.hexdigest()


def write_log(events, path):
    """把事件写成 JSON Lines，一行一事件，便于流式读取与外部审计。"""
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        for k, e in enumerate(events, 1):
            rec = {"seq": k}
            rec.update(e)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(events)


def read_log(path):
    out = []
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def rollback(rows, events):
    """把修复后的表还原为修复前。

    步骤：
    1. 取全部 row_drop，算出原始行数，按原始索引把被删的行放回原位；
    2. 逆序重放 cell_fix，把 before 写回。
    """
    drops = {e["row"]: e["snapshot"] for e in events if e.get("op") == OP_DROP}
    if drops:
        n_orig = len(rows) + len(drops)
        out, j = [], 0
        for k in range(n_orig):
            if k in drops:
                out.append(dict(drops[k]))
            else:
                out.append(dict(rows[j]))
                j += 1
    else:
        out = [dict(r) for r in rows]

    for e in reversed(events):
        if e.get("op") == OP_CELL:
            i = e["row"]
            if 0 <= i < len(out):
                out[i][e["col"]] = e["before"]
    return out


def summarize(events):
    """按操作类型与动作名汇总，供报告引用。"""
    ops, acts = {}, {}
    for e in events:
        ops[e.get("op")] = ops.get(e.get("op"), 0) + 1
        if e.get("op") == OP_CELL:
            a = e.get("action", "-")
            acts[a] = acts.get(a, 0) + 1
    return {
        "total": len(events),
        "by_op": ops,
        "by_action": dict(sorted(acts.items(), key=lambda x: -x[1])),
        "reversible": ops.get(OP_CELL, 0) + ops.get(OP_DROP, 0),
    }


def verify(rows_before, rows_after_rollback, cols):
    """回滚校验：两次签名一致即逐字节还原。"""
    a = signature(rows_before, cols)
    b = signature(rows_after_rollback, cols)
    return {"original": a, "rolled_back": b, "identical": a == b}
