"""审查报告生成：findings → 飞书/Markdown 友好的审查报告。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .checks import AuditResult

SEVERITY_BADGE = {"error": "🔴", "warning": "🟡", "info": "🔵"}
RULE_LABEL = {
    "S1": "结构·必填", "S2": "结构·HS编码", "S3": "结构·数量金额", "S4": "结构·日期",
    "S5": "结构·币制", "S6": "结构·毛净重", "S7": "结构·项号", "S8": "算术·单价×数量",
    "S9": "算术·表体合计",
    "P1": "出货单·必填", "P2": "出货单·行算术", "P3": "出货单·合计", "P4": "出货单·毛净重",
    "A1": "对齐·总毛重", "A2": "对齐·总净重", "A3": "对齐·总件数", "A4": "对齐·总金额",
    "A5": "对齐·行数量", "A6": "对齐·HS编码", "A7": "对齐·收发货人", "A8": "对齐·目的港",
    "A9": "对齐·行数", "A10": "对齐·合同号",
}


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def build_report(packing: dict[str, Any], declaration: dict[str, Any], result: AuditResult,
                 packing_file: str = "", declaration_file: str = "") -> str:
    n_err, n_warn = len(result.errors), len(result.warnings)
    n_info = len(result.findings) - n_err - n_warn
    if n_err:
        verdict = "❌ 不通过"
    elif n_warn:
        verdict = "⚠️ 有条件通过"
    else:
        verdict = "✅ 通过"

    out: list[str] = []
    out.append("# 外贸单据审查报告")
    out.append("")
    out.append(f"- **结论：{verdict}**（🔴 错误 {n_err} · 🟡 预警 {n_warn} · 🔵 提示 {n_info}）")
    out.append(f"- 审查时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}")
    if packing_file:
        out.append(f"- 出货单：`{packing_file}`")
    if declaration_file:
        out.append(f"- 报关单：`{declaration_file}`")
    out.append("")

    # 关键值对照
    pt = packing.get("totals") or {}
    dc = declaration.get("domestic_consignor") or {}
    oc = declaration.get("overseas_consignee") or {}
    d_total = (declaration.get("totals") or {}).get("total_amount")
    if d_total is None and declaration.get("items"):
        from .schema import as_float
        d_total = sum(as_float(it.get("amount")) or 0.0 for it in declaration["items"])
    out.append("## 关键值对照")
    out.append("")
    out.append("| 项目 | 出货单 | 报关单 |")
    out.append("|---|---|---|")
    out.append(f"| 发货人/境内发货人 | {_fmt(packing.get('shipper'))} | {_fmt(dc.get('name'))} |")
    out.append(f"| 收货人/境外收货人 | {_fmt(packing.get('consignee'))} | {_fmt(oc.get('name'))} |")
    out.append(f"| 总件数 | {_fmt(pt.get('packages'))} | {_fmt(declaration.get('package_count'))} |")
    out.append(f"| 总毛重(kg) | {_fmt(pt.get('gross_weight_kg'))} | {_fmt(declaration.get('gross_weight_kg'))} |")
    out.append(f"| 总净重(kg) | {_fmt(pt.get('net_weight_kg'))} | {_fmt(declaration.get('net_weight_kg'))} |")
    out.append(f"| 总金额 | {_fmt(pt.get('total_amount'))} {pt.get('currency') or ''} | {_fmt(d_total)} |")
    out.append(f"| 明细行数 | {len(packing.get('lines') or [])} | {len(declaration.get('items') or [])} |")
    out.append("")

    for sev, title in [("error", "错误（必须整改）"), ("warning", "预警（建议核实）"), ("info", "提示（供参考）")]:
        rows = [f for f in result.findings if f.severity == sev]
        if not rows:
            continue
        out.append(f"## {SEVERITY_BADGE[sev]} {title}")
        out.append("")
        out.append("| 规则 | 类别 | 位置 | 说明 | 出货单值 | 报关单值 |")
        out.append("|---|---|---|---|---|---|")
        for f in rows:
            loc = f"第{f.item}项" if f.item else "—"
            out.append(f"| {f.rule} | {RULE_LABEL.get(f.rule, '')} | {loc} | {f.message} | {_fmt(f.left_value)} | {_fmt(f.right_value)} |")
        out.append("")

    if not result.errors and not result.warnings and not result.findings:
        out.append("## ✅ 未发现任何问题")
        out.append("")
        out.append("两单结构与数值全部一致。")
        out.append("")
    out.append("---")
    out.append("*本报告由确定性规则引擎生成（结构/算术/对齐 23 条规则）；品名等语义匹配结果请结合业务确认。*")
    return "\n".join(out)
