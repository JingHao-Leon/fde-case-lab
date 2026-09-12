"""NO.10 线下零售智能对账：生成"门店POS vs 商场结算"合成对账数据。

场景来自《Datawhale FDE 案例 100》NO.10：门店收银系统与商场结算单两套数据
人工逐笔核对，一个周期要 1~2 个人天；差异在容忍区间内常被直接放弃。
本生成器植入五类真实差异：商场漏记、金额漂移、单号转录错误(OCR)、拆单、商场多记。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

# OCR 常见混淆对（商场录入员/扫描仪看错数字）
OCR_CONFUSION = {"0": "8", "1": "7", "5": "6", "3": "9", "2": "0"}

N_STORES = 30
TX_PER_STORE = (300, 800)


def _gen_tx(rng: random.Random, store: str, i: int) -> dict:
    amount = round(min(3000.0, max(30.0, rng.lognormvariate(4.6, 0.9))), 2)
    return {
        "tx_id": f"{store}{rng.randint(10**8, 10**9 - 1)}{i:03d}",
        "store": store,
        "amount": amount,
        "hour": rng.randrange(10, 22),
    }


def corrupt_id(rng: random.Random, tx_id: str) -> str:
    digits = [c for c in tx_id]
    pos = [i for i, c in enumerate(digits) if c in OCR_CONFUSION and i > 0]
    if not pos:
        return tx_id
    i = rng.choice(pos)
    digits[i] = OCR_CONFUSION[digits[i]]
    return "".join(digits)


def gen_ledger(seed: int = 20260913) -> dict:
    """返回 ground_truth(真值流水)、pos(门店收银账)、mall(商场结算账, 带植入差异)。"""
    rng = random.Random(seed)
    truth, pos, mall = [], [], []
    for s in range(N_STORES):
        store = f"S{s:02d}"
        for i in range(rng.randint(*TX_PER_STORE)):
            tx = _gen_tx(rng, store, i)
            truth.append({**tx, "mall_status": "ok"})
            pos.append({"tx_id": tx["tx_id"], "store": store, "amount": tx["amount"],
                        "hour": tx["hour"]})
            r = rng.random()
            if r < 0.02:  # 商场漏记
                truth[-1]["mall_status"] = "missing"
            elif r < 0.035:  # 金额漂移（结算折扣/录入错误）
                truth[-1]["mall_status"] = "drifted"
                drift = rng.choice([-5.0, -2.0, -0.01, 0.01, 2.0, 5.0])
                mall.append({"tx_id": tx["tx_id"], "store": store,
                             "amount": round(max(0.01, tx["amount"] + drift), 2),
                             "hour": tx["hour"]})
            elif r < 0.05:  # 单号转录错误（金额一致）
                truth[-1]["mall_status"] = "id_corrupted"
                mall.append({"tx_id": corrupt_id(rng, tx["tx_id"]), "store": store,
                             "amount": tx["amount"], "hour": tx["hour"]})
            elif r < 0.056:  # 拆单（商场把一笔拆成两笔）
                truth[-1]["mall_status"] = "split"
                a = round(tx["amount"] * rng.uniform(0.3, 0.7), 2)
                mall.append({"tx_id": tx["tx_id"] + "A", "store": store, "amount": a,
                             "hour": tx["hour"]})
                mall.append({"tx_id": tx["tx_id"] + "B", "store": store,
                             "amount": round(tx["amount"] - a, 2), "hour": tx["hour"]})
            elif r < 0.064:  # 商场多记（POS 没有这笔）
                mall.append({"tx_id": f"X{rng.randint(10**8, 10**9 - 1)}", "store": store,
                             "amount": _gen_tx(rng, store, 0)["amount"], "hour": tx["hour"]})
            else:
                mall.append({"tx_id": tx["tx_id"], "store": store, "amount": tx["amount"],
                             "hour": tx["hour"]})
    rng.shuffle(mall)
    return {"truth": truth, "pos": pos, "mall": mall}


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    data = gen_ledger()
    (out / "ledger.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    n = {k: len(v) for k, v in data.items()}
    planted = {}
    for t in data["truth"]:
        planted[t["mall_status"]] = planted.get(t["mall_status"], 0) + 1
    print(f"真值 {n['truth']} 笔 / POS {n['pos']} 笔 / 商场 {n['mall']} 笔；植入差异: {planted}")
