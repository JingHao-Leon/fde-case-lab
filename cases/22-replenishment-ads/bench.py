"""NO.22 回测：三种补货/广告策略在 200 SKU × 240 天同一需求流上的对比。

复现：python cases/22-replenishment-ads/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_demand
from solution import run_all

DATA = Path(__file__).parent / "data" / "demand.json"

NAMES = {
    "manual_bulk": "人工月度补货(现状)",
    "static_rop": "经典ROP(广告割裂)",
    "adaptive_rop": "ROP+广告联动(优化)",
}


def main() -> None:
    if not DATA.exists():
        d = gen_demand()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(d), encoding="utf-8")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    results = run_all(d["demand"], d["unit_price"], d["lead_time"], d["ad_daily_budget"])
    base = results[0]
    print("200 SKU × 240 天回测（三种策略共用同一需求流）\n")
    header = (f"{'策略':<16}{'满足率':>8}{'缺货天数':>9}{'平均库存':>9}"
              f"{'断货期广告浪费':>13}{'总成本(元)':>12}{'成本降幅':>9}")
    print(header)
    print("-" * 80)
    for r in results:
        drop = (1 - r.total_cost / base.total_cost) * 100
        print(f"{NAMES[r.policy]:<16}{r.fill_rate:>7.1%}{r.stockout_days:>9}"
              f"{r.avg_inventory:>9.0f}{r.ad_waste:>13.0f}{r.total_cost:>12.0f}"
              f"{drop:>8.1f}%")
    r = results[2]
    print(
        f"\n结论：库存-广告联动把总成本再降 "
        f"{(1 - r.total_cost / results[1].total_cost) * 100:.1f}%（对比经典 ROP），"
        f"断货期广告浪费归零、满足率最高({r.fill_rate:.1%})。"
        f"代价是有效需求因广告刹车下移 "
        f"{(1 - (r.filled + r.lost) / (base.filled + base.lost)):.1%}，"
        "其中大部分是无法履约的无效曝光；真实系统可将预算转投有货 SKU。"
    )


if __name__ == "__main__":
    main()
