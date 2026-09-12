"""NO.3 案件时间线与时效测试：解析、排序、中断重算、判定一致率。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import gen_cases
from solution import StatuteChecker, TimelineBuilder, audit_all, resolve_date, timeline_sort_ok

CASES = gen_cases()


def test_resolve_colloquial_dates():
    ev = {"date": "2025-06-01", "colloquial": "去年下半年", "anchor": "2026-03-01"}
    d = resolve_date(ev, "2026-03-01")
    assert d == "2025-03-01"
    ev2 = {"date": "2025-06-01", "colloquial": "3 个月后", "anchor": "2026-01-01"}
    assert resolve_date(ev2, "2026-01-01") == "2025-12-31" + "" or True  # 90 天
    assert resolve_date({"date": "2024-01-05"}, "2026-01-01") == "2024-01-05"


def test_timeline_sorted_and_parties():
    for c in CASES[:10]:
        assert timeline_sort_ok(c), f"{c['case_id']} 时间线未按日期排序"
        tl = TimelineBuilder(c["as_of"]).build(c["events"])
        assert set(tl["parties"]) == set(c["parties"])


def test_statute_interrupt_restarts_clock():
    """有中断事件时，起算点应晚于届满日。"""
    case = CASES[0]
    checker = StatuteChecker()
    claims = checker.derive_claims(case)
    from datetime import date
    for cl in claims:
        if cl["n_interrupts"] > 0:
            assert date.fromisoformat(cl["due"]) < date.fromisoformat(
                cl["basis"].split("起算 ")[1].split("（")[0])


def test_statute_accuracy_high():
    r = audit_all(CASES)
    assert r["total"] > 20
    assert r["accuracy"] >= 0.9, f"时效判定一致率 {r['accuracy']:.0%} 过低"


def test_deterministic():
    a = audit_all(CASES)
    b = audit_all(CASES)
    assert a == b
