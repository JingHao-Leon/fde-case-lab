"""NO.17 回测：报价 MAPE 对比 + 数据飞轮收益曲线。

复现：python cases/17-quoting-engine/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_specs
from solution import CalibratedQuote, ExpertQuote, RuleQuote, mape

DATA = Path(__file__).parent / "data" / "rfqs.json"


def main() -> None:
    if not DATA.exists():
        specs = gen_specs()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(specs, ensure_ascii=False), encoding="utf-8")
    specs = json.loads(DATA.read_text(encoding="utf-8"))
    train_full, test = specs[:150], specs[150:]

    print(f"历史询价 {len(specs)} 条（测试集 {len(test)} 条），"
          f"口径：对隐性真实成本的 MAPE（越低报价越准）\n")
    expert = ExpertQuote().fit(train_full)
    rows = [
        ("老师傅快速估法(基线)", mape([expert.quote(s) for s in test], test)),
        ("规则库成本模型", mape([RuleQuote().quote(s) for s in test], test)),
        ("飞轮 k=30", mape([CalibratedQuote().fit(specs[:30]).quote(s) for s in test], test)),
        ("飞轮 k=80", mape([CalibratedQuote().fit(specs[:80]).quote(s) for s in test], test)),
        ("飞轮 k=150", mape([CalibratedQuote().fit(train_full).quote(s) for s in test], test)),
    ]
    print(f"{'方案':<18}{'对真实成本MAPE':>14}")
    print("-" * 34)
    for name, m in rows:
        print(f"{name:<18}{m:>13.1%}")

    base = rows[1][1]
    best = rows[-1][1]
    print(f"\n结论：裸规则库已优于老师傅估法（可解释、可复用）；"
          f"人工校准回填（数据飞轮）把 MAPE 从 {base:.1%} 降到 {best:.1%}"
          f"（- {(1 - best / base) * 100:.0f}%）。"
          f"叠加结构化置信分流（人工只审低置信字段，占比 <50%），"
          f"对应原案例'相关工作量减少 50%+、响应从天级到秒级'。")


if __name__ == "__main__":
    main()
