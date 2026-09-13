"""NO.5 达人匹配与履约提醒求解器。

对应 NO.5 的两个核心改造：
- 三档匹配排序：粉丝量降序（人工现状）→ 类目+转化率规则 → 类目+标签+粉丝段+转化率
  综合评分。评价：NDCG@10 / HitRate@10（对隐含 gold 优质达人集合）。
- 履约提醒引擎：状态机超时规则 → 今日待办清单（按逾期天数排序）。
  对照"人工翻 Excel 抽查"的漏催率；用轨迹数据回测提醒对履约周期的影响。
"""
from __future__ import annotations

import math

STATE_ORDER = ["建联", "寄样", "收样", "创作", "提交"]
SLA = {"建联": 3, "寄样": 4, "收样": 3, "创作": 7, "提交": 999}  # 各状态停留上限（天）


class FollowersRanker:
    """人工现状：谁粉丝多先找谁。"""

    def rank(self, product: dict, influencers: list[dict]) -> list[str]:
        return [i["iid"] for i in sorted(influencers, key=lambda x: -x["followers"])]


class RuleRanker:
    """规则加权：类目一致 + 历史转化率 + 响应率。"""

    def rank(self, product: dict, influencers: list[dict]) -> list[str]:
        def score(i: dict) -> float:
            s = 0.0
            if i["cat"] == product["cat"]:
                s += 2.0
            s += i["hist_conv"] * 10 + i["reply_rate"]
            return s
        return [i["iid"] for i in sorted(influencers, key=lambda x: -score(x))]


class MatchRanker:
    """综合匹配：类目 × 卖点标签重叠 × 黄金粉丝段 × 转化率 × 响应率。

    对应案例里"商品卖点 × 达人内容属性"的匹配层——AI 先筛，人再沟通。
    """

    def rank(self, product: dict, influencers: list[dict]) -> list[str]:
        def score(i: dict) -> float:
            s = 0.0
            if i["cat"] == product["cat"]:
                s += 2.0
            s += 1.5 * len(set(i["tags"]) & set(product["tags"]))
            if 10_000 <= i["followers"] <= 500_000:
                s += 1.0
            s += i["hist_conv"] * 10 + i["reply_rate"]
            return s
        return [i["iid"] for i in sorted(influencers, key=lambda x: -score(x))]


def ndcg_at_k(rank: list[str], gold: set[str], k: int = 10) -> float:
    dcg = sum(1 / math.log2(pos + 1) for pos, iid in enumerate(rank[:k], 1)
              if iid in gold)
    ideal = sum(1 / math.log2(pos + 1) for pos in range(1, min(len(gold), k) + 1))
    return dcg / ideal if ideal else 0.0


def hit_at_k(rank: list[str], gold: set[str], k: int = 10) -> float:
    return len(set(rank[:k]) & gold) / k


class ReminderEngine:
    """履约状态机超时提醒：状态停留超过 SLA → 进入今日待办，按逾期排序。"""

    def today_todo(self, tracks: list[dict], day: int) -> list[dict]:
        todo = []
        for tr in tracks:
            cur = tr["track"][day]
            if cur["state"] == "提交":
                continue
            overdue = sum(1 for t in tr["track"][:day + 1] if t["state"] == cur["state"])
            if overdue >= SLA[cur["state"]]:
                todo.append({"iid": tr["iid"], "state": cur["state"],
                             "overdue_days": overdue})
        todo.sort(key=lambda x: -x["overdue_days"])
        return todo


def simulate_missed_followup(tracks: list[dict], days: int = 30,
                             human_recall: float = 0.7, seed: int = 3) -> dict:
    """对照实验：人工翻 Excel 每天只能发现 70% 的逾期；系统提醒全量覆盖。"""
    import random
    rng = random.Random(seed)
    eng = ReminderEngine()
    human_miss = sys_miss = 0
    for d in range(days):
        todo = eng.today_todo(tracks, d)
        sys_miss += 0  # 引擎是全量扫描，不存在漏看
        found = max(0, int(len(todo) * human_recall + rng.gauss(0, 0.5)))
        human_miss += len(todo) - min(found, len(todo))
    return {"human_missed": human_miss, "system_missed": sys_miss}


def fulfillment_cycles(tracks: list[dict]) -> tuple[float, float]:
    """manual 组 vs system 组的平均履约完成天数（低提醒覆盖 vs 高提醒覆盖）。"""
    cov, uncov = [], []
    for tr in tracks:
        if tr["finish_day"] is None:
            continue
        (cov if tr.get("regime") == "system" else uncov).append(tr["finish_day"])
    if not cov or not uncov:
        return -1.0, -1.0
    return sum(uncov) / len(uncov), sum(cov) / len(cov)
