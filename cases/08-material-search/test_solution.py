"""NO.8 物料搜索测试：归一化、查询命中、重复拦截的查全与查准、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import gen_catalog, gen_queries
from solution import FuzzyHybrid, KeywordSearch, NormalizedTfidf, normalize

CAT = gen_catalog()
RECORDS = CAT["records"]
QUERIES = gen_queries(CAT["truth"])
CLEAN = [r for r in RECORDS if r["variant"] == "clean"]
DUPS = [r for r in RECORDS if r["variant"] != "clean"]
HYBRID = FuzzyHybrid(CLEAN)  # 主数据核查库 = 干净记录


def test_normalize_rules():
    assert normalize("[R120-300]内六角螺栓 M8x20mm") == normalize("内六角螺栓 M8x20")
    assert normalize("Ｏ型圈 20x3mm") == normalize("o型圈 20x3")
    assert normalize("圆柱头螺钉 M8x20") == normalize("内六角螺栓 M8x20")


def test_query_hit_rate_hybrid():
    ok1 = ok5 = 0
    for q in QUERIES:
        top = HYBRID.search(q["q"], k=5)
        if top and top[0][0] == q["gold"]:
            ok1 += 1
        if any(g == q["gold"] for g, _ in top):
            ok5 += 1
    assert ok1 / len(QUERIES) >= 0.6, f"Top1 {ok1/len(QUERIES):.0%} 过低"
    assert ok5 / len(QUERIES) >= 0.85, f"Top5 {ok5/len(QUERIES):.0%} 过低"


def test_hybrid_beats_keyword_on_queries():
    kw = KeywordSearch(CLEAN)
    ok_kw = sum(1 for q in QUERIES
                if any(g == q["gold"] for g, _ in kw.search(q["q"], k=5)))
    ok_hy = sum(1 for q in QUERIES
                if any(g == q["gold"] for g, _ in HYBRID.search(q["q"], k=5)))
    assert ok_hy > ok_kw


def test_duplicate_blocking_precision_recall():
    """三态判定：变体应被 exact 拦截或 suspect 送审（合计 100%）；
    干净记录的自动拦截误报必须为 0，人工确认率应低。"""
    verdicts = [HYBRID.is_duplicate(r) for r in DUPS[:200]]
    caught = sum(1 for v in verdicts if v in ("exact", "suspect"))
    exact = sum(1 for v in verdicts if v == "exact")
    assert caught / 200 == 1.0, "变体记录未被全部拦下"
    assert exact / 200 >= 0.6, f"自动拦截率 {exact/200:.0%} 过低"
    fp = [r for r in CLEAN[:200] if HYBRID.is_duplicate(r, exclude_gid=r["gid"]) == "exact"]
    assert not fp, "自动拦截出现误报（把新物料当成重复）"
    suspect_rate = sum(1 for r in CLEAN[:200]
                       if HYBRID.is_duplicate(r, exclude_gid=r["gid"]) == "suspect") / 200
    assert suspect_rate <= 0.30, f"干净记录人工确认率 {suspect_rate:.0%} 过高"


def test_tfidf_ranking_wellformed():
    s = NormalizedTfidf(CLEAN)
    top = s.search("深沟球轴承 20x47x14 NSK", k=5)
    assert len(top) == 5 and top == sorted(top, key=lambda x: -x[1])


def test_deterministic():
    a = [HYBRID.search(q["q"], k=3) for q in QUERIES[:10]]
    b = [HYBRID.search(q["q"], k=3) for q in QUERIES[:10]]
    assert a == b
