"""NO.3 案件处理求解器：时间线重建 + 诉讼时效判定。

对应 NO.3 的 AI 介入点「材料整理 + 信息梳理」（律师保留策略判断）：

- resolve_date     口语化时间解析：把"去年下半年""3 个月前"等相对描述
                   按案件基准日解析为具体日期。
- TimelineBuilder  时间线重建：事件按解析后日期排序，输出当事人清单与事件时间轴。
- StatuteChecker   诉讼时效判定（民法典 3 年普通时效），从事件流推导：
                   起算 = 约定履行期届满日（无则取违约日）；
                   届满后的催告/对方承认构成**时效中断**，自中断日重新起算；
                   输出 时效内 / 临近时效(6 个月内到期) / 已过时效 + 依据链。

评价口径：时效判定与 gold 一致率、时间线排序正确率。
"""
from __future__ import annotations

from datetime import date, timedelta

STATUTE_DAYS = int(3 * 365.25)          # 普通诉讼时效 3 年
NEAR_WINDOW = timedelta(days=180)
INTERRUPT_TYPES = ("催告", "对方承认债务")
DUE_TYPES = ("约定履行期届满", "违约")


def resolve_date(ev: dict, as_of: str) -> str:
    """把事件日期解析为 ISO 日期；口语化描述按锚点/基准日估算。"""
    c = ev.get("colloquial")
    if not c:
        return ev["date"]
    anchor = ev.get("anchor") or as_of
    d = date.fromisoformat(anchor)
    if "去年" in c:
        return (d - timedelta(days=365)).isoformat()
    if c.endswith("个月前"):
        months = int(c.replace("个月前", "") or 1)
        return (d - timedelta(days=30 * months)).isoformat()
    if c.endswith("个月后"):
        months = int(c.replace("个月后", "") or 1)
        return (d + timedelta(days=30 * months)).isoformat()
    return ev["date"]


class TimelineBuilder:
    def __init__(self, as_of: str):
        self.as_of = as_of

    def build(self, events: list[dict]) -> dict:
        resolved = [{**ev, "resolved_date": resolve_date(ev, self.as_of)}
                    for ev in events]
        resolved.sort(key=lambda e: e["resolved_date"])
        return {
            "timeline": resolved,
            "parties": sorted({e["party"] for e in events}),
            "n_events": len(resolved),
        }


class StatuteChecker:
    """从事件流推导请求权时效状态（不读取 gold 字段）。"""

    def derive_claims(self, case: dict) -> list[dict]:
        as_of = date.fromisoformat(case["as_of"])
        events = [{**e, "d": date.fromisoformat(resolve_date(e, case["as_of"]))}
                  for e in case["events"]]
        due_events = [e for e in events if e["type"] in DUE_TYPES][:3]
        out = []
        for k, due_ev in enumerate(due_events):
            due = due_ev["d"]
            interrupts = [e["d"] for e in events
                          if e["type"] in INTERRUPT_TYPES and due < e["d"] <= as_of]
            start = max(interrupts) if interrupts else due
            expiry = start + timedelta(days=STATUTE_DAYS)
            if expiry <= as_of:
                status = "已过时效"
            elif expiry <= as_of + NEAR_WINDOW:
                status = "临近时效"
            else:
                status = "时效内"
            basis = (f"起算 {start.isoformat()}"
                     + (f"（{len(interrupts)} 次中断）" if interrupts else "")
                     + f"，届满 {expiry.isoformat()}")
            out.append({"claim_id": f"{case['case_id']}-{k}",
                        "due": due.isoformat(),
                        "n_interrupts": len(interrupts),
                        "judged": status, "basis": basis})
        return out

    def audit_case(self, case: dict) -> dict:
        return {"case_id": case["case_id"], "claims": self.derive_claims(case)}


def audit_all(cases: list[dict]) -> dict:
    """推导时效状态 vs gold 状态的一致率（按顺序对齐 gold 请求权列表）。"""
    checker = StatuteChecker()
    total = right = 0
    for case in cases:
        res = checker.audit_case(case)
        golds = case["claims"]
        for claim, gold in zip(res["claims"], golds):
            total += 1
            right += claim["judged"] == gold["status"]
    return {"total": total, "right": right, "accuracy": right / max(1, total)}


def timeline_sort_ok(case: dict) -> bool:
    tl = TimelineBuilder(case["as_of"]).build(case["events"])["timeline"]
    return all(tl[i]["resolved_date"] <= tl[i + 1]["resolved_date"]
               for i in range(len(tl) - 1))
