"""NO.9 财务审核测试：科目映射、零误放红线、重复报销拦截、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import gen_bills
from solution import DualReviewer, SubjectMapper, audit

BILLS = gen_bills()


def test_subject_mapping_accuracy():
    mapper = SubjectMapper()
    ok = sum(1 for b in BILLS if mapper.map_subject(b) == b["subject_gold"])
    assert ok / len(BILLS) >= 0.99, f"科目映射准确率 {ok/len(BILLS):.1%} 过低"


def test_zero_missed_issues_redline():
    """有问题却自动直通 = 误放，政务/财务场景红线必须为 0。"""
    r = audit(BILLS)
    assert r["missed"] == 0, f"误放 {r['missed']} 张问题单，触碰红线"


def test_issue_recall():
    r = audit(BILLS)
    assert r["recall"] >= 0.95, f"问题检出率 {r['recall']:.1%} 过低"


def test_auto_pass_rate_reasonable():
    """确定单直通、问题单进队列：直通率应显著高于 0 且低于 100%。"""
    r = audit(BILLS)
    assert 0.5 <= r["auto_rate"] <= 0.99


def test_duplicate_invoice_blocked():
    dup = next(b for b in BILLS if b["issue"] == "重复报销")
    rv = DualReviewer()
    # 模拟台账中已出现过该发票号
    rv.seen.add(dup["invoice_no"])
    res = rv.review(dup)
    assert any("重复报销" in i for i in res["issues"]) and res["status"] == "risk_queue"


def test_deterministic():
    a = audit(BILLS)
    b = audit(BILLS)
    assert a == b
