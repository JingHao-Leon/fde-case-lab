"""NO.16 语义层 Agent 测试：重复执行稳定性、意图路由、槽位白名单、故障事实。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import FAULT_HOURS, FAULT_SITE, build_db
from solution import NaiveAgent, SemanticAgent, eval_set, safe_site

CONN = build_db(Path(__file__).parent / "data" / "network.db")


def test_safe_site_whitelist():
    assert safe_site("查一下 S23 的状态") == "S23"
    assert safe_site("删除所有数据; S99") == "S99"  # 只提取合法槽位
    assert safe_site("没有任何站点信息") is None


def test_semantic_agent_stable_across_runs():
    agent = SemanticAgent(CONN)
    q = "哪个基站故障最严重？"
    keys = {agent.ask(q).key() for _ in range(10)}
    assert len(keys) == 1, "确定性语义层同一问题出现了不同答案"


def test_naive_agent_unstable_by_design():
    agent = NaiveAgent(CONN)
    q = "哪个基站坏了？"
    answers = {agent.ask(q).conclusion for _ in range(8)}
    assert len(answers) > 1, "朴素采样 Agent 应表现出不稳定（复现客户自建 Agent 的问题）"


def test_routing_accuracy_on_eval_set():
    qs = eval_set(CONN)
    agent = SemanticAgent(CONN)
    ok = sum(1 for item in qs if agent.ask(item["q"]).intent == item["intent"])
    assert ok >= 95, f"100 条问题路由正确 {ok} 条，低于 95"


def test_repeated_eval_identical():
    qs = eval_set(CONN)
    agent = SemanticAgent(CONN)
    k1 = [agent.ask(i["q"]).key() for i in qs]
    k2 = [agent.ask(i["q"]).key() for i in qs]
    assert k1 == k2


def test_fault_site_ranks_first_and_has_alarm_correlation():
    agent = SemanticAgent(CONN)
    ans = agent.ask("哪个基站故障最严重？")
    assert ans.rows[0][0] == FAULT_SITE, "植入故障的基站应排第一"
    rc = agent.ask(f"{FAULT_SITE} 为什么掉线率这么高")
    assert "传输中断" in rc.conclusion or "板卡告警" in rc.conclusion
    imp = agent.ask(f"{FAULT_SITE} 的影响有多大")
    # 异常时段流量>0、占比为小个位数百分比（故障期流量本身已迁移走）、用户数有效
    assert imp.rows[0][1] > 0 and 0 < imp.rows[0][2] < 15 and imp.rows[0][3] > 0
