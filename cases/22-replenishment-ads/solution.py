"""NO.22 补货与广告联动：三种策略在同一需求流上的库存模拟回测。

对应 NO.22 案例的链路「订单库存 → 补货决策 → 广告投放」联动：
- ManualBulk   人工现状：每 30 天盘点，按近 90 天平均需求补足"90 天覆盖"，
               无安全库存；广告与库存割裂，断货照常投放。
- StaticROP    经典 (s, Q)：再订货点 = 提前期均值需求 + z·σ·√LT；
               广告仍然割裂。
- AdaptiveROP  优化版：滚动需求重估 + 安全库存 + **库存-广告联动**
               （库存跌破提前期需求 → 暂停广告：省广告费 + 压低断货期需求）。

每天依次执行：在途到货（同步核销在途量）→ 需求实现（未满足即丢失）→
补货决策 → 广告开关。指标：满足率、缺货天数、平均库存、广告浪费、总成本。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

REVIEW_INTERVAL = 30     # 人工盘点周期（天）
Z = 1.65                 # 95% 服务水平
HOLDING_RATE = 0.0007    # 日持有成本率（≈2%/月，含仓储资金占用，× 平均单价）
LOST_MARGIN_RATE = 0.3   # 缺货丢失毛利率（× 平均单价）
AD_DROP_FACTOR = 0.6     # 广告暂停期需求因子


@dataclass
class SimResult:
    policy: str
    filled: int
    lost: int
    stockout_days: int
    avg_inventory: float
    ad_waste: float          # 断货期间仍投放的广告费（元）
    holding_cost: float
    lost_margin: float

    @property
    def fill_rate(self) -> float:
        return self.filled / max(1, self.filled + self.lost)

    @property
    def total_cost(self) -> float:
        return self.ad_waste + self.holding_cost + self.lost_margin


def _demand_estimate(history: np.ndarray, d: int, window: int = 30):
    """近窗均值与全程均值混合：缓解断货期"需求被截断→不再补货"的死亡螺旋。"""
    recent = history[:, max(0, d - window + 1) : d + 1]
    todate = history[:, : d + 1]
    if d >= window - 1:
        mu_r = recent.mean(axis=1)
        sd_r = recent.std(axis=1)
    else:
        mu_r = todate.mean(axis=1)
        sd_r = mu_r * 0.5
    mu_all = todate.mean(axis=1)
    return 0.6 * mu_r + 0.4 * mu_all, sd_r


def _run(demand: np.ndarray, price: np.ndarray, lead: int, ad_budget: float,
         policy: str) -> SimResult:
    n_sku, n_days = demand.shape
    inv = np.zeros(n_sku)
    pipeline: dict[int, list] = {d: [] for d in range(n_days)}  # 到货日 -> [(sku, qty)]
    onhand_order = np.zeros(n_sku)  # 已下单未到货
    history = np.zeros((n_sku, n_days))
    filled = lost = stockout_days = 0
    inv_sum = 0.0
    ad_waste = 0.0
    ad_paused = np.zeros(n_sku, dtype=bool)
    mu = np.ones(n_sku)

    for d in range(n_days):
        # 1) 到货并核销在途
        for sku, qty in pipeline.pop(d, []):
            inv[sku] += qty
            onhand_order[sku] -= qty
        # 2) 需求实现（广告暂停期需求因子下调）
        eff = np.where(ad_paused, demand[:, d] * AD_DROP_FACTOR, demand[:, d]).round()
        got = np.minimum(inv, eff)
        inv -= got
        filled += int(got.sum())
        lost += int(max(0.0, eff.sum() - got.sum()))
        history[:, d] = demand[:, d]
        stockout_days += int(((inv <= 0.5) & (demand[:, d] > 0)).sum())
        # 3) 补货决策
        if policy == "manual_bulk":
            if d % REVIEW_INTERVAL == 0:
                mu90 = history[:, max(0, d - 89) : d + 1].mean(axis=1) if d > 0 \
                    else demand[:, :1].mean(axis=1)
                target = mu90 * 90
                gap = target - inv - onhand_order
                for i in np.nonzero(gap > 0)[0]:
                    q = float(gap[i])
                    onhand_order[i] += q
                    pipeline.setdefault(min(n_days - 1, d + lead), []).append((int(i), q))
        else:
            mu, sd = _demand_estimate(history, d)
            rop = mu * lead + Z * sd * np.sqrt(lead)
            position = inv + onhand_order
            for i in np.nonzero((position < rop) & (onhand_order <= 0.5))[0]:
                q = max(float(mu[i] * (lead + 7)), float(rop[i] - position[i] + mu[i] * 7))
                onhand_order[i] += q
                pipeline.setdefault(min(n_days - 1, d + lead), []).append((int(i), q))
        # 4) 广告决策
        if policy == "adaptive_rop":
            ad_paused = inv < mu * lead * 0.9
        else:
            waste_mask = (inv <= 0.5) & (demand[:, d] > 0)  # 断货仍在投放
            ad_waste += float((waste_mask * ad_budget).sum())
        inv_sum += inv.sum()
    return SimResult(
        policy=policy, filled=filled, lost=lost, stockout_days=stockout_days,
        avg_inventory=inv_sum / n_days, ad_waste=ad_waste,
        holding_cost=float(inv_sum * HOLDING_RATE * price.mean()),
        lost_margin=float(lost * LOST_MARGIN_RATE * price.mean()),
    )


def run_all(demand: list[list[int]], prices: list[float], lead: int,
            ad_budget: float) -> list[SimResult]:
    D = np.asarray(demand, dtype=float)
    P = np.asarray(prices, dtype=float)
    return [
        _run(D, P, lead, ad_budget, "manual_bulk"),
        _run(D, P, lead, ad_budget, "static_rop"),
        _run(D, P, lead, ad_budget, "adaptive_rop"),
    ]
