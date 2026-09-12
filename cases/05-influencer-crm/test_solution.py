"""NO.5 匹配排序与提醒引擎测试：NDCG 层次、SLA 规则、周期对比、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_pipeline, gen_world
from solution import (
    MatchRanker,
    FollowersRanker,
    ReminderEngine,
    RuleRanker,
    fulfillment_cycles,
    hit_at_k,
    ndcg_at_k,
    simulate_missed_followup,
)

WORLD = gen_world()
INFL = WORLD["influencers"]
PRODUCTS = [p for p in WORLD["products"] if p["pid"] in WORLD["gold"]]  # 评测子集
GOLD = WORLD["gold"]


def test_rankers_quality_hierarchy():
    """综合匹配 > 规则加权 > 粉丝量降序（对 gold 的 NDCG@10）。"""
    scores = {}
    for cls in (FollowersRanker, RuleRanker, MatchRanker):
        r = cls()
        s = sum(ndcg_at_k(r.rank(p, INFL), set(GOLD[p["pid"]]))
                for p in PRODUCTS) / len(PRODUCTS)
        scores[cls.__name__] = s
    assert scores["MatchRanker"] > scores["RuleRanker"] > scores["FollowersRanker"], scores


def test_match_ranker_meets_bar():
    r = MatchRanker()
    mean_ndcg = sum(ndcg_at_k(r.rank(p, INFL), set(GOLD[p["pid"]]))
                    for p in PRODUCTS) / len(PRODUCTS)
    mean_hit = sum(hit_at_k(r.rank(p, INFL), set(GOLD[p["pid"]]))
                   for p in PRODUCTS) / len(PRODUCTS)
    assert mean_ndcg >= 0.30 and mean_hit >= 0.6, (mean_ndcg, mean_hit)


def test_reminder_respects_sla():
    tracks = gen_pipeline(n=30)
    eng = ReminderEngine()
    for day in (5, 15, 25):
        for item in eng.today_todo(tracks, day):
            stayed = sum(1 for t in next(tr for tr in tracks if tr["iid"] == item["iid"])
                         ["track"][:day + 1] if t["state"] == item["state"])
            assert stayed == item["overdue_days"]
            assert item["overdue_days"] >= 3  # 最短 SLA（建联 3 天）


def test_todo_sorted_by_overdue():
    tracks = gen_pipeline(n=40)
    todo = ReminderEngine().today_todo(tracks, 20)
    days = [t["overdue_days"] for t in todo]
    assert days == sorted(days, reverse=True)


def test_reminder_cuts_missed_followups():
    tracks = gen_pipeline(n=80)
    r = simulate_missed_followup(tracks)
    assert r["system_missed"] == 0
    assert r["human_missed"] > 0, "人工抽查应存在漏看（对照项）"


def test_reminded_cycle_shorter():
    manual_avg, system_avg = fulfillment_cycles(gen_pipeline(n=120))
    assert 0 < system_avg < manual_avg, f"提醒覆盖组周期应更短: {system_avg} vs {manual_avg}"


def test_deterministic():
    a = MatchRanker().rank(PRODUCTS[0], INFL)[:10]
    b = MatchRanker().rank(PRODUCTS[0], INFL)[:10]
    assert a == b
