#!/usr/bin/env python3
"""端到端冒烟测试：好坏样例审查结论 + 解析器 + bench 捕获矩阵。

完整规则级测试见 tests/（41 用例）。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from engine.checks import audit
from engine.excel_packing import parse as parse_excel

SAMPLES = HERE / "samples"


def load(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def test_good_pair_has_no_error_or_warning():
    r = audit(load("packing_good.json"), load("declaration_good.json"))
    assert not r.errors
    assert not r.warnings
    assert all(f.severity == "info" for f in r.findings)


def test_bad_pair_catches_injected_errors():
    r = audit(load("packing_bad.json"), load("declaration_bad.json"))
    rules = {f.rule for f in r.findings if f.severity == "error"}
    assert {"A1", "A5", "A6", "S5", "S8"} <= rules


def test_excel_parser_extracts_lines_and_totals():
    raw = parse_excel(SAMPLES / "packing_list_sample.xlsx")
    h = raw["hints"]
    assert len(h["lines"]) == 2
    assert h["lines"][0]["amount"] == 10500.0
    assert h["totals"]["total_amount"] == 20100.0
    assert h["totals"]["gross_weight_kg"] == 1740.0


def test_excel_parser_top_fields():
    h = parse_excel(SAMPLES / "packing_list_sample.xlsx")["hints"]
    assert h["invoice_no"] == "CX-2026-088"
    assert h["consignee"] == "ABC Trading GmbH"
