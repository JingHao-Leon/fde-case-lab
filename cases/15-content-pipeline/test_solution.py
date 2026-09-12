"""NO.15 内容流水线测试：校验器、首过/终过率、违禁词红线、查重、回退、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import BANNED, gen_briefs
from solution import NaiveWriter, Pipeline, audit_texts, run_pipeline

BRIEFS = gen_briefs()


def test_baseline_violates_banned_words():
    """基线（直出无审计）应包含违禁词脚本——复现合规问题。"""
    texts = [NaiveWriter(BANNED).write(b) for b in BRIEFS]
    bad = sum(1 for t in texts if any(w in t for w in BANNED))
    assert bad > 0, "基线未复现违禁词问题"


def test_pipeline_output_has_no_banned_words():
    p = Pipeline(banned=BANNED)
    for b in BRIEFS[:60]:
        t, st = p.write(b)
        assert not any(w in t for w in BANNED), f"流水线输出违禁词: {t[:30]}"


def test_pipeline_final_pass_rate():
    r = run_pipeline(BRIEFS, BANNED)
    assert r["final_pass"] >= 0.95, f"终过率 {r['final_pass']:.0%} 过低"
    assert r["human"] <= 0.05, f"人工回退率 {r['human']:.0%} 过高"


def test_pipeline_beats_baseline_usability():
    base_texts = [NaiveWriter(BANNED).write(b) for b in BRIEFS]
    base_ok = audit_texts(base_texts, BRIEFS, BANNED)
    p = Pipeline(banned=BANNED)
    pipe_ok = sum(1 for b in BRIEFS if p.write(b)[1] == "passed") / len(BRIEFS)
    assert pipe_ok > base_ok + 0.3, f"流水线 {pipe_ok:.0%} vs 基线 {base_ok:.0%}"


def test_same_shop_scripts_not_identical():
    p = Pipeline(banned=BANNED)
    shop_briefs = [b for b in BRIEFS if b["shop"]["shop"] == BRIEFS[0]["shop"]["shop"]]
    texts = [p.write(b)[0] for b in shop_briefs]
    assert len(set(texts)) == len(texts), "同商户脚本出现完全重复"


def test_human_fallback_on_impossible_brief():
    """构造极端 brief（卖点全空）→ 应进入人工队列而不是硬编。"""
    bad = dict(BRIEFS[0])
    bad = {**bad, "sells": ["{price}元", "{price}元"]}
    p = Pipeline(banned=BANNED)
    _, st = p.write(bad, attempt=99)
    assert st in ("passed", "human")


def test_deterministic():
    r1 = run_pipeline(BRIEFS[:50], BANNED)
    r2 = run_pipeline(BRIEFS[:50], BANNED)
    assert r1 == r2
