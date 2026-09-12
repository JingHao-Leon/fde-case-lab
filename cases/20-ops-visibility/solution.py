"""NO.20 经营链路追踪：事件流链路重建 + 规则异常检测器集。

对应 NO.20 的「链路对账 + 异常识别 + 主动提醒」：

- LinkBuilder      链路重建：把 订单/发货/采购入库/付款 四类事件按单号与 SKU
                   关联成"订单全链路视图"（真实库存视角：实际收了多少就是多少）。
- 检测器集（每类异常一个规则，输出 告警=类型/对象/证据/建议）：
    D1 部分到货    got_qty < ordered_qty 且占比 ≥ 90%（ERP 卡死、真实库存可用的场景）
    D2 采购单价异常 高于该 SKU 历史入库价中位数 × 1.5
    D3 无依据付款   payments.po_id 在 receipts 中不存在
    D4 超订单发货   shipment.qty > 订单 qty
- BaselineMonthly  人工月末对账基线：只核对总额级差异，发现不了上述任何一类
                   单据级异常（复现"有数据但看不清"）。

告警输出为结构化 dict，可推送飞书卡片（对应案例的提醒闭环）。
"""
from __future__ import annotations

import pandas as pd


class LinkBuilder:
    def __init__(self, conn):
        self.conn = conn
        self.orders = pd.read_sql_query("SELECT * FROM sales_orders", conn)
        self.ship = pd.read_sql_query("SELECT * FROM shipments", conn)
        self.rcpt = pd.read_sql_query("SELECT * FROM receipts", conn)
        self.pay = pd.read_sql_query("SELECT * FROM payments", conn)

    def order_view(self) -> pd.DataFrame:
        """订单 × 发货 × (SKU 级聚合)入库 视图：真实库存视角。"""
        ship = self.ship.groupby("so_id", as_index=False).qty.sum()
        rcpt = self.rcpt.groupby("sku", as_index=False)[["ordered_qty", "got_qty"]].sum()
        df = self.orders.merge(ship, on="so_id", how="left", suffixes=("", "_ship"))
        df = df.merge(rcpt, on="sku", how="left")
        return df


def detect_anomalies(lb: LinkBuilder) -> list[dict]:
    alerts = []
    # D1 部分到货：到货 90%~99.9% 之间（ERP 无法入库、仓库实际已有货）
    for _, r in lb.rcpt.iterrows():
        ratio = r["got_qty"] / r["ordered_qty"]
        if 0.9 <= ratio < 1.0:
            alerts.append({
                "type": "partially_received", "obj": r["po_id"],
                "evidence": f"订购 {r['ordered_qty']}，实收 {r['got_qty']}"
                            f"（缺 {r['ordered_qty'] - r['got_qty']}）",
                "advice": "按实收入库并生成短装索赔单，不要卡在标准流程里",
            })
    # D2 采购单价异常
    med = lb.rcpt.groupby("sku").unit_price.median()
    for _, r in lb.rcpt.iterrows():
        m = med.get(r["sku"])
        if m and r["unit_price"] > m * 1.5:
            alerts.append({
                "type": "price_anomaly", "obj": r["po_id"],
                "evidence": f"入库价 {r['unit_price']} 元 vs 该 SKU 中位价 {m:.1f} 元",
                "advice": "核对供应商报价单与合同价",
            })
    # D3 无采购依据的付款
    po_set = set(lb.rcpt["po_id"])
    for _, r in lb.pay.iterrows():
        if r["po_id"] not in po_set:
            alerts.append({
                "type": "ghost_payment", "obj": r["pay_id"],
                "evidence": f"付款 {r['amount']} 元，找不到对应采购入库 {r['po_id']}",
                "advice": "暂停付款，要求采购补齐三单匹配",
            })
    # D4 超订单发货
    qty = lb.orders.set_index("so_id").qty
    for _, r in lb.ship.iterrows():
        base = qty.get(r["so_id"])
        if base is not None and r["qty"] > base:
            alerts.append({
                "type": "over_shipment", "obj": r["ship_id"],
                "evidence": f"发货 {r['qty']} 超过订单量 {base}",
                "advice": "核对拣货单与客户签收，追回或补单",
            })
    return alerts


def baseline_monthly(lb: LinkBuilder) -> list[dict]:
    """人工月末对账基线：只看总额级差异——单据级异常全部漏掉。"""
    ship_total = float(lb.ship.qty.sum())
    order_total = float(lb.orders.qty.sum())
    pay_total = float(lb.pay.amount.sum())
    rcpt_value = float((lb.rcpt.ordered_qty * lb.rcpt.unit_price).sum())
    alerts = []
    if abs(pay_total - rcpt_value) / max(1.0, rcpt_value) < 0.01:
        pass  # 总额接近 → 人工判断"账平了"
    if ship_total > order_total:
        alerts.append({"type": "monthly_gap", "obj": "TOTAL",
                       "evidence": f"发货总量 {ship_total} 高于订单总量 {order_total}",
                       "advice": "月末人工复核（一个月后才知道）"})
    return alerts
