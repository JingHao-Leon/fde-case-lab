"""出货单/发票 Excel 解析：提取原始网格 + 尽力归一化（hints）。

设计原则：解析器只做"忠实提取 + 常见列名映射"，不做任何业务判断；
判断全部交给 checks.py，抽取缺口由 agent（LLM）按 schema 补齐。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .schema import as_float

# 常见列名（中英）→ 标准字段。匹配时对表头文本做 lower + 去空白。
# 顺序即优先级：具体词在前，宽泛词（unit/hs/no）放最后，避免 "UNIT PRICE" 命中 "unit"。
HEADER_ALIASES: list[tuple[tuple[str, ...], str]] = [
    (("数量", "qty", "quantity"), "qty"),
    (("单价", "unitprice", "price"), "unit_price"),
    (("金额", "总价", "totalprice", "amount", "value", "amt"), "amount"),
    (("净重", "netweight", "n.w", "nweight"), "net_weight_kg"),
    (("毛重", "grossweight", "g.w", "gweight"), "gross_weight_kg"),
    (("箱数", "件数", "cartons", "ctns", "carton", "boxes"), "cartons"),
    (("英文品名", "descriptionen", "producten"), "name_en"),
    (("型号", "规格", "model", "specification", "spec", "style"), "model"),
    (("品名", "商品名称", "货品名称", "productname", "product", "description", "goods", "货名"), "name"),
    (("hscode", "hs编码", "海关编码", "商品编码"), "hs_code"),
    (("单位", "uom"), "unit"),
]

# 抬头 key:value 抓取（单元格开头匹配，norm 后比较；值取冒号后文本）
TOP_KEYS: list[tuple[str, tuple[str, ...]]] = [
    ("invoice_no", ("invoiceno", "invoice#", "发票号")),
    ("contract_no", ("contractno", "s/cno", "合同号", "pono", "po#", "订单号")),
    ("shipper", ("shipper", "发货人", "exporter", "seller")),
    ("consignee", ("consignee", "收货人", "buyer", "importer")),
    ("incoterm", ("incoterm", "priceterm", "贸易条款")),
    ("port_of_loading", ("portofloading", "装运港", "起运港")),
    ("port_of_discharge", ("portofdischarge", "目的港", "卸货港")),
]
TOTAL_MARKS = ("total", "合计", "小计")


def _norm(text: Any) -> str:
    return re.sub(r"[\s._（）()：:/\\#-]+", "", str(text or "").lower())


# keys 统一归一化（"N.W" → "nw"），与 _map_header 里的 h 对齐
HEADER_ALIASES = [([_norm(k) for k in keys], field) for keys, field in HEADER_ALIASES]


def _map_header(text: Any) -> str | None:
    h = _norm(text)
    if not h:
        return None
    for keys, field in HEADER_ALIASES:
        if any(k in h for k in keys):
            return field
    return None


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _typed(field: str, cell: str) -> Any:
    if field in ("qty", "unit_price", "amount", "net_weight_kg", "gross_weight_kg", "cartons"):
        return as_float(cell)
    return cell


def parse(path: str | Path, max_rows: int = 500, max_cols: int = 40) -> dict[str, Any]:
    """返回 {source_file, kind, grid, hints, notes}。hints 是尽力归一化结果，允许残缺。"""
    path = Path(path)
    wb = load_workbook(path, data_only=True, read_only=True)

    hints: dict[str, Any] = {"lines": []}
    totals: dict[str, Any] = {}
    notes: list[str] = []
    grid_lines: list[str] = []       # 给 agent 看的原文网格
    header_idx: int | None = None
    col_fields: list[str | None] = []

    row_abs = 0
    for ws in wb.worksheets:
        grid_lines.append(f"### Sheet: {ws.title}")
        for row in ws.iter_rows(max_row=max_rows, max_col=max_cols, values_only=True):
            cells = [_cell_str(v) for v in row]
            while cells and cells[-1] == "":
                cells.pop()
            grid_lines.append(" | ".join(cells) if cells else "")

            if header_idx is None:
                hits = sum(1 for c in cells if _map_header(c))
                if hits >= 3:
                    header_idx = row_abs
                    col_fields = [_map_header(c) for c in cells]
                elif any(cells):
                    _absorb_top(hints, cells)
            else:
                joined = "".join(cells).lower()
                if any(m in joined for m in TOTAL_MARKS):
                    _absorb_totals_row(totals, col_fields, cells)
                elif any(cells):
                    item: dict[str, Any] = {}
                    for cell, field in zip(cells, col_fields):
                        if field and cell != "":
                            item[field] = _typed(field, cell)
                    if item.get("name") and (item.get("qty") is not None or item.get("amount") is not None):
                        hints["lines"].append(item)
            row_abs += 1
        row_abs += 1  # sheet 分隔行
    wb.close()

    if "lines" in hints:
        hints.setdefault("totals", totals)
    if header_idx is None:
        notes.append("未定位到明细表头行，lines 为空；请阅读网格原文按 schema 抽取。")
    elif "name" not in [f for f in col_fields if f]:
        notes.append("表头映射不完整（缺品名列），请阅读原文重新抽取。")
    if not hints["lines"]:
        notes.append("明细未自动解析出任何行。")
    if totals:
        hints["totals"] = totals
    return {
        "source_file": path.name,
        "kind": "packing",
        "grid": grid_lines,
        "hints": hints,
        "notes": notes,
    }


def _absorb_top(hints: dict[str, Any], cells: list[str]) -> None:
    """抬头区域：按单元格 key:value 抓取（key 出现在单元格开头，值取冒号后）。"""
    for cell in cells:
        if not cell:
            continue
        low = _norm(cell)
        if not low:
            continue
        for field, keys in TOP_KEYS:
            if hints.get(field):
                continue
            for k in keys:
                nk = _norm(k)
                if low.startswith(nk) or low == nk:
                    _, _, rest = cell.partition("：")
                    _, _, rest_en = cell.partition(":")
                    value = (rest if rest.strip() else rest_en).strip(" \t|,，")
                    if value:
                        hints[field] = value[:160]
                    break


def _absorb_totals_row(totals: dict[str, Any], col_fields: list[str | None], cells: list[str]) -> None:
    """合计行：按表头列位置吸收数字（TOTAL: 行通常只有一排数字）。"""
    alias = {"amount": "total_amount", "gross_weight_kg": "gross_weight_kg",
             "net_weight_kg": "net_weight_kg", "cartons": "packages", "qty": "total_qty"}
    for cell, field in zip(cells, col_fields):
        if not field or cell == "":
            continue
        key = alias.get(field)
        if key and totals.get(key) is None:
            v = as_float(cell)
            if v is not None:
                totals[key] = v
