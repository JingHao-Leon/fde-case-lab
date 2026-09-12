"""NO.8 真实数据回测：Amazon-Google 商品标题实体匹配基准。

数据：Magellan/DeepMatcher 基准（Amazon vs Google Products，人工标注），
训练 6,874 对 / 测试 2,293 对。同库内核 = normalize 归一化 + 字符 n-gram TF-IDF。

复现：python cases/08-material-search/bench_real.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import er_real


def main() -> None:
    d = er_real.load()
    ids, vec, mat = er_real.build_matcher(d["B"])
    res = er_real.evaluate(d["test"], d["A"], ids, vec, mat)
    print("Amazon-Google 商品标题匹配（真实人工标注，测试集 2,293 对）\n")
    print(f"  正样本 Top1 命中标注对应商品：{res['top1_acc']:.1%}")
    print(f"  检索式匹配 F1：{res['f1']:.3f}（P={res['precision']:.3f} / R={res['recall']:.3f}）")
    print("\n同一内核在合成 ERP 物料库上 Top1 为 100%（见 bench.py）：真实标题噪声"
          "（缩写/跨平台命名差异）明显更难，但归一化+字符 n-gram 内核无需改动即可"
          "迁移，这正是案例8强调『先把清洗标准化做扎实』的原因。")


if __name__ == "__main__":
    main()
