"""NO.16 网络分析 Agent：确定性语义层 + 查询规划器 vs 朴素关键词 Agent。

对应案例 NO.16 的核心观点：**"能跑起来"和"可以生产使用"是两回事**——
模型随机性不能成为业务系统不稳定的借口（汽油不稳定，但汽车工程让它安全驱动）。

- NaiveAgent      模拟客户自建的"提示词 Agent"：不做意图规划，关键词捞候选后
                  按哈希计数器"采样"输出（同一问题两次可能不同答案）。
- SemanticAgent   确定性流水线：问题 → 意图识别 → 槽位白名单校验 → 参数化 SQL
                  → 结构化答案(结论+数据+SQL)。同一问题重复执行逐位一致，可审计。

意图集（对应分析师日常追问）：rank_faults / site_status / impact / root_cause / trend
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field

import pandas as pd

SITE_RE = re.compile(r"S\d{2}")  # 站点槽位白名单格式


@dataclass
class Answer:
    intent: str
    conclusion: str
    rows: list = field(default_factory=list)
    sql: str = ""

    def key(self) -> str:
        return f"{self.intent}|{self.conclusion}|{self.rows}"


def safe_site(text: str) -> str | None:
    """槽位白名单：只放行 Sxx 形式的站点号，自由文本不进查询层。"""
    m = SITE_RE.search(text)
    return m.group(0) if m else None


def scalar(df: pd.DataFrame):
    return df.iloc[0, 0]


class NaiveAgent:
    """"提示词 Agent"基线：候选池 + 逐次变化的伪采样（模拟 temperature>0）。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._calls = 0

    def ask(self, q: str) -> Answer:
        df = pd.read_sql_query(
            "SELECT site_id, AVG(drop_rate) dr FROM kpi GROUP BY site_id", self.conn)
        cands = df.sort_values("dr", ascending=False).site_id.head(5).tolist()
        self._calls += 1
        digest = hashlib.sha256(f"{q}#{self._calls}".encode()).hexdigest()
        pick = cands[int(digest, 16) % len(cands)]
        return Answer("guess", f"可能是 {pick} 有问题（关键词匹配+采样，未经聚合验证）")


