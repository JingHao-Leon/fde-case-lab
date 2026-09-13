"""确定性校验规则测试：S（报关单结构）/ P（出货单结构）/ A（两单对齐）。"""
import json
from pathlib import Path

import pytest
from engine.checks import audit, company_similar, similiarity

SAMPLES = Path(__file__).parent.parent / "samples"


def load(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def good_pair() -> tuple[dict, dict]:
    return load("packing_good.json"), load("declaration_good.json")


def rules(result) -> list[str]:
    return [f.rule for f in result.findings]


def by_rule(result, rule: str):
    return [f for f in result.findings if f.rule == rule]


# ---------------------------------------------------------------- 整体

class TestGoodPair:
    def test_clean(self, good_pair):
        p, d = good_pair
        r = audit(p, d)
        assert not r.errors
        # 只允许跨语言 info 提示
        assert all(f.severity == "info" for f in r.findings)

    def test_verdict_pass(self, good_pair):
        p, d = good_pair
        assert not audit(p, d).errors


# ---------------------------------------------------------------- S：报关单结构

class TestStructure:
    def test_s1_missing_required(self, good_pair):
        _, d = good_pair
        del d["transport_mode"]
        del d["gross_weight_kg"]
        del d["items"][0]["hs_code"]
        r = audit({}, d)
        s1 = by_rule(r, "S1")
        fields = " ".join(f.field for f in s1)
        assert "transport_mode" in fields and "gross_weight_kg" in fields
        assert "hs_code" in fields
        assert any(f.severity == "error" for f in s1)

    def test_s2_bad_hs_format(self, good_pair):
        _, d = good_pair
        d["items"][0]["hs_code"] = "85395"          # 位数不足
        d["items"][1]["hs_code"] = "94054O10O0"     # 含字母
        r = audit({}, d)
        assert len(by_rule(r, "S2")) == 2

    def test_s4_departure_before_declaration(self, good_pair):
        _, d = good_pair
        d["departure_date"], d["declaration_date"] = d["declaration_date"], d["departure_date"]
        r = audit({}, d)
        assert by_rule(r, "S4") and by_rule(r, "S4")[0].severity == "warning"

    def test_s6_net_heavier_than_gross(self, good_pair):
        _, d = good_pair
        d["net_weight_kg"] = 2000.0
        r = audit({}, d)
        f = by_rule(r, "S6")[0]
        assert f.severity == "error"

    def test_s7_item_numbers_gap(self, good_pair):
        _, d = good_pair
        d["items"][1]["no"] = 5
        r = audit({}, d)
        assert by_rule(r, "S7")

    def test_s8_price_qty_amount_mismatch(self, good_pair):
        _, d = good_pair
        d["items"][0]["unit_price"] = 0.4           # 0.4*30000=12000 ≠ 10500
        r = audit({}, d)
        f = by_rule(r, "S8")[0]
        assert f.severity == "error" and f.item == 1

    def test_s8_within_tolerance_ok(self, good_pair):
        """单价四舍五入到 4 位导致 <0.5% 误差，不应报错。"""
        _, d = good_pair
        d["items"][0]["unit_price"] = 0.35          # 恰好一致
        r = audit({}, d)
        assert not by_rule(r, "S8")

    def test_s9_totals_mismatch(self, good_pair):
        _, d = good_pair
        d["totals"]["total_amount"] = 22222.0
        r = audit({}, d)
        assert by_rule(r, "S9")[0].severity == "error"

    def test_s5_bad_currency(self, good_pair):
        _, d = good_pair
        d["items"][0]["currency"] = "USDD"
        r = audit({}, d)
        assert by_rule(r, "S5")[0].severity == "error"


# ---------------------------------------------------------------- P：出货单结构

class TestPacking:
    def test_p2_line_arithmetic(self, good_pair):
        p, _ = good_pair
        p["lines"][0]["unit_price"] = 0.5
        r = audit(p, {})
        assert by_rule(r, "P2")[0].severity == "error"

    def test_p3_totals_mismatch(self, good_pair):
        p, _ = good_pair
        p["totals"]["total_amount"] = 9999.0
        r = audit(p, {})
        assert by_rule(r, "P3")

    def test_p4_net_over_gross(self, good_pair):
        p, _ = good_pair
        p["totals"]["net_weight_kg"] = 1800.0
        r = audit(p, {})
        assert by_rule(r, "P4")[0].severity == "error"


# ---------------------------------------------------------------- A：对齐

class TestAlignment:
    def test_a1_gross_weight(self, good_pair):
        p, d = good_pair
        d["gross_weight_kg"] = 1500.0               # 出货单 1740
        r = audit(p, d)
        f = by_rule(r, "A1")[0]
        assert f.severity == "error" and f.left_value == 1740.0 and f.right_value == 1500.0

    def test_a2_net_weight_ok_within_tolerance(self, good_pair):
        p, d = good_pair
        d["net_weight_kg"] = 1545.0                 # 差 5kg，>0.5kg 但 <0.5%？1540*0.5%=7.7 → 容差内
        r = audit(p, d)
        assert not by_rule(r, "A2")

    def test_a3_packages(self, good_pair):
        p, d = good_pair
        d["package_count"] = 90
        r = audit(p, d)
        assert by_rule(r, "A3")[0].severity == "error"

    def test_a4_amount(self, good_pair):
        p, d = good_pair
        d["items"][0]["amount"] = 10000.0           # 总价差 500（同步改合计，避开 S9 路径）
        d["totals"]["total_amount"] = 19600.0
        r = audit(p, d)
        f = by_rule(r, "A4")[0]
        assert f.severity == "error"

    def test_a4_cif_diff_is_info(self, good_pair):
        p, d = good_pair
        d["incoterm"] = "CIF"
        d["items"][0]["amount"] = 10800.0           # +300 运费口径
        d["totals"]["total_amount"] = 20400.0
        r = audit(p, d)
        f = by_rule(r, "A4")[-1]
        assert f.severity in ("warning", "info")
        assert any(f.rule == "A4" and f.severity == "info" for f in r.findings)

    def test_a5_qty_mismatch(self, good_pair):
        p, d = good_pair
        d["items"][1]["qty"] = 7600
        r = audit(p, d)
        fs = by_rule(r, "A5")
        assert any(f.severity == "error" and f.item == 2 for f in fs)

    def test_a5_unit_not_convertible(self, good_pair):
        p, d = good_pair
        d["items"][0]["unit"] = "千克"               # PCS vs 千克
        r = audit(p, d)
        fs = [f for f in by_rule(r, "A5") if f.field.endswith("unit")]
        assert fs and fs[0].severity == "warning"

    def test_a6_hs_prefix(self, good_pair):
        p, d = good_pair
        d["items"][0]["hs_code"] = "8539400000"     # 前 6 位 853950→853940
        r = audit(p, d)
        f = by_rule(r, "A6")[0]
        assert f.severity == "error"

    def test_a7_cross_language_is_info(self, good_pair):
        """中英双语公司名：无法自动比对 → info 而非 warning。"""
        p, d = good_pair
        r = audit(p, d)
        fs = by_rule(r, "A7")
        assert fs and all(f.severity == "info" for f in fs)

    def test_a7_same_language_mismatch_is_warning(self, good_pair):
        p, d = good_pair
        p["consignee"] = "XYZ Handel AG"
        r = audit(p, d)
        fs = [f for f in by_rule(r, "A7") if f.field == "overseas_consignee.name"]
        assert fs and fs[0].severity == "warning"

    def test_a7_same_company_suffix_ignored(self):
        assert company_similar("Ningbo Chenxi Import & Export Co., Ltd.",
                               "NINGBO CHENXI IMPORT & EXPORT CO.,LTD") >= 0.6

    def test_a8_port(self, good_pair):
        p, d = good_pair
        d["port_of_discharge"] = "Rotterdam"
        r = audit(p, d)
        assert by_rule(r, "A8")

    def test_a10_contract(self, good_pair):
        p, d = good_pair
        p["contract_no"] = "HT-2026-099"
        r = audit(p, d)
        assert by_rule(r, "A10")[0].severity == "warning"

    def test_unmatched_line_warns(self, good_pair):
        p, d = good_pair
        p["lines"].append({"name": "LED 射灯", "name_en": "LED Spotlight", "qty": 100,
                           "unit": "PCS", "amount": 200.0})
        r = audit(p, d)
        assert any("未能" in f.message and f.rule == "A5" for f in r.findings)


# ---------------------------------------------------------------- 相似度工具

class TestSimilarity:
    def test_identical(self):
        assert similiarity("LED灯泡", "LED 灯泡") == 1.0

    def test_company_suffix(self):
        assert company_similar("ABC Trading GmbH", "ABC Trading GmbH ") > 0.9

    def test_unrelated(self):
        assert similiarity("LED灯泡", "吸顶灯") < 0.4
