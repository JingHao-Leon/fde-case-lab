#!/usr/bin/env python3
"""外贸单据审查 CLI —— 供 pi agent（skill: trade-doc-audit）与人工调用。

用法：
  # 1) 解析原始单据（Excel/PDF），产出“原文网格 + 归一化提示”，供 LLM 按 schema 抽取
  python audit_cli.py parse 样例出货单.xlsx -o work/packing_raw.json
  python audit_cli.py parse 报关单.pdf   -o work/declaration_raw.json

  # 2) 抽取完成后做确定性审查（结构 + 算术 + 两单对齐）
  python audit_cli.py audit work/packing.json work/declaration.json \
      -o work/findings.json --report work/report.md

  # 3) 查看标准 schema（LLM 抽取目标）
  python audit_cli.py schema packing
  python audit_cli.py schema declaration

退出码：audit 存在 error 时为 1，否则 0。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows GBK 环境兜底
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .checks import audit
from .excel_packing import parse as parse_excel
from .pdf_text import parse as parse_pdf
from .report import build_report
from .schema import SCHEMAS

PDF_TEXTUAL_HINTS = (".pdf",)


def _read_json(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"输入 JSON 顶层必须是对象：{path}")
    return data


def _dump(data: dict | list, out: str | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {out}")
    else:
        print(text)


def cmd_parse(args: argparse.Namespace) -> int:
    src = Path(args.file)
    if not src.exists():
        raise SystemExit(f"文件不存在：{src}")
    suffix = src.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        result = parse_excel(src)
    elif suffix == ".csv":
        text = src.read_text(encoding="utf-8", errors="replace")
        lines = [ln.split(",") for ln in text.splitlines()]
        result = {
            "source_file": src.name, "kind": "unknown_csv",
            "grid": [" | ".join(row) for row in lines], "hints": {}, "notes": [],
        }
    elif suffix in PDF_TEXTUAL_HINTS:
        result = parse_pdf(src)
        result["notes"].append("parse 只提供文本与表格原文；请按 declaration/packing schema 由模型抽取字段。")
    elif suffix in (".txt", ".md", ".json"):
        text = src.read_text(encoding="utf-8", errors="replace")
        result = {"source_file": src.name, "kind": "text", "pages_text": text.splitlines(), "tables": [], "notes": []}
    else:
        raise SystemExit(f"不支持的文件类型 {suffix}；扫描件请走图片视觉识别路径（agent 直接读图抽取）。")

    _dump(result, args.out)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    packing = _read_json(args.packing)
    declaration = _read_json(args.declaration)
    for name, doc, kind in (("出货单", packing, "packing_list"), ("报关单", declaration, "export_declaration")):
        if doc.get("doc_type") != kind:
            print(f"警告：{name} 的 doc_type={doc.get('doc_type')!r}，期望 {kind!r}", file=sys.stderr)

    result = audit(packing, declaration)
    findings = [f.to_dict() for f in result.findings]
    summary = {
        "verdict": "fail" if result.errors else ("warn" if result.warnings else "pass"),
        "counts": {"error": len(result.errors), "warning": len(result.warnings),
                   "info": len(findings) - len(result.errors) - len(result.warnings)},
        "findings": findings,
    }
    _dump(summary, args.out)

    report = build_report(
        packing, declaration, result,
        packing_file=packing.get("source_file", ""), declaration_file=declaration.get("source_file", ""),
    )
    report_path = args.report or (Path(args.out).with_suffix(".md") if args.out else None)
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(report + "\n", encoding="utf-8")
        print(f"报告已写入 {report_path}")
    else:
        print("\n" + report)

    n_err = len(result.errors)
    print(f"审查完成：error={len(result.errors)} warning={len(result.warnings)} "
          f"info={len(findings) - len(result.errors) - len(result.warnings)}")
    return 1 if n_err else 0


def cmd_schema(args: argparse.Namespace) -> int:
    print(json.dumps(SCHEMAS[args.kind], ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="外贸出货单 ↔ 海关申报单 审查引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("parse", help="解析原始单据（Excel/PDF/CSV/文本）")
    p1.add_argument("file")
    p1.add_argument("-o", "--out", help="输出 JSON 路径（缺省打印到 stdout）")
    p1.set_defaults(func=cmd_parse)

    p2 = sub.add_parser("audit", help="对两份标准 JSON 做确定性审查")
    p2.add_argument("packing", help="出货单标准 JSON")
    p2.add_argument("declaration", help="报关单标准 JSON")
    p2.add_argument("-o", "--out", help="findings JSON 输出路径")
    p2.add_argument("--report", help="Markdown 报告输出路径（缺省与 -o 同名 .md）")
    p2.set_defaults(func=cmd_audit)

    p3 = sub.add_parser("schema", help="打印标准 schema")
    p3.add_argument("kind", choices=["packing", "declaration"])
    p3.set_defaults(func=cmd_schema)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
