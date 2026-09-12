"""NO.4 选址筛查测试：硬约束零漏筛、Top-K 一致性、依据完整、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import EXPERT_W, expert_score, gen_parcels
from solution import SiteScreener, spearman, topk_overlap

PARCELS = gen_parcels()
for _p in PARCELS:
    _p["expert_score"] = expert_score(_p)


def _expert_top(parcels, k=10):
    scored = [(p["pid"], p["expert_score"]) for p in parcels
              if not p["constraint"] and p["expert_score"] is not None]
    scored.sort(key=lambda x: -x[1])
    return [pid for pid, _ in scored[:k]]


def test_hard_constraints_zero_leak():
    """触碰红线/文化线/断裂带的地块绝不能进入推荐名单。"""
    r = SiteScreener().screen(PARCELS, top_k=20)
    top_ids = {t["pid"] for t in r["top"]}
    constrained = {p["pid"] for p in PARCELS if p["constraint"]}
    assert not (top_ids & constrained), "硬约束地块混入推荐名单"
    assert len(r["rejected"]) == len(constrained)


def test_top10_overlap_with_expert():
    """默认权重 Top10 与专家 gold Top10 重合率 ≥ 0.6。"""
    r = SiteScreener().screen(PARCELS, top_k=10)
    assert topk_overlap([t["pid"] for t in r["top"]], _expert_top(PARCELS)) >= 0.6


def test_spearman_positive_with_expert_weights():
    """用专家权重跑筛查，全序应与专家排序高度相关。"""
    r = SiteScreener(weights=EXPERT_W).screen(PARCELS, top_k=50)
    order = [t["pid"] for t in r["top"]]
    expert_all = sorted((p for p in PARCELS if not p["constraint"]),
                        key=lambda p: -p["expert_score"])
    ra = {pid: i for i, pid in enumerate(order)}
    rb = {p["pid"]: i for i, p in enumerate(expert_all[:50])}
    rho = spearman(ra, rb)
    assert rho > 0.8, f"Spearman {rho:.2f} 过低"


def test_recommendation_has_evidence():
    r = SiteScreener().screen(PARCELS[:50], top_k=5)
    for t in r["top"]:
        assert set(t["detail"]) == {"area", "road", "utility", "sewage",
                                    "service", "cost"}
    assert "一票否决" in r["report"] or len(r["rejected"]) == 0


def test_rejection_reason_recorded():
    r = SiteScreener().screen(PARCELS, top_k=5)
    for item in r["rejected"]:
        assert item["rejected_by"] in ("历史文化保护线", "生态红线", "断裂带避让区")


def test_deterministic():
    a = SiteScreener().screen(PARCELS)
    b = SiteScreener().screen(PARCELS)
    assert a == b
