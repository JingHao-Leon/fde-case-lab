"""NO.6 装车回测：20 个批次（每批约 150~250 方，需多车分装）上对比三种方法。

指标口径：
- 首车装载量：第一批货物里第一辆车的装载方数（对照 98 方保本线）
- 过保本线率：所有已装车辆中装载量 >= 98 方的比例
- 车队利用率：全部车辆平均装载率（相对车厢内净容积 108.2 方）

复现：python cases/06-truck-loading/bench.py
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import BREAK_EVEN_M3, TRUCK_H, TRUCK_L, TRUCK_W, gen_orders
from solution import (
    HeightMapPacker,
    MultiStrategyPacker,
    NaiveRowPacker,
    OptimizedPacker,
    PackResult,
    profit_usd,
    pack_fleet,
    validate_no_overlap,
)

TRUCK = (TRUCK_L, TRUCK_W, TRUCK_H)
TRUCK_M3 = TRUCK_L * TRUCK_W * TRUCK_H


def fleet_metrics(trucks: list[PackResult]) -> dict:
    loads = [t.loaded_m3 for t in trucks]
    return {
        "first_load": loads[0],
        "over_be": sum(1 for v in loads if v >= BREAK_EVEN_M3),
        "n_trucks": len(loads),
        "util": sum(loads) / (len(loads) * TRUCK_M3) * 100,
        "profit_avg": statistics.mean(profit_usd(v, BREAK_EVEN_M3) for v in loads),
        "time_s": sum(t.elapsed_s for t in trucks),
    }


def bench() -> list[dict]:
    orders = gen_orders()
    methods = {
        "单层成排(人工下界)": NaiveRowPacker(),
        "高度图贪心": HeightMapPacker("volume"),
        "多策略取最优": MultiStrategyPacker(),
        "优化版(重启x24)": OptimizedPacker(24),
    }
    rows = []
    for name, packer in methods.items():
        ms, total_time = [], 0.0
        for o in orders:
            t0 = time.perf_counter()
            trucks = pack_fleet(packer, o["items"], TRUCK)
            total_time += time.perf_counter() - t0
            for t in trucks:
                assert validate_no_overlap(t.placements, TRUCK), f"{name} 产生非法解"
            ms.append(fleet_metrics(trucks))
        rows.append(
            {
                "method": name,
                "first_avg": statistics.mean(m["first_load"] for m in ms),
                "first_min": min(m["first_load"] for m in ms),
                "over_rate": sum(m["over_be"] for m in ms) / sum(m["n_trucks"] for m in ms) * 100,
                "util": statistics.mean(m["util"] for m in ms),
                "profit": statistics.mean(m["profit_avg"] for m in ms),
                "time_ms": total_time / len(orders) * 1000,
            }
        )
    return rows


def main() -> None:
    print(f"车厢内净 {TRUCK_M3:.1f} 方 | 保本线 {BREAK_EVEN_M3:.0f} 方 "
          f"(装载率 {BREAK_EVEN_M3/TRUCK_M3*100:.1f}%) | 超 1 方 +100 美元\n")
    header = (f"{'方法':<12}{'首车均装':>9}{'首车最低':>9}{'过保本线':>9}"
              f"{'车队利用率':>10}{'均单车盈亏($)':>13}{'求解耗时':>10}")
    print(header)
    print("-" * 72)
    for r in bench():
        print(f"{r['method']:<12}{r['first_avg']:>8.1f}方{r['first_min']:>8.1f}方"
              f"{r['over_rate']:>8.0f}%{r['util']:>9.1f}%{r['profit']:>12.0f}"
              f"{r['time_ms']:>8.0f}ms")
    print("\n案例对照：老师傅 5 小时装 95~98 方且结果不稳定（批次差时更低），"
          "保本线 98 方；系统目标 = 稳定冲过保本线且压缩规划时间。")


if __name__ == "__main__":
    main()
