"""NO.21 回测：系统生成 vs 人工习惯基线 的合规率与设计耗时。

复现：python cases/21-fire-drawing/bench.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_spaces
from solution import (
    BaselineManual,
    SprinklerPlanner,
    compliance_rate,
    hydrant_layout,
    total_heads,
)

DATA = Path(__file__).parent / "data" / "building.json"
MANUAL_MIN_PER_SPACE = 10.0  # 人工绘制+规范核对 10 分钟/空间


def main() -> None:
    if not DATA.exists():
        spaces = gen_spaces()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(
            {"spaces": spaces, "hazard_spec": __import__("data_gen").HAZARD_SPEC,
             "hydrant_r": 25.0, "extinguisher_m": 20.0},
            ensure_ascii=False, indent=1), encoding="utf-8")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    spaces = d["spaces"]
    planner, baseline = SprinklerPlanner(), BaselineManual()

    t0 = time.perf_counter()
    sys_plans = [planner.plan(s) for s in spaces]
    sys_ms = (time.perf_counter() - t0) * 1000
    base_plans = [baseline.plan(s) for s in spaces]

    sys_rate = compliance_rate(sys_plans)
    base_rate = compliance_rate(base_plans)
    heads = total_heads(sys_plans)

    print(f"建筑 {len(spaces)} 个空间 / 总面积 {sum(s['L']*s['W'] for s in spaces):.0f} m²\n")
    print(f"{'方案':<16}{'合规通过率':>9}{'喷头总数':>8}")
    print("-" * 38)
    print(f"{'人工习惯(基线)':<15}{base_rate:>8.0%}{total_heads(base_plans):>8}")
    print(f"{'规范生成+几何校验':<14}{sys_rate:>8.0%}{heads:>8}")
    print(f"\n耗时：系统 {sys_ms:.0f}ms 完成 30 个空间布置+逐项规范校验；"
          f"人工 10 分钟/空间 → {len(spaces)*MANUAL_MIN_PER_SPACE/60:.1f} 小时。"
          f"大型项目（数百空间）从数天 → 约 30 分钟出初稿（案例实测口径）。")
    print("案例对照：70% 执行类工作（绘制+规范检查）由系统承担，"
          "设计人员从执行者转为审核者与决策者。")


if __name__ == "__main__":
    main()
