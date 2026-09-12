"""NO.20 回测：链路检测器集 vs 月末总额对账 的异常发现对比。

复现：python cases/20-ops-visibility/bench.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import build_db
from solution import LinkBuilder, baseline_monthly, detect_anomalies

DB = Path(__file__).parent / "data" / "erp.db"

TYPE_CN = {
    "partially_received": "部分到货(ERP卡单)",
    "price_anomaly": "采购单价异常",
    "ghost_payment": "无依据付款",
    "over_shipment": "超订单发货",
}


def main() -> None:
    if not DB.exists():
        build_db(DB)
    lb = LinkBuilder(__import__("sqlite3").connect(DB))
    alerts = detect_anomalies(lb)
    base = baseline_monthly(lb)
    c = Counter(a["type"] for a in alerts)

    print("300 张销售订单的全链路视图（订单→发货→采购入库→付款）\n")
    print(f"{'异常类型':<20}{'告警数':>6}  示例")
    print("-" * 78)
    for t, n in c.most_common():
        sample = next(a for a in alerts if a["type"] == t)
        print(f"{TYPE_CN[t]:<20}{n:>6}  {sample['obj']}：{sample['evidence']}")
    print(f"\n月末总额对账基线发现 {len(base)} 条（只在总量差异时才发现，滞后一个月）；"
          f"链路检测器发现 {len(alerts)} 条，全部附证据与建议，可即时推送。")
    print("案例对照：'4980 个扳手'不再卡死在标准流程里——系统按实收入库并提醒；"
          "老板从'问人'变成'看提醒'，应付可追溯到具体订单。")


if __name__ == "__main__":
    main()
