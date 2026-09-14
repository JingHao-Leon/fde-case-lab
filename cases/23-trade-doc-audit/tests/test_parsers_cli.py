"""解析器与 CLI 端到端测试（进程内调用 audit_cli.main，等价于命令行退出码）。"""
import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "samples"
sys.path.insert(0, str(ROOT))

from engine import audit_cli
from engine.excel_packing import parse as parse_excel

try:
    import pdfplumber as _pdfplumber
    from engine.pdf_text import parse as parse_pdf
except ImportError:  # CI 最小依赖环境无 pdfplumber 时跳过 PDF 相关用例
    _pdfplumber = None


def run_cli(*args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = audit_cli.main(list(args))
    return code, buf.getvalue()


class TestExcelParsing:
    def test_lines(self):
        raw = parse_excel(SAMPLES / "packing_list_sample.xlsx")
        lines = raw["hints"]["lines"]
        assert len(lines) == 2
        assert lines[0]["qty"] == 30000.0
        assert lines[0]["unit_price"] == 0.35
        assert lines[0]["amount"] == 10500.0
        assert lines[0]["gross_weight_kg"] == 1020.0
        assert lines[1]["cartons"] == 40.0

    def test_totals_by_column(self):
        raw = parse_excel(SAMPLES / "packing_list_sample.xlsx")
        t = raw["hints"]["totals"]
        assert t["total_amount"] == 20100.0
        assert t["net_weight_kg"] == 1540.0
        assert t["gross_weight_kg"] == 1740.0
        assert t["packages"] == 91.0

    def test_top_fields(self):
        raw = parse_excel(SAMPLES / "packing_list_sample.xlsx")
        h = raw["hints"]
        assert h["invoice_no"] == "CX-2026-088"
        assert h["contract_no"] == "HT-2026-031"
        assert h["incoterm"] == "FOB NINGBO"
        assert "晨曦" in h["shipper"]
        assert h["consignee"] == "ABC Trading GmbH"
        assert h["port_of_loading"] == "NINGBO"
        assert h["port_of_discharge"] == "HAMBURG"

    def test_grid_exposed_for_llm(self):
        raw = parse_excel(SAMPLES / "packing_list_sample.xlsx")
        assert any("DESCRIPTION" in ln for ln in raw["grid"])


class TestPdfParsing:
    def test_text_extracted(self):
        if _pdfplumber is None:
            pytest.skip("pdfplumber 未安装（CI 最小依赖环境）")
        raw = parse_pdf(SAMPLES / "packing_list_sample.pdf")
        text = "\n".join(raw["pages_text"])
        assert "PACKING LIST" in text
        assert "CX-2026-088" in text
        assert raw["notes"] == []


class TestCli:
    def test_audit_good_passes(self, tmp_path):
        out, report = tmp_path / "f.json", tmp_path / "r.md"
        code, _ = run_cli("audit", str(SAMPLES / "packing_good.json"),
                          str(SAMPLES / "declaration_good.json"),
                          "-o", str(out), "--report", str(report))
        assert code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["verdict"] == "pass"            # 跨语言项已降级为 info
        assert data["counts"]["error"] == 0
        assert data["counts"]["info"] == 2
        assert "关键值对照" in report.read_text(encoding="utf-8")

    def test_audit_bad_fails_with_errors(self, tmp_path):
        out, report = tmp_path / "f.json", tmp_path / "r.md"
        code, _ = run_cli("audit", str(SAMPLES / "packing_bad.json"),
                          str(SAMPLES / "declaration_bad.json"),
                          "-o", str(out), "--report", str(report))
        assert code == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["verdict"] == "fail"
        assert data["counts"]["error"] >= 4
        rules = {f["rule"] for f in data["findings"]}
        assert {"A1", "A5", "A6", "S8", "S5"} <= rules
        report_text = report.read_text(encoding="utf-8")
        assert "❌ 不通过" in report_text
        assert "关键值对照" in report_text

    def test_parse_excel(self, tmp_path):
        out = tmp_path / "raw.json"
        code, _ = run_cli("parse", str(SAMPLES / "packing_list_sample.xlsx"), "-o", str(out))
        assert code == 0
        raw = json.loads(out.read_text(encoding="utf-8"))
        assert raw["kind"] == "packing"
        assert len(raw["hints"]["lines"]) == 2

    def test_parse_pdf(self, tmp_path):
        if _pdfplumber is None:
            pytest.skip("pdfplumber 未安装（CI 最小依赖环境）")
        out = tmp_path / "raw.json"
        code, _ = run_cli("parse", str(SAMPLES / "packing_list_sample.pdf"), "-o", str(out))
        assert code == 0
        raw = json.loads(out.read_text(encoding="utf-8"))
        assert "PACKING LIST" in "\n".join(raw["pages_text"])

    def test_schema_command(self):
        for kind in ("packing", "declaration"):
            code, stdout = run_cli("schema", kind)
            assert code == 0
            schema = json.loads(stdout)
            assert schema["required"]
