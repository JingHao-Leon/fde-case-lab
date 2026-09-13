"""NO.9 财务报销审核求解器：科目映射 + 双角色交叉复核 + 风险队列。

对应 NO.9 的架构「业务信息获取 → AI 判断 → AI 监督 → 风险识别 → 执行」：

- SubjectMapper   科目映射规则引擎：发票类型 × 是否有出差申请 → 会计科目
                  （对应财务人员"判断费用性质"的隐性经验规则化）。
- DualReviewer    双角色交叉复核（对应"一个执行判断、一个监督、一个发现风险"）：
                  执行角色做合规检查（招待费审批 / 住宿标准 / 发票重复），
                  监督角色独立按规则集复核；两者一致且无风险 → **自动直通**；
                  任一发现问题 → 风险队列转人工。
- 发票重复检测：invoice_no 在历史台账中出现 → 重复报销（硬拦截）。

指标：科目映射准确率、自动直通率、风险检出率、误放率（有问题却直通，红线=0）。
"""
from __future__ import annotations

CITY_STD = {"一线": 600, "二线": 450, "三线": 350}  # 住宿标准 元/晚


class SubjectMapper:
    """科目映射规则：确定性、可解释（规则表外置，便于财务维护）。"""

    RULES = [
        (lambda b: b["inv_type"] == "交通" and b["has_travel_req"], "差旅费-市内交通"),
        (lambda b: b["inv_type"] == "住宿" and b["has_travel_req"], "差旅费-住宿"),
        (lambda b: b["inv_type"] == "餐饮招待", "业务招待费"),
        (lambda b: b["inv_type"] == "培训", "职工教育经费"),
        (lambda b: b["has_travel_req"], "差旅费-其他"),
    ]
    DEFAULT = "办公费"

    def map_subject(self, bill: dict) -> str:
        for cond, subject in self.RULES:
            if cond(bill):
                return subject
        return self.DEFAULT


class DualReviewer:
    def __init__(self, history_invoice_nos: set[str] | None = None):
        self.seen = set(history_invoice_nos or ())

    def _executor_view(self, bill: dict, subject: str) -> list[str]:
        issues = []
        if bill["inv_type"] == "餐饮招待" and not bill["has_approval"]:
            issues.append("招待费缺事前审批")
        if bill["inv_type"] == "住宿" and bill.get("hotel_daily"):
            std = CITY_STD.get(bill.get("city_tier"), 450)
            if bill["hotel_daily"] > std:
                issues.append(f"住宿超标准({bill['hotel_daily']}>{std}元/晚)")
        if bill["invoice_no"] in self.seen:
            issues.append("发票重复报销")
        return issues

    def _supervisor_view(self, bill: dict, subject: str) -> list[str]:
        # 监督角色独立复核：重复发票 + 科目与类型明显错配
        issues = []
        if bill["invoice_no"] in self.seen:
            issues.append("发票重复报销")
        if subject == "业务招待费" and bill["inv_type"] != "餐饮招待":
            issues.append("科目与发票类型错配")
        if subject.startswith("差旅费") and not bill["has_travel_req"] \
                and bill["inv_type"] != "餐饮招待":
            issues.append("无出差申请却记差旅费")
        return issues

    def review(self, bill: dict, history_mode: bool = False) -> dict:
        subject = SubjectMapper().map_subject(bill)
        exec_issues = self._executor_view(bill, subject)
        sup_issues = self._supervisor_view(bill, subject)
        all_issues = sorted(set(exec_issues) | set(sup_issues))
        if history_mode:
            self.seen.add(bill["invoice_no"])
        status = "auto_pass" if not all_issues else "risk_queue"
        return {"id": bill["id"], "subject": subject, "status": status,
                "issues": all_issues,
                "agreed": set(exec_issues) == set(sup_issues)}


def audit(bills: list[dict], history_nos: set[str] | None = None) -> dict:
    reviewer = DualReviewer(history_nos)
    total = auto = 0
    subject_ok = 0
    caught = missed = 0
    SubjectMapper()
    for b in bills:
        total += 1
        r = reviewer.review(b, history_mode=True)
        auto += r["status"] == "auto_pass"
        subject_ok += r["subject"] == b["subject_gold"]
        if b.get("issue"):
            caught += r["status"] == "risk_queue"
            missed += r["status"] == "auto_pass"
    n_issue = sum(1 for b in bills if b.get("issue"))
    return {
        "total": total,
        "auto_rate": auto / total,
        "subject_acc": subject_ok / total,
        "issue_caught": caught,
        "issue_total": n_issue,
        "recall": caught / max(1, n_issue),
        "missed": missed,
    }
