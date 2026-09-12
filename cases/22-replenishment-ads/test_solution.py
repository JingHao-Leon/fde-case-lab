"""NO.22 补货策略测试：库存非负、策略单调性、广告联动收益、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import gen_demand
from solution import run_all

DATA = gen_demand()
D = np.asarray(DATA["demand"], dtype=float)
P = np.asarray(DATA["unit_price"], dtype=float)


def _small_demand():
    rng = np.random.default_rng(1)
    return rng.poisson(3.0, size=(6, 60)).astype(float)


def test_results_well_formed():
    results = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"],
                      DATA["ad_daily_budget"])
    assert len(results) == 3
    for r in results:
        assert r.filled + r.lost > 0
        assert 0.0 <= r.fill_rate <= 1.0
        assert r.avg_inventory >= 0


def test_rop_beats_manual_on_fill_rate():
    results = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"],
                      DATA["ad_daily_budget"])
    manual, static, adaptive = results
    assert static.fill_rate > manual.fill_rate, "经典 ROP 未超过人工月度补货"
    assert adaptive.fill_rate >= static.fill_rate - 0.01, "联动版满足率不应明显退化"


def test_ad_linkage_cuts_ad_waste():
    results = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"],
                      DATA["ad_daily_budget"])
    static, adaptive = results[1], results[2]
    assert adaptive.ad_waste < static.ad_waste * 0.5, "广告联动未把断货期浪费砍半"


def test_adaptive_has_lowest_total_cost():
    results = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"],
                      DATA["ad_daily_budget"])
    costs = [r.total_cost for r in results]
    assert costs[2] == min(costs), "联动版总成本应最低"


def test_common_random_numbers_fairness():
    """两种非联动策略必须面对同一条需求流；联动版因广告暂停允许需求下移。"""
    results = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"],
                      DATA["ad_daily_budget"])
    t_manual, t_static, t_adaptive = [r.filled + r.lost for r in results]
    assert abs(t_manual - t_static) < 0.01 * t_manual, "非联动策略需求流不一致"
    assert t_adaptive < t_manual, "联动版广告暂停应压低有效需求"
    # 需求下移主要来自"本就难以履约 SKU"上的广告刹车；真实系统会把预算
    # 转投给有货 SKU（本模型未建模该收益），因此只约束下移幅度上限。
    assert t_adaptive > 0.75 * t_manual, "广告暂停过度牺牲有效需求"


def test_deterministic():
    a = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"], 30.0)
    b = run_all(DATA["demand"], DATA["unit_price"], DATA["lead_time"], 30.0)
    assert [r.total_cost for r in a] == [r.total_cost for r in b]