class SemanticAgent:
    INTENTS = [
        ("impact", re.compile(r"(影响|波及|多少用户|多少流量)")),
        ("root_cause", re.compile(r"(为什么|原因|根因|怎么会)")),
        ("site_status", re.compile(r"(表现|状态|情况)")),
        ("trend", re.compile(r"(趋势|近\s*\d+\s*天|这几天)")),
        ("rank_faults", re.compile(r"(哪个|最严重|故障最多|坏了|有问题|异常|吗)")),
    ]

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ask(self, q: str) -> Answer:
        intent = self._intent(q)
        site = safe_site(q)
        dispatch = {
            "rank_faults": self._rank_faults,
            "site_status": lambda: self._site_status(site or "S00"),
            "impact": lambda: self._impact(site or self._worst_site()),
            "root_cause": lambda: self._root_cause(site or self._worst_site()),
            "trend": lambda: self._trend(site or "S00"),
        }
        return dispatch[intent]()

    def _intent(self, q: str) -> str:
        for name, pat in self.INTENTS:
            if pat.search(q):
                return name
        return "rank_faults"

    def _worst_site(self) -> str:
        df = pd.read_sql_query(
            "SELECT site_id FROM kpi GROUP BY site_id ORDER BY AVG(drop_rate) DESC LIMIT 1",
            self.conn)
        return df.site_id[0]

    def _rank_faults(self) -> Answer:
        sql = ("SELECT site_id, ROUND(AVG(drop_rate)*100,2) drop_pct, "
               "ROUND(SUM(traffic_gb),1) traffic FROM kpi GROUP BY site_id "
               "ORDER BY AVG(drop_rate) DESC LIMIT 3")
        df = pd.read_sql_query(sql, self.conn)
        rows = df.values.tolist()
        return Answer("rank_faults",
                      f"掉线率最严重的基站是 {rows[0][0]}（平均掉线率 {rows[0][1]}%），"
                      f"其后为 {rows[1][0]}、{rows[2][0]}。", rows, sql)

    def _site_status(self, site: str) -> Answer:
        sql = ("SELECT COUNT(*) n, ROUND(AVG(drop_rate)*100,2) drop_pct, "
               "ROUND(AVG(setup_rate)*100,2) setup_pct, ROUND(SUM(traffic_gb),1) traf "
               "FROM kpi WHERE site_id=?")
        df = pd.read_sql_query(sql, self.conn, params=(site,))
        n, drop, setup, traf = df.iloc[0].tolist()
        healthy = drop < 5
        return Answer("site_status",
                      f"{site} 共 {n} 小时数据：平均掉线率 {drop}%、接通率 {setup}%、"
                      f"总流量 {traf}GB，{'整体正常' if healthy else '存在异常时段'}。",
                      df.values.tolist(), sql)

    def _impact(self, site: str) -> Answer:
        sql = ("SELECT COALESCE(ROUND(SUM(traffic_gb),1),0) v FROM kpi "
               "WHERE site_id=? AND drop_rate>0.1")
        sql2 = "SELECT COALESCE(ROUND(SUM(traffic_gb),1),0) v FROM kpi WHERE site_id=?"
        bad_traf = scalar(pd.read_sql_query(sql, self.conn, params=(site,)))
        all_traf = scalar(pd.read_sql_query(sql2, self.conn, params=(site,)))
        users = scalar(pd.read_sql_query(
            "SELECT users FROM sites WHERE site_id=?", self.conn, params=(site,)))
        pct = bad_traf / all_traf * 100 if all_traf else 0
        return Answer("impact",
                      f"{site} 异常时段承载流量 {bad_traf}GB（占该站 {pct:.1f}%），"
                      f"影响在网用户约 {users} 名。", [(site, bad_traf, pct, users)],
                      f"{sql} ; {sql2}")

    def _root_cause(self, site: str) -> Answer:
        sql = ("SELECT alarm_type, COUNT(*) n FROM alarms WHERE site_id=? GROUP BY "
               "alarm_type ORDER BY n DESC LIMIT 3")
        df = pd.read_sql_query(sql, self.conn, params=(site,))
        if df.empty:
            return Answer("root_cause", f"{site} 无告警记录，掉线率异常需查传输上游。",
                          [], sql)
        rows = df.values.tolist()
        extra = f"，另有 {rows[1][0]} × {rows[1][1]} 次" if len(rows) > 1 else ""
        return Answer("root_cause",
                      f"{site} 掉线率异常与告警强相关：{rows[0][0]} × {rows[0][1]} 次{extra}。",
                      rows, sql)

    def _trend(self, site: str) -> Answer:
        sql = ("SELECT day, ROUND(AVG(drop_rate)*100,2) drop_pct FROM kpi WHERE site_id=? "
               "GROUP BY day ORDER BY day")
        df = pd.read_sql_query(sql, self.conn, params=(site,))
        first, last = df.drop_pct[0], df.drop_pct.iloc[-1]
        direction = "上升" if last > first * 1.3 else ("下降" if last < first * 0.7 else "平稳")
        return Answer("trend", f"{site} 近 {len(df)} 天掉线率整体{direction}"
                      f"（{first}% → {last}%）。", df.values.tolist(), sql)


def eval_set(conn: sqlite3.Connection) -> list[dict]:
    """100 条评测问题（意图 × 站点槽位），gold 由参考实现（确定性 Agent）推导。"""
    qs = []
    sites = pd.read_sql_query("SELECT site_id FROM sites", conn).site_id.tolist()
    agent = SemanticAgent(conn)
    for s in sites[:20]:
        qs.append({"q": f"{s} 这个基站故障最严重吗", "intent": "rank_faults"})
    for s in sites[20:45]:
        qs.append({"q": f"基站 {s} 状态怎么样", "intent": "site_status"})
    for s in sites[45:]:
        qs.append({"q": f"{s} 的影响有多大", "intent": "impact"})
    for s in sites[:15]:
        qs.append({"q": f"{s} 为什么掉线率这么高", "intent": "root_cause"})
    for s in sites[15:30]:
        qs.append({"q": f"{s} 近 7 天掉线率趋势如何", "intent": "trend"})
    for s in sites[30:50]:
        qs.append({"q": f"看一下 {s} 的情况，为什么{agent._worst_site()}会这样",
                   "intent": "root_cause"})
    for item in qs:
        ans = agent.ask(item["q"])
        item["gold_key"] = ans.key()
        item["gold_conclusion"] = ans.conclusion
    return qs
