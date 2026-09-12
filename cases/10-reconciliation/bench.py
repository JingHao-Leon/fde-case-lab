"""NO.10 对账回测：精确匹配 vs 多级模糊匹配的差异检出与净额还原精度。

复现：python cases/10-reconciliation/bench.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_ledger
from solution import ExactMatcher, FuzzyReconciler

DATA = Path(__file__).parent / "data" / "ledger.json"


def evaluate(res, truth):
    planted = [t for t in truth if t["mall_status"] != "ok"]
    # 正确分类的差异：OCR抢救(id_corrupted)、漂移对(drifted)、拆单(split)
    classified = len(res.rescued_id) + len(res.drift) + len(res.split)
    true_net = sum(-t["amount"] if t["mall_status"] == "missing" else 0 for t in planted)
    return {
        "classified": classified,
        "recall": min(1.0, classified / max(1, len(planted))) * 100,
        "missing_n": len(res.missing_in_mall),
        "extra_n": len(res.extra_in_mall),
        "net_err": abs(res.net_diff - true_net),
        "rescued": len(res.rescued_id),
    }


def main() -> None:
    if not DATA.exists():
        data = gen_ledger()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    data = json.loads(DATA.read_text(encoding="utf-8"))
    pos, mall, truth = data["pos"], data["mall"], data["truth"]
    planted_n = sum(1 for t in truth if t["mall_status"] != "ok")
    print(f"流水：POS {len(pos)} 笔 / 商场 {len(mall)} 笔，植入差异 {planted_n} 笔\n")

    manual_s = len(pos) * 0.35  # 人工逐笔 0.35s/笔（肉眼+核对）
    rows = []
    for name, solver in (("精确匹配(第一轮人工划账)", ExactMatcher()),
                         ("多级模糊匹配(Fuzzy)", FuzzyReconciler())):
        t0 = time.perf_counter()
        res = solver.run(pos, mall)
        dt = time.perf_counter() - t0
        ev = evaluate(res, truth)
        rows.append((name, res, ev, dt))

    print(f"{'方法':<18}{'分类召回':>8}{'OCR抢救':>8}{'判漏记':>7}{'判多记':>7}{'净额误差(元)':>12}{'耗时':>9}")
    print("-" * 76)
    for name, _, ev, dt in rows:
        print(f"{name:<18}{ev['recall']:>7.1f}%{ev['rescued']:>8}{ev['missing_n']:>7}"
              f"{ev['extra_n']:>7}{ev['net_err']:>12.2f}{dt*1000:>7.0f}ms")
    r = rows[-1][1]
    print(f"\n多级匹配找回差异 {r.anomaly_count} 笔；净差异 {r.net_diff:,.2f} 元"
          f"（原流程中这部分常落在'容忍区间'内被放弃）")


if __name__ == "__main__":
    main()
