#!/usr/bin/env python3
"""生成测试样例：出货单 Excel、英文文本型 PDF（装箱单）、标准抽取 JSON。

运行：python samples/make_samples.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from openpyxl import Workbook


def make_packing_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Packing List"
    rows = [
        ["Ningbo Chenxi Lighting Import & Export Co., Ltd.", "", "", "", "", "", "", "", "", ""],
        ["No.88 Qianshan Road, Yinzhou District, Ningbo, China", "", "", "", "", "", "", "", "", ""],
        [],
        ["INVOICE NO.: CX-2026-088", "", "DATE: 2026-08-20", "", "", "", "", "", "", ""],
        ["CONTRACT NO.: HT-2026-031", "", "INCOTERM: FOB NINGBO", "", "", "", "", "", "", ""],
        ["SHIPPER: 宁波晨曦照明进出口有限公司", "", "", "", "", "", "", "", "", ""],
        ["CONSIGNEE: ABC Trading GmbH", "", "", "", "", "", "", "", "", ""],
        ["PORT OF LOADING: NINGBO", "", "PORT OF DISCHARGE: HAMBURG", "", "", "", "", "", "", ""],
        [],
        ["NO.", "DESCRIPTION", "MODEL", "QTY", "UNIT", "UNIT PRICE (USD)", "AMOUNT (USD)", "NW (KGS)", "GW (KGS)", "CTNS"],
        [1, "LED 灯泡 LED Bulb", "E27-5W", 30000, "PCS", 0.35, 10500.0, 900.0, 1020.0, 51],
        [2, "LED 吸顶灯 LED Ceiling Light", "CL-18W", 8000, "PCS", 1.20, 9600.0, 640.0, 720.0, 40],
        [],
        ["TOTAL:", "", "", 38000, "", "", 20100.0, 1540.0, 1740.0, 91],
    ]
    for row in rows:
        ws.append(row)
    wb.save(path)


MINIMAL_PDF = """%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length 620 >>
stream
BT /F1 12 Tf 40 750 Td (PACKING LIST / COMMERCIAL INVOICE) Tj 0 -20 Td
(Invoice No.: CX-2026-088    Date: 2026-08-20) Tj 0 -18 Td
(Shipper: Ningbo Chenxi Lighting Import & Export Co., Ltd.) Tj 0 -18 Td
(Consignee: ABC Trading GmbH) Tj 0 -18 Td
(Port of Loading: NINGBO    Port of Discharge: HAMBURG) Tj 0 -18 Td
(Incoterm: FOB NINGBO    Currency: USD) Tj 0 -18 Td
(1. LED Bulb E27-5W  30000 PCS x 0.35 = 10500.00 USD  NW 900.0 KGS GW 1020.0 KGS 51 CTNS) Tj 0 -16 Td
(2. LED Ceiling Light CL-18W  8000 PCS x 1.20 = 9600.00 USD  NW 640.0 KGS GW 720.0 KGS 40 CTNS) Tj 0 -16 Td
(TOTAL: 38000 PCS  20100.00 USD  NW 1540.0 KGS  GW 1740.0 KGS  91 CTNS) Tj ET
endstream
endobj
trailer << /Root 1 0 R >>
%%EOF
"""


def main() -> None:
    make_packing_xlsx(HERE / "packing_list_sample.xlsx")
    (HERE / "packing_list_sample.pdf").write_text(MINIMAL_PDF, encoding="latin-1")

    good_lines = [
        {"no": 1, "name": "LED 灯泡", "name_en": "LED Bulb", "hs_code": "85395000", "model": "E27-5W",
         "qty": 30000, "unit": "PCS", "unit_price": 0.35, "amount": 10500.0,
         "net_weight_kg": 900.0, "gross_weight_kg": 1020.0, "cartons": 51},
        {"no": 2, "name": "LED 吸顶灯", "name_en": "LED Ceiling Light", "hs_code": "94054010", "model": "CL-18W",
         "qty": 8000, "unit": "PCS", "unit_price": 1.20, "amount": 9600.0,
         "net_weight_kg": 640.0, "gross_weight_kg": 720.0, "cartons": 40},
    ]
    packing_good = {
        "doc_type": "packing_list", "source_file": "packing_list_sample.xlsx",
        "shipper": "Ningbo Chenxi Lighting Import & Export Co., Ltd.",
        "consignee": "ABC Trading GmbH",
        "invoice_no": "CX-2026-088", "contract_no": "HT-2026-031", "date": "2026-08-20",
        "incoterm": "FOB NINGBO", "port_of_loading": "NINGBO", "port_of_discharge": "HAMBURG",
        "lines": good_lines,
        "totals": {"packages": 91, "package_unit": "CTNS", "net_weight_kg": 1540.0,
                   "gross_weight_kg": 1740.0, "total_amount": 20100.0, "currency": "USD"},
    }
    declaration_good = {
        "doc_type": "export_declaration", "source_file": "declaration_sample.pdf",
        "pre_entry_no": "2026082200001234", "customs_no": "311120260000123456",
        "domestic_consignor": {"name": "宁波晨曦照明进出口有限公司", "customs_code": "3302967890",
                               "uscc": "91330200MA2ABCD123"},
        "overseas_consignee": {"name": "ABC Trading GmbH"},
        "transport_mode": "江海运输", "vessel": "CMA CGM LYRA / 088W",
        "supervision_mode": "一般贸易", "levy_type": "一般征税",
        "trade_country": "德国", "port_of_loading": "宁波港", "port_of_discharge": "德国汉堡",
        "incoterm": "FOB", "contract_no": "HT-2026-031",
        "declaration_date": "2026-08-22", "departure_date": "2026-08-25",
        "package_count": 91, "package_type": "纸箱",
        "gross_weight_kg": 1740.0, "net_weight_kg": 1540.0,
        "items": [
            {"no": 1, "hs_code": "8539500000", "name": "LED灯泡", "spec": "E27 5W 3000K",
             "qty": 30000, "unit": "个", "country_of_origin": "中国", "destination_country": "德国",
             "unit_price": 0.35, "amount": 10500.0, "currency": "USD"},
            {"no": 2, "hs_code": "9405401000", "name": "LED吸顶灯", "spec": "18W 圆形",
             "qty": 8000, "unit": "个", "country_of_origin": "中国", "destination_country": "德国",
             "unit_price": 1.2, "amount": 9600.0, "currency": "USD"},
        ],
        "totals": {"total_amount": 20100.0, "currency": "USD"},
    }

    # 坏样例：在 good 基础上注入典型错误
    declaration_bad = json.loads(json.dumps(declaration_good, ensure_ascii=False))
    declaration_bad["gross_weight_kg"] = 1620.0                      # A1 毛重不一致
    declaration_bad["items"][1]["qty"] = 7600                        # A5 数量不一致
    declaration_bad["items"][0]["hs_code"] = "8539400000"            # A6 HS 前 6 位不一致
    declaration_bad["items"][0]["unit_price"] = 0.40                 # S8 单价×数量≠总价
    declaration_bad["items"][1]["currency"] = "USDD"                 # S5 币制非法
    packing_bad = json.loads(json.dumps(packing_good, ensure_ascii=False))
    packing_bad["contract_no"] = "HT-2026-099"                       # A10 合同号不一致

    for name, data in [
        ("packing_good.json", packing_good), ("declaration_good.json", declaration_good),
        ("packing_bad.json", packing_bad), ("declaration_bad.json", declaration_bad),
    ]:
        (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("样例已生成：packing_list_sample.xlsx / packing_list_sample.pdf / *.json")


if __name__ == "__main__":
    main()
