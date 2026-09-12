"""NO.22 跨境电商补货与广告联动：生成多 SKU 需求合成数据。

场景来自《Datawhale FDE 案例 100》NO.22：东南亚服装跨境电商，约 2000+ SKU，
补货靠人工扒 SaaS 数据填 Excel；广告与库存割裂——SKU 断货了广告还在烧。
本生成器产出 200 个 SKU × 240 天的需求矩阵（快/中/慢三层动销 + 周末高峰），
固定种子可复现，供三种补货策略在完全相同的需求流上做公平回测。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

N_SKU = 200
N_DAYS = 240
LEAD_TIME = 14        # 工厂补货提前期（天）
AD_DAILY_BUDGET = 30.0  # 每 SKU 日广告预算（元）


def gen_demand(seed: int = 20260913) -> dict:
    rng = np.random.default_rng(seed)
    tiers = rng.choice(["fast", "mid", "slow"], size=N_SKU, p=[0.2, 0.35, 0.45])
    lam = np.where(tiers == "fast", rng.uniform(6, 12, N_SKU),
                   np.where(tiers == "mid", rng.uniform(2, 5, N_SKU),
                            rng.uniform(0.4, 1.5, N_SKU)))
    weekend_boost = np.ones(N_DAYS)
    weekend_boost[[d for d in range(N_DAYS) if d % 7 in (5, 6)]] = 1.5
    # 缓慢趋势：快销 SKU 逐月爬坡（+40%/4个月），慢销持平
    trend = np.linspace(1.0, 1.0, N_DAYS)
    fast_mask = tiers == "fast"
    demand = np.zeros((N_SKU, N_DAYS), dtype=int)
    for i in range(N_SKU):
        t = np.linspace(1.0, 1.4 if fast_mask[i] else 1.0, N_DAYS)
        demand[i] = rng.poisson(lam[i] * weekend_boost * t)
    unit_price = rng.uniform(60, 220, N_SKU).round(2)
    return {
        "demand": demand.tolist(),
        "tiers": tiers.tolist(),
        "unit_price": unit_price.tolist(),
        "lead_time": LEAD_TIME,
        "ad_daily_budget": AD_DAILY_BUDGET,
    }


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    data = gen_demand()
    (out / "demand.json").write_text(json.dumps(data), encoding="utf-8")
    total = sum(sum(r) for r in data["demand"])
    print(f"生成 {N_SKU} SKU × {N_DAYS} 天需求矩阵，总需求 {total} 件 -> {out/'demand.json'}")


if __name__ == "__main__":
    main()
