"""NO.6 装车求解器测试：正确性、无重叠、可执行顺序、确定性、基线对比。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest

from data_gen import BREAK_EVEN_M3, TRUCK_H, TRUCK_L, TRUCK_W, gen_orders
from solution import (
    HeightMapPacker,
    MultiStrategyPacker,
    NaiveRowPacker,
    Placement,
    profit_usd,
    validate_no_overlap,
)

TRUCK = (TRUCK_L, TRUCK_W, TRUCK_H)
ORDERS = gen_orders()


def test_single_item_places_inside_truck():
    item = [{"spec": "电动摩托C1", "l": 1.9, "w": 0.7, "h": 1.1}]
    r = HeightMapPacker("volume").pack(item, TRUCK)
    assert len(r.placements) == 1
    p = r.placements[0]
    assert 0 <= p.x <= TRUCK_L - p.l + 1e-6
    assert 0 <= p.y <= TRUCK_W - p.w + 1e-6
    assert p.z == 0.0


def test_rotation_enables_fit():
    # 宽比长小很多、横放才能跨过宽度方向已有占位的场景
    blocker = [{"spec": "电动三轮D2", "l": 1.2, "w": 3.0, "h": 1.35}]  # 需要旋转才能放进 2.47m 宽
    r = HeightMapPacker("volume").pack(blocker, TRUCK)
    assert len(r.placements) == 1
    assert r.placements[0].l == pytest.approx(3.0, abs=1e-6)
    assert r.placements[0].w == pytest.approx(1.2, abs=1e-6)


def test_no_overlap_and_bounds_all_methods():
    items = ORDERS[0]["items"]
    for packer in (NaiveRowPacker(), HeightMapPacker("volume"), MultiStrategyPacker()):
        r = packer.pack(items, TRUCK)
        assert validate_no_overlap(r.placements, TRUCK), f"{r.method} 出现重叠或越界"


def test_loaded_volume_matches_placements():
    items = ORDERS[3]["items"]
    r = MultiStrategyPacker().pack(items, TRUCK)
    total = sum(p.l * p.w * p.h for p in r.placements)
    assert abs(total - r.loaded_m3) < 1e-6


def test_multistrategy_beats_naive_on_every_order():
    naive, multi = NaiveRowPacker(), MultiStrategyPacker()
    for o in ORDERS[:5]:
        rn, rm = naive.pack(o["items"], TRUCK), multi.pack(o["items"], TRUCK)
        assert rm.loaded_m3 > rn.loaded_m3, f"订单 {o['order_id']} 多策略未超过基线"


def test_loading_sequence_is_deep_first_low_first():
    """截面式装载顺序：位置由内向外（x 递增）、同截面内由低到高（z 允许顺序）。"""
    r = MultiStrategyPacker().pack(ORDERS[1]["items"], TRUCK)
    seq = r.placements
    # 装载顺序中，任意一步放置的箱底高度，等于此刻高度图上该足迹的高度
    # （即每一步都站在"已装货物"或车厢地板上，现场可逐箱执行）
    executed: list[Placement] = []
    for p in seq:
        support = 0.0
        for q in executed:
            ox = min(p.x + p.l, q.x + q.l) - max(p.x, q.x)
            oy = min(p.y + p.w, q.y + q.w) - max(p.y, q.y)
            if ox > 1e-6 and oy > 1e-6:
                support = max(support, q.z + q.h)
        assert abs(p.z - support) < 0.11, f"箱 {p.spec} 悬空 {p.z} vs 支撑 {support}"
        executed.append(p)


def test_deterministic():
    r1 = MultiStrategyPacker().pack(ORDERS[0]["items"], TRUCK)
    r2 = MultiStrategyPacker().pack(ORDERS[0]["items"], TRUCK)
    key = [(p.spec, round(p.x, 3), round(p.y, 3), round(p.z, 3)) for p in r1.placements]
    key2 = [(p.spec, round(p.x, 3), round(p.y, 3), round(p.z, 3)) for p in r2.placements]
    assert key == key2 and abs(r1.loaded_m3 - r2.loaded_m3) < 1e-9


def test_profit_model():
    assert profit_usd(98.0) == 0.0
    assert profit_usd(100.0) == 200.0
    assert profit_usd(90.0) == -800.0
    assert profit_usd(97.0, break_even=BREAK_EVEN_M3) == -100.0
