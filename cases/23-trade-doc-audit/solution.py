#!/usr/bin/env python3
"""外贸出货单 ↔ 海关申报单审查求解器（门面模块）。

真正的实现位于 engine/ 包：
- engine.excel_packing / engine.pdf_text : 原始单据解析（确定性）
- engine.schema                          : 两份单据的标准 JSON Schema
- engine.checks                          : 23 条确定性审查规则（S/P/A）
- engine.report                          : Markdown 审查报告
- engine.audit_cli                       : parse / audit / schema 命令行

本文件按本仓库案例规范暴露统一入口。
"""
from pathlib import Path

from engine.checks import audit as run_audit
from engine.checks import match_lines
from engine.excel_packing import parse as parse_excel
from engine.pdf_text import parse as parse_pdf
from engine.report import build_report

__all__ = [
    "RULE_COUNT",
    "audit_documents",
    "build_report",
    "match_lines",
    "parse_excel",
    "parse_pdf",
    "run_audit",
]

RULE_COUNT = 23  # S1-S9 + P1-P4 + A1-A10

CASE_DIR = Path(__file__).parent


def audit_documents(packing: dict, declaration: dict):
    """审查两份标准 JSON，返回 (AuditResult, markdown_report)。"""
    result = run_audit(packing, declaration)
    report = build_report(
        packing, declaration, result,
        packing_file=packing.get("source_file", ""),
        declaration_file=declaration.get("source_file", ""),
    )
    return result, report
