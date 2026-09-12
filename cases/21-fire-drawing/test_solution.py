"""NO.21 消防布置测试：参数匹配、间距上限、几何覆盖、基线违规复现、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import HAZARD_SPEC, gen_spaces
from solution import (
    BaselineManual,
    SprinklerPlanner,
    compliance_rate,
    hydrant_layout,
)

SPACES = gen_spaces()


def test_spec_lookup_matches_hazard():
    p = SprinklerPlanner()
    r = p.plan(SPACES[0])
    assert r["K"] == HAZARD_SPEC[SPACES[0]["hazard"]]["K"]


def test_spacing_within_code_limit():
    for s in SPACES:
        r = SprinklerPlanner().plan(s)
        sx, sy = r["spacing"]
        s_max = HAZARD_SPEC[s["hazard"]]["S_max"]
        assert sx <= s_max + 1e-6 and sy <= s_max + 1e-6, f"{s['sid']} 间距超限"


def test_full_coverage_all_spaces():
    for s in SPACES:
        r = SprinklerPlanner().plan(s)
        assert r["coverage_ok"], f"{s['sid']} 存在保护盲区"
        assert r["spacing_ok"]


def test_baseline_shows_violations():
    """统一 4.0m 间距的人工习惯基线：应复现间距/覆盖违规。"""
    plans = [BaselineManual().plan(s) for s in SPACES]
    rate = compliance_rate(plans)
    assert rate < 0.9, f"基线合规率 {rate:.0%} 过高，未复现差异"


def test_planner_beats_baseline_compliance():
    sys_rate = compliance_rate([SprinklerPlanner().plan(s) for s in SPACES])
    base_rate = compliance_rate([BaselineManual().plan(s) for s in SPACES])
    assert sys_rate == 1.0 and sys_rate > base_rate


def test_hydrant_layout_covers_floor():
    h = hydrant_layout(SPACES, floor_L=60.0, floor_W=18.0)
    assert h["ok"] and h["worst_gap_m"] <= 25.0


def test_head_count_reasonable():
    """喷头数下界：总面积 / 单头保护面积（向上取整容差）。"""
    plans = [SprinklerPlanner().plan(s) for s in SPACES]
    area = sum(s["L"] * s["W"] for s in SPACES)
    total = sum(p["n_heads"] for p in plans)
    assert total >= area / 12.5 * 0.9
