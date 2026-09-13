"""NO.10 对账求解器测试：精确匹配、OCR 抢救、漂移、拆单、零误报、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import gen_ledger
from solution import ExactMatcher, FuzzyReconciler


def _pos_of(truth, status=None):
    out = []
    for t in truth:
        if status is None or t["mall_status"] == status:
            out.append({"tx_id": t["tx_id"], "store": t["store"], "amount": t["amount"],
                        "hour": t["hour"]})
    return out


def _mall_of(truth):
    """从真值+状态推导商场账（与 data_gen 同构，避免依赖文件）。"""
    import random
    random.Random(99)
    mall = []
    for t in truth:
        st = t["mall_status"]
        if st == "ok":
            mall.append({**t, "tx_id": t["tx_id"]})
        elif st == "missing":
            continue
        elif st == "drifted":
            mall.append({**t, "amount": round(t["amount"] + 2.0, 2)})
        elif st == "id_corrupted":
            # 0→8 是常见 OCR 混淆；保证至少一位可混淆
            mall.append({**t, "tx_id": t["tx_id"].replace("0", "8", 1)})
        elif st == "split":
            a = round(t["amount"] * 0.5, 2)
            mall.append({**t, "tx_id": t["tx_id"] + "A", "amount": a})
            mall.append({**t, "tx_id": t["tx_id"] + "B", "amount": round(t["amount"] - a, 2)})
    return mall


def test_clean_ledger_zero_false_positives():
    truth = [{"tx_id": f"T{i:04d}", "store": "S0", "amount": 100.0 + i, "hour": 12,
              "mall_status": "ok"} for i in range(50)]
    pos, mall = _pos_of(truth), _mall_of(truth)
    for solver in (ExactMatcher(), FuzzyReconciler()):
        r = solver.run(pos, mall)
        assert r.anomaly_count == 0, f"{solver} 在干净账本上误报 {r.anomaly_count}"
        assert r.matched == 50


def test_missing_and_extra_detected():
    truth = [{"tx_id": f"T{i:04d}", "store": "S0", "amount": 100.0, "hour": 12,
              "mall_status": ("missing" if i % 2 else "ok")} for i in range(20)]
    pos, mall = _pos_of(truth), _mall_of(truth)
    r = FuzzyReconciler().run(pos, mall)
    assert len(r.missing_in_mall) == 10
    assert abs(r.net_diff - (-1000.0)) < 1.0  # 商场少结 10 笔 × 100 元


def test_ocr_rescue():
    truth = [{"tx_id": "S0" + "1" * 7 + "05", "store": "S0", "amount": 88.0, "hour": 12,
              "mall_status": "id_corrupted"}]
    pos, mall = _pos_of(truth), _mall_of(truth)
    r = FuzzyReconciler().run(pos, mall)
    assert len(r.rescued_id) == 1, "OCR 单号转录错误未被抢救"


def test_drift_within_tolerance():
    truth = [{"tx_id": "T0001", "store": "S0", "amount": 200.0, "hour": 12,
              "mall_status": "drifted"}]
    pos, mall = _pos_of(truth), _mall_of(truth)  # _mall_of 漂移 +2 元
    r = FuzzyReconciler(amount_tol=5.0).run(pos, mall)
    assert len(r.drift) == 1 and abs(r.net_diff - 2.0) < 0.01


def test_split_detection():
    truth = [{"tx_id": "T0001", "store": "S0", "amount": 100.0, "hour": 12,
              "mall_status": "split"}]
    pos, mall = _pos_of(truth), _mall_of(truth)
    r = FuzzyReconciler().run(pos, mall)
    assert len(r.split) == 1, "拆单未被识别"


def test_full_dataset_recall_and_determinism():
    data = gen_ledger()
    pos, mall, truth = data["pos"], data["mall"], data["truth"]
    planted = {
        "missing": sum(1 for t in truth if t["mall_status"] == "missing"),
        "drifted": sum(1 for t in truth if t["mall_status"] == "drifted"),
        "id_corrupted": sum(1 for t in truth if t["mall_status"] == "id_corrupted"),
        "split": sum(1 for t in truth if t["mall_status"] == "split"),
    }
    r1 = FuzzyReconciler().run(pos, mall)
    r2 = FuzzyReconciler().run(pos, mall)
    assert len(r1.drift) == len(r2.drift) and len(r1.rescued_id) == len(r2.rescued_id)
    assert len(r1.rescued_id) >= planted["id_corrupted"] * 0.8, "OCR 抢救召回不足"
    assert len(r1.drift) >= planted["drifted"] * 0.8, "金额漂移检出不足"
    assert len(r1.missing_in_mall) >= planted["missing"] * 0.9, "漏记检出不足"
    assert r1.matched + r1.anomaly_count + len(r1.split) >= len(pos) * 0.99
