"""确定性审查引擎：报关单结构校验（S）、出货单结构校验（P）、两单对齐校验（A）。

所有规则都是纯函数：输入两份标准 JSON，输出 findings。数字判断绝不经过
LLM —— LLM 只负责上游抽取与品名等语义对齐的复核提示。
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from .schema import COMMON_CURRENCIES, INCO_OK, SUPERVISION_COMMON, as_float, canonical_unit

# 可调容差（相对值针对金额类，绝对值针对重量/计数）
TOLERANCE = {
    "amount_rel": 0.005,     # 金额相对容差 0.5%
    "amount_abs": 1.0,       # 金额绝对容差（低值兜底）
    "weight_abs": 0.5,       # 重量绝对容差 kg
    "weight_rel": 0.005,     # 重量相对容差 0.5%
    "name_match": 0.55,      # 品名匹配阈值
    "name_weak": 0.35,       # 品名弱匹配下限
    "party_match": 0.60,     # 收发货人匹配阈值
}

HS_RE = re.compile(r"^\d{8}(?:\d{2}|\d{5})?$")  # 8 位基础 + 2/5 位附加
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日")

COMPANY_SUFFIXES = (
    "co.,ltd", "co.,ltd.", "coltd", "co,ltd", "ltd.", "ltd", "limited", "inc.", "inc",
    "llc", "gmbh", "s.a.", "sa", "b.v.", "bv", "pte", "ltd.,", "corp.", "corp",
    "有限公司", "股份有限公司", "有限责任公司", "进出口有限公司", "公司",
)


@dataclass
class Finding:
    rule: str            # 规则编号，如 S1 / P2 / A4
    severity: str        # error / warning / info
    field: str           # 相关字段
    message: str         # 人读说明（中文）
    left_value: Any = None   # 出货单侧值
    right_value: Any = None  # 报关单侧值
    item: int | None = None  # 涉及行号（表体）

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)

    def add(self, rule: str, severity: str, field_: str, message: str, **kw: Any) -> None:
        self.findings.append(Finding(rule, severity, field_, message, **kw))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]


# ================================================================ 工具

def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, (date, datetime)):
        return value if isinstance(value, date) and not isinstance(value, datetime) else value.date()
    s = str(value).strip()
    for fmt in DATE_FORMATS:
        # 单据日期无时区语义，naive strptime 属预期
        try:
            return datetime.strptime(s, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None


def norm_text(value: Any) -> str:
    s = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[\s.,，。、;；:：'\"()（）\[\]【】-]+", "", s)


def similiarity(a: str, b: str) -> float:
    na, nb = norm_text(a), norm_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na), set(nb)
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(ratio, jac)


def strip_company_suffix(name: str) -> str:
    n = norm_text(name)
    changed = True
    while changed and n:
        changed = False
        for suf in COMPANY_SUFFIXES:
            sn = norm_text(suf)
            if n.endswith(sn) and sn:
                n = n[: -len(sn)]
                changed = True
                break
    return n


def company_similar(a: str, b: str) -> float:
    return similiarity(strip_company_suffix(a), strip_company_suffix(b))


CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def is_cross_language(a: Any, b: Any) -> bool:
    """一边是中文一边是纯西文：确定性比对无法判断，只能降级提示。"""
    return bool(CJK_RE.search(str(a or ""))) != bool(CJK_RE.search(str(b or "")))


def _close(a: float, b: float, rel: float, abs_: float) -> bool:
    return abs(a - b) <= max(abs_, abs(b) * rel)


def _name_score(p_name: str, p_name_en: str | None, d_name: str, hs_prefix_same: bool) -> float:
    s = max(similiarity(p_name or "", d_name), similiarity(p_name_en or "", d_name))
    if hs_prefix_same:
        s = min(1.0, s + 0.15)
    return s


# ================================================================ S：报关单结构校验

HEADER_REQUIRED = [
    ("domestic_consignor.name", "境内发货人名称"),
    ("overseas_consignee.name", "境外收货人名称"),
    ("transport_mode", "运输方式"),
    ("supervision_mode", "监管方式"),
    ("incoterm", "成交方式"),
    ("trade_country", "贸易国（地区）"),
    ("port_of_loading", "启运港"),
    ("port_of_discharge", "目的港/运抵国"),
    ("declaration_date", "申报日期"),
    ("package_count", "件数"),
    ("gross_weight_kg", "毛重"),
    ("net_weight_kg", "净重"),
]
ITEM_REQUIRED = [
    ("hs_code", "商品编号"),
    ("name", "商品名称"),
    ("qty", "申报数量"),
    ("unit", "计量单位"),
    ("amount", "总价"),
    ("currency", "币制"),
    ("destination_country", "最终目的国"),
]


def check_declaration(d: dict[str, Any], r: AuditResult) -> None:
    def dig(path: str) -> Any:
        cur: Any = d
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    # S1 必填
    for path, label in HEADER_REQUIRED:
        v = dig(path)
        if v is None or (isinstance(v, str) and not v.strip()):
            r.add("S1", "error", path, f"报关单表头缺失必填项：{label}")
    items = d.get("items") or []
    if not items:
        r.add("S1", "error", "items", "报关单表体为空")
        return

    for i, it in enumerate(items, 1):
        for path, label in ITEM_REQUIRED:
            v = it.get(path)
            if v is None or (isinstance(v, str) and not v.strip()):
                r.add("S1", "error", f"items[{i}].{path}", f"第{i}项缺失必填项：{label}", item=i)

    for i, it in enumerate(items, 1):
        # S2 HS 编码
        hs = str(it.get("hs_code") or "").strip()
        if hs and not HS_RE.match(hs):
            r.add("S2", "error", f"items[{i}].hs_code", f"第{i}项 HS 编码格式非法（应为 8-10 位数字）：{hs}", item=i)

        # S3 数量/金额
        qty, amount = as_float(it.get("qty")), as_float(it.get("amount"))
        if qty is not None and qty <= 0:
            r.add("S3", "error", f"items[{i}].qty", f"第{i}项申报数量应大于 0", item=i)
        if amount is not None and amount <= 0:
            r.add("S3", "error", f"items[{i}].amount", f"第{i}项总价应大于 0", item=i)

        # S5 币制
        cur = str(it.get("currency") or "").strip().upper()
        if cur:
            if len(cur) != 3 or not cur.isalpha():
                r.add("S5", "error", f"items[{i}].currency", f"第{i}项币制应为三位代码：{cur}", item=i)
            elif cur not in COMMON_CURRENCIES:
                r.add("S5", "info", f"items[{i}].currency", f"第{i}项币制不在常见币种表内，请人工确认：{cur}", item=i)

        # S8 单价×数量≈总价
        unit_price = as_float(it.get("unit_price"))
        if unit_price is not None and qty is not None and amount is not None:
            expect = unit_price * qty
            if not _close(expect, amount, TOLERANCE["amount_rel"], TOLERANCE["amount_abs"]):
                r.add(
                    "S8", "error", f"items[{i}].amount",
                    f"第{i}项 单价×数量={expect:.4f} 与总价 {amount:.4f} 不符（容差 0.5%）",
                    left_value=round(expect, 4), right_value=amount, item=i,
                )

    # S4 日期逻辑：出口日期早于申报日期 → 现场先放行后补录情形，提示人工确认
    dd, xd = parse_date(d.get("declaration_date")), parse_date(d.get("departure_date"))
    if dd and xd and xd < dd:
        r.add("S4", "warning", "departure_date",
              f"出口日期（{xd}）早于申报日期（{dd}），如非先放行后补录情形请核实",
              left_value=str(xd), right_value=str(dd))

    # S6 毛净重
    gw, nw = as_float(d.get("gross_weight_kg")), as_float(d.get("net_weight_kg"))
    if gw is not None and nw is not None and nw > gw:
        r.add("S6", "error", "net_weight_kg", f"净重（{nw}kg）大于毛重（{gw}kg）", left_value=nw, right_value=gw)

    # S7 项号连续
    nos = [it.get("no") for it in items]
    if all(isinstance(n, int) for n in nos) and nos and nos != list(range(1, len(items) + 1)):
        r.add("S7", "warning", "items[].no", f"表体项号不连续（应为 1..{len(items)}）：{nos}")

    # S9 表体合计 vs 单据合计
    totals = d.get("totals") or {}
    t_amount = as_float(totals.get("total_amount"))
    if t_amount is not None:
        sum_items = sum(as_float(it.get("amount")) or 0.0 for it in items)
        if not _close(sum_items, t_amount, TOLERANCE["amount_rel"], TOLERANCE["amount_abs"]):
            r.add("S9", "error", "totals.total_amount",
                  f"表体合计 {sum_items:.2f} 与单据合计 {t_amount:.2f} 不符",
                  left_value=round(sum_items, 2), right_value=t_amount)

    # 附加：成交方式取值与监管方式白名单提示
    incoterm = norm_text(d.get("incoterm")).upper()
    if incoterm and not any(k in incoterm for k in INCO_OK):
        r.add("S1", "warning", "incoterm", f"成交方式取值异常：{d.get('incoterm')}")
    sup = norm_text(d.get("supervision_mode"))
    if sup and not any(norm_text(k) in sup or norm_text(v) in sup for k, v in SUPERVISION_COMMON.items()):
        r.add("S1", "info", "supervision_mode", f"监管方式非常见贸易方式，请人工确认：{d.get('supervision_mode')}")


# ================================================================ P：出货单结构校验

def check_packing(p: dict[str, Any], r: AuditResult) -> None:
    lines = p.get("lines") or []
    if not lines:
        r.add("P1", "error", "lines", "出货单明细行为空")
        return

    sum_amount, sum_gw, sum_nw, sum_ctns = 0.0, 0.0, 0.0, 0.0
    has_gw = has_nw = has_ctns = False
    for i, ln in enumerate(lines, 1):
        qty, amount = as_float(ln.get("qty")), as_float(ln.get("amount"))
        if qty is not None and qty <= 0:
            r.add("P1", "error", f"lines[{i}].qty", f"出货单第{i}行数量应大于 0", item=i)
        if amount is None:
            r.add("P1", "error", f"lines[{i}].amount", f"出货单第{i}行缺金额", item=i)
        elif amount < 0:
            r.add("P1", "error", f"lines[{i}].amount", f"出货单第{i}行金额为负", item=i)
        else:
            sum_amount += amount
        up = as_float(ln.get("unit_price"))
        if (up is not None and qty is not None and amount is not None
                and not _close(up * qty, amount, TOLERANCE["amount_rel"], TOLERANCE["amount_abs"])):
            r.add("P2", "error", f"lines[{i}].amount",
                  f"出货单第{i}行 单价×数量={up * qty:.4f} 与金额 {amount:.4f} 不符",
                  left_value=round(up * qty, 4), right_value=amount, item=i)
        gw, nw, ct = as_float(ln.get("gross_weight_kg")), as_float(ln.get("net_weight_kg")), as_float(ln.get("cartons"))
        if gw is not None:
            sum_gw += gw
            has_gw = True
        if nw is not None:
            sum_nw += nw
            has_nw = True
        if ct is not None:
            sum_ctns += ct
            has_ctns = True

    totals = p.get("totals") or {}
    t_amount = as_float(totals.get("total_amount"))
    if t_amount is not None and not _close(sum_amount, t_amount, TOLERANCE["amount_rel"], TOLERANCE["amount_abs"]):
        r.add("P3", "error", "totals.total_amount",
              f"出货单明细合计 {sum_amount:.2f} 与单据总计 {t_amount:.2f} 不符",
              left_value=round(sum_amount, 2), right_value=t_amount)
    t_gw = as_float(totals.get("gross_weight_kg"))
    if has_gw and t_gw is not None and not _close(sum_gw, t_gw, TOLERANCE["weight_rel"], TOLERANCE["weight_abs"]):
        r.add("P3", "warning", "totals.gross_weight_kg",
              f"出货单分行毛重合计 {sum_gw:.2f}kg 与总计 {t_gw:.2f}kg 不符",
              left_value=round(sum_gw, 2), right_value=t_gw)
    t_nw = as_float(totals.get("net_weight_kg"))
    if has_nw and t_nw is not None and not _close(sum_nw, t_nw, TOLERANCE["weight_rel"], TOLERANCE["weight_abs"]):
        r.add("P3", "warning", "totals.net_weight_kg",
              f"出货单分行净重合计 {sum_nw:.2f}kg 与总计 {t_nw:.2f}kg 不符",
              left_value=round(sum_nw, 2), right_value=t_nw)
    t_pkgs = as_float(totals.get("packages"))
    if has_ctns and t_pkgs is not None and abs(sum_ctns - t_pkgs) > 0.5:
        r.add("P3", "warning", "totals.packages",
              f"出货单分行箱数合计 {sum_ctns:g} 与总计 {t_pkgs:g} 不符",
              left_value=sum_ctns, right_value=t_pkgs)
    if t_gw is not None and t_nw is not None and t_nw > t_gw:
        r.add("P4", "error", "totals.net_weight_kg",
              f"出货单净重（{t_nw}kg）大于毛重（{t_gw}kg）", left_value=t_nw, right_value=t_gw)


# ================================================================ A：出货单 ↔ 报关单对齐

def match_lines(p: dict[str, Any], d: dict[str, Any]) -> list[tuple[int, int, float]]:
    """贪心一对一匹配：返回 (packing 行下标, declaration 项下标, 分数)。"""
    pairs: list[tuple[float, int, int]] = []
    for pi, pl in enumerate(p.get("lines") or []):
        for di, di_item in enumerate(d.get("items") or []):
            hs_same = bool(pl.get("hs_code")) and bool(di_item.get("hs_code")) and \
                str(pl["hs_code"])[:6] == str(di_item["hs_code"])[:6]
            score = _name_score(str(pl.get("name") or ""), pl.get("name_en"), str(di_item.get("name") or ""), hs_same)
            if score >= TOLERANCE["name_weak"]:
                pairs.append((score, pi, di))
    pairs.sort(reverse=True)
    used_p: set[int] = set()
    used_d: set[int] = set()
    out: list[tuple[int, int, float]] = []
    for score, pi, di in pairs:
        if pi in used_p or di in used_d:
            continue
        used_p.add(pi)
        used_d.add(di)
        out.append((pi, di, score))
    return out


def check_alignment(p: dict[str, Any], d: dict[str, Any], r: AuditResult) -> None:
    pt = p.get("totals") or {}
    lines = p.get("lines") or []
    items = d.get("items") or []

    # A1/A2 总毛净重
    for key, rule, label in [("gross_weight_kg", "A1", "总毛重"), ("net_weight_kg", "A2", "总净重")]:
        pv, dv = as_float(pt.get(key)), as_float(d.get(key))
        if pv is not None and dv is not None and not _close(dv, pv, TOLERANCE["weight_rel"], TOLERANCE["weight_abs"]):
            r.add(rule, "error", key,
                  f"{label}不一致：出货单 {pv}kg vs 报关单 {dv}kg（差 {dv - pv:+.2f}kg）",
                  left_value=pv, right_value=dv)

    # A3 总件数
    pv, dv = as_float(pt.get("packages")), as_float(d.get("package_count"))
    if pv is not None and dv is not None and abs(dv - pv) > 0.5:
        r.add("A3", "error", "package_count",
              f"总件数不一致：出货单 {pv:g} vs 报关单 {dv:g}", left_value=pv, right_value=dv)

    # A4 总金额
    pv, dv = as_float(pt.get("total_amount")), None
    if (d.get("totals") or {}).get("total_amount") is not None:
        dv = as_float(d["totals"]["total_amount"])
    elif items:
        dv = sum(as_float(it.get("amount")) or 0.0 for it in items)
    if pv is not None and dv is not None:
        diff = dv - pv
        if abs(diff) <= TOLERANCE["amount_abs"]:
            pass
        elif _close(dv, pv, TOLERANCE["amount_rel"], TOLERANCE["amount_abs"]):
            r.add("A4", "warning", "total_amount",
                  f"总金额小幅差异：出货单 {pv:.2f} vs 报关单 {dv:.2f}（差 {diff:+.2f}），请确认是否为运保费或尾差",
                  left_value=pv, right_value=dv)
        else:
            r.add("A4", "error", "total_amount",
                  f"总金额不一致：出货单 {pv:.2f} vs 报关单 {dv:.2f}（差 {diff:+.2f}，{(diff / pv * 100 if pv else 0):+.2f}%）",
                  left_value=pv, right_value=dv)
        if diff and str(norm_text(d.get("incoterm"))).startswith(("cif", "cfr", "c&f")):
            r.add("A4", "info", "incoterm", "成交方式含运保费（CIF/CFR），报关单总价与出货单金额允许差异，请人工确认口径")

    # A5/A6 行级对齐
    matches = match_lines(p, d)
    matched_p = {pi for pi, _, _ in matches}
    matched_d = {di for _, di, _ in matches}
    for pi, di, score in sorted(matches):
        pl, di_item = lines[pi], items[di]
        n = di + 1
        if score < TOLERANCE["name_match"]:
            r.add("A5", "warning", f"items[{n}].name",
                  f"行匹配存疑（相似度 {score:.2f}）：出货单“{pl.get('name')}” ↔ 报关单第{n}项“{di_item.get('name')}”，请人工确认",
                  left_value=pl.get("name"), right_value=di_item.get("name"))
        # A5 数量
        pq, dq = as_float(pl.get("qty")), as_float(di_item.get("qty"))
        pu, du = canonical_unit(pl.get("unit")), canonical_unit(di_item.get("unit"))
        if pq is not None and dq is not None:
            if pu and du and pu == du:
                if abs(dq - pq) > max(0.5, abs(pq) * 0.001):
                    r.add("A5", "error", f"items[{n}].qty",
                          f"数量不一致（{pu}）：出货单 {pq:g} vs 报关单 {dq:g}",
                          left_value=pq, right_value=dq, item=n)
            else:
                r.add("A5", "warning", f"items[{n}].unit",
                      f"计量单位不同（出货单“{pl.get('unit')}” vs 报关单“{di_item.get('unit')}”），无法自动换算，请人工核对数量：{pq:g} vs {dq:g}",
                      left_value=f"{pq:g} {pl.get('unit')}", right_value=f"{dq:g} {di_item.get('unit')}", item=n)
        # A6 HS
        ph, dh = str(pl.get("hs_code") or "").strip(), str(di_item.get("hs_code") or "").strip()
        if ph and dh:
            if ph[:6] != dh[:6]:
                r.add("A6", "error", f"items[{n}].hs_code",
                      f"HS 编码前 6 位不一致：出货单 {ph} vs 报关单 {dh}",
                      left_value=ph, right_value=dh, item=n)
            elif ph[: min(len(ph), len(dh))] != dh[: min(len(ph), len(dh))]:
                r.add("A6", "warning", f"items[{n}].hs_code",
                      f"HS 编码附加位不一致：出货单 {ph} vs 报关单 {dh}",
                      left_value=ph, right_value=dh, item=n)

    # 未匹配行提示
    for pi, pl in enumerate(lines):
        if pi not in matched_p:
            r.add("A5", "warning", "lines",
                  f"出货单行“{pl.get('name')}”未能在报关单表体找到匹配项，请人工核对")
    for di, di_item in enumerate(items):
        if di not in matched_d:
            r.add("A5", "warning", "items",
                  f"报关单第{di + 1}项“{di_item.get('name')}”未能在出货单找到匹配行（多行合并申报属正常，请确认）", item=di + 1)

    if len(lines) != len(items) and lines and items:
        r.add("A9", "info", "items",
              f"行数不同：出货单 {len(lines)} 行 vs 报关单 {len(items)} 项（合并申报常见，请按行明细确认）")

    # A7 收发货人
    shipper, consignor = str(p.get("shipper") or ""), str((d.get("domestic_consignor") or {}).get("name") or "")
    if shipper and consignor and company_similar(shipper, consignor) < TOLERANCE["party_match"]:
        if is_cross_language(shipper, consignor):
            r.add("A7", "info", "domestic_consignor.name",
                  f"发货人为中英双语（出货单“{shipper}” vs 报关单“{consignor}”），规则引擎无法自动比对，请由模型/人工确认一致性",
                  left_value=shipper, right_value=consignor)
        else:
            r.add("A7", "warning", "domestic_consignor.name",
                  f"发货人疑似不一致：出货单 SHIPPER“{shipper}” vs 报关单境内发货人“{consignor}”",
                  left_value=shipper, right_value=consignor)
    consignee, overseas = str(p.get("consignee") or ""), str((d.get("overseas_consignee") or {}).get("name") or "")
    if consignee and overseas and company_similar(consignee, overseas) < TOLERANCE["party_match"]:
        if is_cross_language(consignee, overseas):
            r.add("A7", "info", "overseas_consignee.name",
                  f"收货人为中英双语（出货单“{consignee}” vs 报关单“{overseas}”），请由模型/人工确认一致性",
                  left_value=consignee, right_value=overseas)
        else:
            r.add("A7", "warning", "overseas_consignee.name",
                  f"收货人疑似不一致：出货单 CONSIGNEE“{consignee}” vs 报关单境外收货人“{overseas}”",
                  left_value=consignee, right_value=overseas)

    # A8 目的港
    p_pod, d_pod = str(p.get("port_of_discharge") or ""), str(d.get("port_of_discharge") or "")
    if p_pod and d_pod and similiarity(p_pod, d_pod) < TOLERANCE["name_weak"]:
        sev = "info" if is_cross_language(p_pod, d_pod) else "warning"
        r.add("A8", sev, "port_of_discharge",
              f"目的港疑似不一致：出货单“{p_pod}” vs 报关单“{d_pod}”，请人工确认（译名差异属正常）",
              left_value=p_pod, right_value=d_pod)

    # A10 合同/发票号引用
    d_contract, p_contract = str(d.get("contract_no") or ""), str(p.get("contract_no") or "")
    p_invoice = str(p.get("invoice_no") or "")
    if d_contract and p_contract and norm_text(d_contract) != norm_text(p_contract):
        r.add("A10", "warning", "contract_no",
              f"合同号不一致：出货单“{p_contract}” vs 报关单“{d_contract}”",
              left_value=p_contract, right_value=d_contract)
    if p_invoice and d_contract and norm_text(p_invoice) in norm_text(d_contract):
        r.add("A10", "info", "contract_no", f"报关单合同号引用了出货单发票号（{p_invoice}），请确认申报口径")


# ================================================================ 总入口

def audit(packing: dict[str, Any], declaration: dict[str, Any]) -> AuditResult:
    r = AuditResult()
    check_packing(packing, r)
    check_declaration(declaration, r)
    check_alignment(packing, declaration, r)
    r.findings.sort(key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.severity], f.rule))
    return r
