"""出货单（装箱单/发票）与出口报关单的标准中间格式定义。

agent（LLM）负责把原始单据内容抽取成这里的结构；之后的所有校验
（结构 / 算术 / 两单对齐）都在该结构上以确定性代码完成，不依赖 LLM。
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------- 出货单 schema

PACKING_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PackingListDoc 出货单/商业发票（含箱单要素）",
    "type": "object",
    "required": ["doc_type", "lines", "totals"],
    "properties": {
        "doc_type": {"const": "packing_list"},
        "source_file": {"type": "string", "description": "来源文件名"},
        "shipper": {"type": "string", "description": "发货人 / SHIPPER / SELLER（尽量保留原文）"},
        "consignee": {"type": "string", "description": "收货人 / CONSIGNEE / BUYER"},
        "invoice_no": {"type": "string"},
        "contract_no": {"type": ["string", "null"], "description": "合同号 / S/C NO. / PO NO."},
        "date": {"type": ["string", "null"], "description": "单据日期 YYYY-MM-DD"},
        "incoterm": {"type": ["string", "null"], "description": "贸易条款，如 FOB NINGBO / CIF HAMBURG"},
        "port_of_loading": {"type": ["string", "null"]},
        "port_of_discharge": {"type": ["string", "null"]},
        "lines": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "qty", "unit", "amount"],
                "properties": {
                    "no": {"type": ["integer", "null"]},
                    "name": {"type": "string", "description": "品名（有中文用中文，否则英文原文）"},
                    "name_en": {"type": ["string", "null"], "description": "英文品名（若与 name 不同）"},
                    "hs_code": {"type": ["string", "null"], "description": "如单据提供"},
                    "model": {"type": ["string", "null"], "description": "型号/规格"},
                    "qty": {"type": "number", "exclusiveMinimum": 0},
                    "unit": {"type": "string", "description": "PCS/SET/CTNS/KGS…原样保留"},
                    "unit_price": {"type": ["number", "null"]},
                    "amount": {"type": "number", "minimum": 0},
                    "cartons": {"type": ["number", "null"], "description": "该行箱数"},
                    "net_weight_kg": {"type": ["number", "null"]},
                    "gross_weight_kg": {"type": ["number", "null"]},
                },
            },
        },
        "totals": {
            "type": "object",
            "required": ["total_amount"],
            "properties": {
                "packages": {"type": ["number", "null"], "description": "总件数（箱数）"},
                "package_unit": {"type": ["string", "null"], "description": "CTNS/PLTS…"},
                "net_weight_kg": {"type": ["number", "null"]},
                "gross_weight_kg": {"type": ["number", "null"]},
                "total_amount": {"type": "number", "minimum": 0},
                "currency": {"type": ["string", "null"], "description": "三位币制代码 USD/EUR/CNY…"},
            },
        },
    },
}

# ---------------------------------------------------------------- 报关单 schema

DECLARATION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ExportDeclarationDoc 中华人民共和国海关出口货物报关单",
    "type": "object",
    "required": ["doc_type", "items"],
    "properties": {
        "doc_type": {"const": "export_declaration"},
        "source_file": {"type": "string"},
        "pre_entry_no": {"type": ["string", "null"], "description": "预录入编号"},
        "customs_no": {"type": ["string", "null"], "description": "海关编号/统一编号"},
        "domestic_consignor": {
            "type": "object",
            "description": "境内发货人（生产销售单位）",
            "properties": {
                "name": {"type": ["string", "null"]},
                "customs_code": {"type": ["string", "null"], "description": "海关注册编码（10 位数字）"},
                "uscc": {"type": ["string", "null"], "description": "统一社会信用代码（18 位）"},
            },
        },
        "overseas_consignee": {
            "type": "object",
            "description": "境外收货人",
            "properties": {"name": {"type": ["string", "null"]}},
        },
        "transport_mode": {"type": ["string", "null"], "description": "运输方式：江海运输/公路运输/航空运输…"},
        "vessel": {"type": ["string", "null"], "description": "运输工具名称及航次号"},
        "supervision_mode": {"type": ["string", "null"], "description": "监管方式：一般贸易/来料加工…"},
        "levy_type": {"type": ["string", "null"], "description": "征免性质：一般征税/其他…"},
        "trade_country": {"type": ["string", "null"], "description": "贸易国（地区）"},
        "port_of_loading": {"type": ["string", "null"], "description": "启运港/指运港"},
        "port_of_discharge": {"type": ["string", "null"], "description": "目的港/运抵国"},
        "incoterm": {"type": ["string", "null"], "description": "成交方式：FOB/CIF/CFR/C&F…"},
        "contract_no": {"type": ["string", "null"], "description": "合同编号"},
        "declaration_date": {"type": ["string", "null"], "description": "申报日期 YYYY-MM-DD"},
        "departure_date": {"type": ["string", "null"], "description": "出口日期 YYYY-MM-DD"},
        "package_count": {"type": ["number", "null"], "description": "件数"},
        "package_type": {"type": ["string", "null"], "description": "包装种类：纸箱/托盘…"},
        "gross_weight_kg": {"type": ["number", "null"], "description": "毛重（千克）"},
        "net_weight_kg": {"type": ["number", "null"], "description": "净重（千克）"},
        "license_no": {"type": ["string", "null"], "description": "许可证号（无则 null）"},
        "items": {
            "type": "array",
            "minItems": 1,
            "description": "表体（项号从 1 连续编号）",
            "items": {
                "type": "object",
                "required": ["name", "qty", "unit", "amount", "currency"],
                "properties": {
                    "no": {"type": ["integer", "null"], "description": "项号"},
                    "hs_code": {"type": ["string", "null"], "description": "商品编号（8-10 位数字）"},
                    "name": {"type": "string", "description": "商品名称（申报中文品名）"},
                    "spec": {"type": ["string", "null"], "description": "规格型号/申报要素"},
                    "qty": {"type": "number", "exclusiveMinimum": 0},
                    "unit": {"type": "string", "description": "申报计量单位：个/台/千克…"},
                    "second_qty": {"type": ["number", "null"], "description": "法定第二数量（如有）"},
                    "second_unit": {"type": ["string", "null"]},
                    "country_of_origin": {"type": ["string", "null"], "description": "原产国（地区）"},
                    "destination_country": {"type": ["string", "null"], "description": "最终目的国（地区）"},
                    "unit_price": {"type": ["number", "null"]},
                    "amount": {"type": "number", "minimum": 0, "description": "总价"},
                    "currency": {"type": "string", "description": "币制（三位代码）"},
                },
            },
        },
        "totals": {
            "type": ["object", "null"],
            "description": "报关单合计（如单据呈现）",
            "properties": {
                "total_amount": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
            },
        },
    },
}

SCHEMAS = {"packing": PACKING_SCHEMA, "declaration": DECLARATION_SCHEMA}

# ---------------------------------------------------------------- 通用常量

COMMON_CURRENCIES = {
    "USD", "EUR", "CNY", "JPY", "HKD", "GBP", "AUD", "CAD", "CHF", "KRW",
    "SGD", "NZD", "SEK", "NOK", "DKK", "MXN", "THB", "VND", "PHP", "IDR",
    "INR", "RUB", "TRY", "AED", "SAR", "BRL", "ZAR", "PLN", "CZK", "HUF",
}

# 出货单单位 → 报关单申报单位的归一（键小写）
UNIT_ALIASES = {
    "pcs": "个", "pc": "个", "piece": "个", "pieces": "个", "个": "个", "只": "个",
    "件": "个", "支": "个", "枚": "个", "颗": "个",
    "set": "个", "sets": "个", "套": "套", "台": "台",
    "kgs": "千克", "kg": "千克", "千克": "千克", "公斤": "千克",
    "ctn": "箱", "ctns": "箱", "carton": "箱", "cartons": "箱", "箱": "箱",
    "m": "米", "meter": "米", "meters": "米", "米": "米",
    "sqm": "平方米", "㎡": "平方米", "平方米": "平方米",
    "l": "升", "liter": "升", "liters": "升", "升": "升",
    "g": "克", "克": "克",
}

INCO_OK = {"FOB", "CIF", "CFR", "C&F", "C&I", "EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS"}

SUPERVISION_COMMON = {
    "一般贸易": "0110", "来料加工": "0214", "进料对口": "0615", "进料非对口": "0715",
    "保税工厂": "1215", "无代价抵偿": "0700", "退运货物": "4561", "其他": "9900",
}


def canonical_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    return UNIT_ALIASES.get(str(unit).strip().lower(), str(unit).strip())


def as_float(value: Any) -> float | None:
    """宽松转 float：接受 1,234.56 / 1 234,56 之外的常规写法；失败返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace(" ", "").replace("，", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
