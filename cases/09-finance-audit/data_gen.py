"""NO.9 央国企财务报销：生成报销单与审批/发票数据（植入合规问题）。

场景来自《Datawhale FDE 案例 100》NO.9：央企科研机构财务流程——判断费用性质/
科目、关联出差申请与审批、再手工录入集团系统，全流程半个月到一个月；AI+RPA
后 1~2 天，落地 10 个 AI 场景。

数据模型（2,000 张报销单）：
- 字段：发票类型（差旅/住宿/交通/招待/办公）、金额、员工部门、项目、
  有无出差申请、有无事前审批、发票号、日期；
- 植入问题：重复报销（同发票号二次提交）、住宿超标准（按城市档位）、
  缺事前审批的招待费、科目错配 gold（业务事实给出正确科目）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

INVOICE_TYPES = ["交通", "住宿", "餐饮招待", "办公用品", "培训"]
CITY_TIER = {"一线": 600, "二线": 450, "三线": 350}
PROJECTS = ["预研项目", "型号任务", "基础研究", " platform"[:0] or "平台建设"]


def _subject(t: dict) -> str:
    """业务事实：正确的会计科目（gold）。"""
    if t["inv_type"] == "交通" and t["has_travel_req"]:
        return "差旅费-市内交通"
    if t["inv_type"] == "住宿" and t["has_travel_req"]:
        return "差旅费-住宿"
    if t["inv_type"] == "餐饮招待":
        return "业务招待费"
    if t["inv_type"] == "培训":
        return "职工教育经费"
    if t["has_travel_req"]:
        return "差旅费-其他"
    return "办公费"


def gen_bills(seed: int = 20260913, n: int = 2000) -> list[dict]:
    rng = random.Random(seed)
    bills = []
    used_invoice_ids = {}
    for i in range(n):
        inv_type = rng.choices(INVOICE_TYPES, weights=[3, 3, 2, 3, 1])[0]
        tier = rng.choice(list(CITY_TIER))
        has_travel = inv_type in ("交通", "住宿") and rng.random() < 0.8
        b = {
            "id": f"BX{i:05d}",
            "inv_type": inv_type,
            "invoice_no": f"INV{rng.randint(10**9, 10**10 - 1)}",
            "dept": rng.choice(["研发一部", "研发二部", "总体部", "工艺部"]),
            "project": rng.choice(PROJECTS),
            "has_travel_req": has_travel,
            "has_approval": rng.random() < 0.93,
            "city_tier": tier,
            "amount": round(rng.uniform(60, 5000), 2),
        }
        if inv_type == "住宿":
            b["nights"] = rng.randint(1, 5)
            b["hotel_daily"] = round(b["amount"] / b["nights"], 2)
        b["subject_gold"] = _subject(b)
        # 植入问题
        r = rng.random()
        if r < 0.03 and inv_type == "餐饮招待":
            b["has_approval"] = False
            b["issue"] = "招待费缺事前审批"
        elif r < 0.05 and inv_type == "住宿":
            b["hotel_daily"] = round(CITY_TIER[tier] * rng.uniform(1.3, 2.0), 2)
            b["issue"] = "住宿超标准"
        else:
            b["issue"] = None
        if b["invoice_no"] in used_invoice_ids and rng.random() < 0.8:
            b["issue"] = "重复报销"
        used_invoice_ids[b["invoice_no"]] = b["id"]
        # 显式种入重复报销：约 1.5% 的单复用"他人"的历史发票号
        # （跳过已标记问题的单，避免覆盖标签造成假重复）
        if rng.random() < 0.015 and not b["issue"]:
            others = [no for no in used_invoice_ids if no != b["invoice_no"]]
            if others:
                prev_no = rng.choice(others)
                used_invoice_ids.pop(b["invoice_no"], None)  # 释放被替换的旧号
                b["invoice_no"] = prev_no
                b["issue"] = "重复报销"
        bills.append(b)
    return bills


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    bills = gen_bills()
    (out / "bills.json").write_text(json.dumps(bills, ensure_ascii=False), encoding="utf-8")
    n_issue = sum(1 for b in bills if b["issue"])
    print(f"生成 {len(bills)} 张报销单（问题单 {n_issue} 张）-> {out/'bills.json'}")


if __name__ == "__main__":
    main()
