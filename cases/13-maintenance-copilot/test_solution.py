"""NO.13 复用推荐与路由测试：命中率、字符节省、路由层次、回退、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_data
from solution import ReuseRecommender, Router, route_accuracy

DATA = gen_data()
HIST, PENDING = DATA["history"], DATA["pending"]
REC = ReuseRecommender(HIST, DATA["devices"])
ROUTER = Router(HIST, DATA["devices"])


def test_reuse_hit_rate():
    r = REC.audit(PENDING)
    assert r["hit_rate"] >= 0.7, f"自动填充命中率 {r['hit_rate']:.0%} 过低"


def test_chars_saved_substantial():
    r = REC.audit(PENDING)
    assert r["chars_saved"] >= 0.6, f"录入字符节省 {r['chars_saved']:.0%} 过低"


def test_router_hierarchy():
    a0 = route_accuracy(ROUTER.route_v0, PENDING)
    a1 = route_accuracy(ROUTER.route_v1, PENDING)
    a2 = route_accuracy(ROUTER.route_v2, PENDING)
    assert a1 > a0, "规则路由应优于全部塞给综合组"
    assert a2 >= a1, "历史多数票校正不应变差"
    assert a2 >= 0.95


def test_new_device_fallback():
    """新设备（无历史）应回退到类型规则路由而不是报错。"""
    assert ROUTER.route_v2("DUNKNOWN") == ROUTER.route_v1("DUNKNOWN")


def test_recommend_returns_none_for_unknown_device():
    assert REC.recommend("DUNKNOWN") is None


def test_deterministic():
    a = REC.audit(PENDING)
    b = REC.audit(PENDING)
    assert a == b
