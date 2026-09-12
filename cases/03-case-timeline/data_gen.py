"""NO.3 诉讼案件处理：生成案件事件流与待检请求权数据。

场景来自《Datawhale FDE 案例 100》NO.3：商事诉讼律师，材料整理耗费 3~5 个
工作日（14 被告的请求权基础分析要 2~3 天）；AI 辅助后一晚完成，效率 +70%。

数据模型（20 个案件 × 15~40 条事件）：
- 事件类型：合同签订 / 约定履行期 / 违约 / 催告 / 对方承认(时效中断) / 起诉意向；
- 一部分事件以口语化时间出现（"去年年底""三个月后"），需相对基准日解析；
- 每个案件附若干请求权（claim）：需判定诉讼时效（3 年）状态——
  起算点 = 约定履行期届满日；催告/承认构成时效中断，从中断日重新起算。
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

STATUTE_YEARS = 3
EVENT_TYPES = ["合同签订", "约定履行期届满", "违约", "催告", "对方承认债务", "付款", "协商"]
PARTIES = ["甲公司", "乙建设", "丙贸易", "丁科技", "戊物流", "己实业"]


def _fmt(d: date) -> str:
    return d.isoformat()


def gen_cases(seed: int = 20260913, n: int = 20) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for c in range(n):
        base = date(2026, 1, 1) + timedelta(days=rng.randint(0, 120))
        n_events = rng.randint(15, 40)
        contract = base - timedelta(days=rng.randint(400, 2000))
        events = [{"type": "合同签订", "date": _fmt(contract),
                   "party": rng.choice(PARTIES), "note": "主合同"}]
        for _ in range(n_events):
            etype = rng.choice(EVENT_TYPES[1:])
            d = contract + timedelta(days=rng.randint(30, 2200))
            ev = {"type": etype, "date": _fmt(d),
                  "party": rng.choice(PARTIES),
                  "amount": round(rng.uniform(1, 300) * 10000, 2)}
            events.append(ev)
        events.sort(key=lambda e: e["date"])
        # 口语化时间扰动（20% 事件改为相对描述，附解析锚点）
        for ev in events:
            if rng.random() < 0.2:
                d0 = date.fromisoformat(ev["date"])
                delta = (d0 - base).days
                if delta < -300:
                    ev["colloquial"] = "去年下半年"
                elif delta < 0:
                    ev["colloquial"] = f"{-delta // 30}个月前"
                else:
                    ev["colloquial"] = f"{delta // 30}个月后"
                ev["anchor"] = _fmt(base)
        # 请求权：时效判定 gold（按"约定履行期届满"起算 + 最近中断）
        claims = []
        due_events = [e for e in events if e["type"] == "约定履行期届满"] or \
                     [e for e in events if e["type"] == "违约"]
        for k, due in enumerate(due_events[:3]):
            due_d = date.fromisoformat(due["date"])
            # 中断事件：届满后的催告/承认
            interrupts = [date.fromisoformat(e["date"]) for e in events
                          if e["type"] in ("催告", "对方承认债务")
                          and due_d < date.fromisoformat(e["date"]) <= base]
            start = max(interrupts) if interrupts else due_d
            expiry = start + timedelta(days=int(STATUTE_YEARS * 365.25))
            if expiry <= base:
                status = "已过时效"
            elif expiry <= base + timedelta(days=180):
                status = "临近时效"
            else:
                status = "时效内"
            claims.append({"claim_id": f"C{c:02d}-{k}", "due": _fmt(due_d),
                           "interrupts": [_fmt(x) for x in interrupts],
                           "expiry": _fmt(expiry), "status": status})
        cases.append({"case_id": f"CASE{c:02d}", "as_of": _fmt(base),
                      "events": events, "claims": claims,
                      "parties": sorted({e["party"] for e in events})})
    return cases


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    cases = gen_cases()
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    n_claims = sum(len(c["claims"]) for c in cases)
    print(f"生成 {len(cases)} 个案件 / {sum(len(c['events']) for c in cases)} 条事件 / "
          f"{n_claims} 项请求权时效判定 -> {out/'cases.json'}")


if __name__ == "__main__":
    main()
