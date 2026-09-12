"""NO.20 制造企业经营链路：生成 订单→生产→采购→库存→发货→回款 事件流。

场景来自《Datawhale FDE 案例 100》NO.20：汽车供应链企业，ERP 里有数据但老板
"看不清"——供应商少发 20 个扳手导致整单无法入库、财务付款对不上业务依据。
AI 的角色是"数据关系处理器"：把不同业务环节的数据匹配、核对、关联，异常主动提醒。

事件流（300 张销售订单展开，SQLite 四张表，植入四类异常）：
- sales_orders / shipments / receipts(采购入库) / payments(应付)
- 部分到货(4980/5000 型)、采购单价异常上浮、无采购依据的付款、超订单发货
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path


def build_db(path: Path, seed: int = 20260913, n_orders: int = 300) -> sqlite3.Connection:
    rng = random.Random(seed)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sales_orders(so_id TEXT PRIMARY KEY, cust TEXT, sku TEXT,
                                  qty INT, price REAL, so_date TEXT);
        CREATE TABLE shipments(so_id TEXT, ship_id TEXT, qty INT, ship_date TEXT);
        CREATE TABLE receipts(po_id TEXT, sku TEXT, ordered_qty INT, got_qty INT,
                              unit_price REAL, rcv_date TEXT);
        CREATE TABLE payments(pay_id TEXT, po_id TEXT, amount REAL, pay_date TEXT);
        """
    )
    skus = [f"SKU{i:03d}" for i in range(40)]
    price_map = {s: round(rng.uniform(8, 90), 1) for s in skus}
    so_rows, ship_rows, rcpt_rows, pay_rows = [], [], [], []
    anomalies = {"short_receipt": 0, "price_spike": 0, "ghost_pay": 0, "over_ship": 0}
    for i in range(n_orders):
        so = f"SO{i:04d}"
        sku = rng.choice(skus)
        qty = rng.randint(50, 2000)
        price = price_map[sku]
        so_rows.append((so, f"客户{rng.randint(1, 20):02d}", sku, qty, price,
                        f"2026-0{rng.randint(1, 6)}-{rng.randint(10, 28):02d}"))
        r = rng.random()
        if r < 0.03:  # 超订单发货
            ship_rows.append((so, f"SH{i:04d}", int(qty * 1.25), "2026-07-01"))
            anomalies["over_ship"] += 1
        else:
            ship_rows.append((so, f"SH{i:04d}", qty, "2026-07-01"))
        if rng.random() < 0.6:
            po = f"PO{i:04d}"
            ordered = qty + rng.randint(0, 500)
            if r >= 0.03 and rng.random() < 0.05:  # 部分到货（4980/5000 型）
                got = int(ordered * rng.uniform(0.94, 0.996))
                rcpt_rows.append((po, sku, ordered, got,
                                  round(price_map[sku] * rng.uniform(0.9, 1.0), 2),
                                  "2026-07-05"))
                anomalies["short_receipt"] += 1
            else:
                got = ordered
                up = price_map[sku] * rng.uniform(0.9, 1.0)
                if rng.random() < 0.04:  # 采购单价异常上浮
                    up *= rng.uniform(1.6, 2.4)
                    anomalies["price_spike"] += 1
                rcpt_rows.append((po, sku, ordered, got, round(up, 2), "2026-07-05"))
                if rng.random() < 0.05:  # 无采购依据的付款
                    pay_rows.append((f"PAY{i:04d}G", f"POX{i:04d}",
                                     round(rng.uniform(5_000, 80_000), 2), "2026-07-20"))
                    anomalies["ghost_pay"] += 1
                pay_rows.append((f"PAY{i:04d}", po, round(ordered * up, 2), "2026-07-20"))
    conn.executemany("INSERT INTO sales_orders VALUES(?,?,?,?,?,?)", so_rows)
    conn.executemany("INSERT INTO shipments VALUES(?,?,?,?)", ship_rows)
    conn.executemany("INSERT INTO receipts VALUES(?,?,?,?,?,?)", rcpt_rows)
    conn.executemany("INSERT INTO payments VALUES(?,?,?,?)", pay_rows)
    conn.commit()
    print(f"  植入异常：{anomalies}")
    return conn


def main() -> None:
    import pandas as pd

    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    conn = build_db(out / "erp.db")
    n = pd.read_sql_query(
        "SELECT (SELECT COUNT(*) FROM sales_orders) so,"
        "(SELECT COUNT(*) FROM receipts) rc,"
        "(SELECT COUNT(*) FROM payments) pay", conn)
    print(f"erp.db：订单 {n.so[0]} / 入库批次 {n.rc[0]} / 付款 {n.pay[0]}")


if __name__ == "__main__":
    main()
