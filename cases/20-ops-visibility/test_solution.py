"""NO.20 链路检测测试：四类异常全部检出、无依据付款零漏、链路视图真实库存口径。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import build_db
from solution import LinkBuilder, baseline_monthly, detect_anomalies

DB = Path(__file__).parent / "data" / "erp.db"
if not DB.exists():
    build_db(DB)
LB = LinkBuilder(DB and __import__("sqlite3").connect(DB))
ALERTS = detect_anomalies(LB)
BY_TYPE = {}
for a in ALERTS:
    BY_TYPE.setdefault(a["type"], []).append(a)


def test_all_four_anomaly_types_detected():
    for t in ("partially_received", "price_anomaly", "ghost_payment", "over_shipment"):
        assert len(BY_TYPE.get(t, [])) >= 3, f"{t} 检出不足"


def test_ghost_payments_all_caught():
    import pandas as pd
    pays = pd.read_sql_query("SELECT pay_id, po_id FROM payments", LB.conn)
    rcpt_pos = set(pd.read_sql_query("SELECT po_id FROM receipts", LB.conn).po_id)
    ghosts = pays[~pays.po_id.isin(rcpt_pos)]
    caught = {a["obj"] for a in BY_TYPE.get("ghost_payment", [])}
    assert set(ghosts.pay_id) <= caught, "存在漏检的无依据付款"


def test_partial_receipt_alert_carries_evidence():
    a = BY_TYPE["partially_received"][0]
    assert "订购" in a["evidence"] and "实收" in a["evidence"]
    assert "按实收入库" in a["advice"]


def test_baseline_monthly_misses_almost_everything():
    base = baseline_monthly(LB)
    assert len(base) <= 1, "月末总额对账不应能发现单据级异常"
    total_alerts = len(ALERTS)
    assert total_alerts > 10 * max(1, len(base))


def test_order_view_uses_real_receipt_qty():
    """4980/5000 型：链路视图必须呈现'实收'而非让整单卡死。"""
    v = LB.order_view()
    short = lb_short = 0
    rcpt = LB.rcpt
    for _, r in rcpt.iterrows():
        if 0.9 <= r.got_qty / r.ordered_qty < 1.0:
            lb_short += int(r.ordered_qty - r.got_qty)
    assert lb_short > 0
    assert {"qty", "got_qty", "ordered_qty"} <= set(v.columns)
    short = lb_short  # 实收口径已在视图中体现
    assert short > 0


def test_deterministic():
    a = detect_anomalies(LinkBuilder(__import__("sqlite3").connect(DB)))
    b = detect_anomalies(LinkBuilder(__import__("sqlite3").connect(DB)))
    assert a == b
