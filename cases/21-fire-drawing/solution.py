"""NO.21 消防布置求解器：规范查表生成 + 几何合规验证。

对应 NO.21 的「规范规则化 + AI 生成 + 人审核」：

- SpecTable        规范查表：空间类型 → 危险等级 → (K, 最大间距 S_max, 保护半径 R)。
- SprinklerPlanner 网格布置：n = ceil(边长/S_max)，实际间距 = 边长/n ≤ S_max，
  喷头置于等分格心。合规验证做两件事：
    V1 间距校验：实际间距 ≤ 规范上限；
    V2 覆盖校验：0.5m 网格采样全空间，任一点到最近喷头距离 ≤ 保护半径
      （吊投影几何，确定性、可复核）。
- BaselineManual   人工经验基线：所有空间统一 4.0m 间距、不按等级调参
  （复现"因人而异、按习惯画"的合规风险）。
- 消火栓：沿长边按保护半径布点，校验每个空间中心可达。
"""
from __future__ import annotations

import math

from data_gen import EXTINGUISHER_M, HAZARD_SPEC, HYDRANT_R


class SprinklerPlanner:
    def plan(self, space: dict) -> dict:
        spec = HAZARD_SPEC[space["hazard"]]
        s_max, radius = spec["S_max"], spec["R"]
        nx = math.ceil(space["L"] / s_max)
        ny = math.ceil(space["W"] / s_max)
        sx, sy = space["L"] / nx, space["W"] / ny
        heads = [((i + 0.5) * sx, (j + 0.5) * sy)
                 for i in range(nx) for j in range(ny)]
        covered = self._coverage_ok(space, heads, radius)
        return {
            "sid": space["sid"], "K": spec["K"], "n_heads": len(heads),
            "spacing": (round(sx, 2), round(sy, 2)),
            "spacing_ok": sx <= s_max + 1e-9 and sy <= s_max + 1e-9,
            "coverage_ok": covered,
            "heads": heads,
        }

    @staticmethod
    def _coverage_ok(space: dict, heads: list[tuple[float, float]], radius: float,
                     step: float = 0.5) -> bool:
        """0.5m 网格采样：任一点到最近喷头距离 ≤ 保护半径。"""
        L, W = space["L"], space["W"]
        nx_s, ny_s = int(L / step), int(W / step)
        for i in range(nx_s + 1):
            for j in range(ny_s + 1):
                x, y = min(i * step, L), min(j * step, W)
                if min(math.hypot(x - hx, y - hy) for hx, hy in heads) > radius:
                    return False
        return True


class BaselineManual:
    """人工经验基线：全空间统一 4.0m 间距，不区分危险等级。"""

    S = 4.0

    def plan(self, space: dict) -> dict:
        spec = HAZARD_SPEC[space["hazard"]]
        nx = math.ceil(space["L"] / self.S)
        ny = math.ceil(space["W"] / self.S)
        sx, sy = space["L"] / nx, space["W"] / ny
        heads = [((i + 0.5) * sx, (j + 0.5) * sy)
                 for i in range(nx) for j in range(ny)]
        return {
            "sid": space["sid"], "K": spec["K"], "n_heads": len(heads),
            "spacing": (round(sx, 2), round(sy, 2)),
            "spacing_ok": (spec["S_max"] >= sx - 1e-9
                           and spec["S_max"] >= sy - 1e-9),
            "coverage_ok": SprinklerPlanner._coverage_ok(space, heads, spec["R"]),
            "heads": heads,
        }


def hydrant_layout(spaces: list[dict], floor_L: float, floor_W: float) -> dict:
    """沿长边布消火栓，间距 ≤ 保护半径的 √2 倍（最坏对角覆盖），校验空间中心可达。"""
    n = max(2, math.ceil(floor_L / (HYDRANT_R * 0.8)))
    xs = [floor_L * (i + 0.5) / n for i in range(n)]
    hydrants = [(x, floor_W / 2) for x in xs]
    gaps = []
    for s in spaces:
        cx, cy = s["L"] / 2, s["W"] / 2
        d = min(math.hypot(cx - hx, cy - hy) for hx, hy in hydrants)
        gaps.append((s["sid"], round(d, 1)))
    worst = max(g for _, g in gaps)
    return {"n": n, "hydrants": hydrants, "worst_gap_m": worst,
            "ok": worst <= HYDRANT_R,
            "extinguisher_ok": worst <= EXTINGUISHER_M}


def compliance_rate(plans: list[dict]) -> float:
    ok = sum(1 for p in plans if p["spacing_ok"] and p["coverage_ok"])
    return ok / len(plans)


def total_heads(plans: list[dict]) -> int:
    return sum(p["n_heads"] for p in plans)
