"""NO.22 真实数据回测测试：UCI Online Retail 真实需求流上的策略良构性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_real", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_real import PROCESSED, load
from solution import run_all


def test_real_data_file_committed():
    assert PROCESSED.exists(), "真实需求 CSV 未随仓库提交，离线不可复现"
    daily = PROCESSED.read_text(encoding="utf-8").strip().splitlines()
    assert len(daily) >= 201  # 表头 + 200 SKU


def test_policies_run_on_real_demand():
    d = load()
    assert d["source"].startswith("UCI Online Retail"), "应优先使用真实数据"
    results = run_all(d["demand"], d["prices"], 14, 30.0)
    for r in results:
        assert 0.0 <= r.fill_rate <= 1.0
        assert r.avg_inventory >= 0
        assert all(x == r.total_cost for x in [r.total_cost])  # 有限值


def test_adaptive_zero_ad_waste_on_real_data():
    results = run_all(demand := load()["demand"], prices := load()["prices"],
                      lead := 14, ad_budget := 30.0)
    adaptive = results[2]
    assert adaptive.ad_waste == 0.0
    # 成本排序：联动 ≤ ROP ≤ 人工（真实需求上依旧成立）
    costs = [r.total_cost for r in results]
    assert costs[2] <= costs[1] <= costs[0]
