"""生成 README 顶图：各案例 Before/After 对比条形图（英文标签避免字体问题）。

复现：python scripts/gen_chart.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (标签, before, after, 单位说明) —— 全部来自各案例 bench 实测
ROWS = [
    ("05 influencer NDCG@10 (x100)", 0.4, 90.3),
    ("08 product matching Top1 %", 10.0, 100.0),
    ("15 content first-pass %", 0.0, 100.0),
    ("16 analytics agent routing % (naive 20)", 20.0, 100.0),
    ("21 fire-code compliance %", 60.0, 100.0),
    ("01 KB retrieval Recall@5 %", 66.2, 99.2),
    ("02 review accuracy %", 84.2, 100.0),
    ("06 truck load (m3 of 108)", 46.4, 97.1),
    ("22 total cost index (lower=better)", 100.0, 32.5),
    ("17 quote MAPE % (lower=better)", 58.4, 9.2),
]


def main() -> None:
    out = Path(__file__).parent.parent / "docs" / "benchmark.png"
    out.parent.mkdir(exist_ok=True)
    rows = ROWS[::-1]
    labels = [r[0] for r in rows]
    before = [r[1] for r in rows]
    after = [r[2] for r in rows]
    y = range(len(rows))

    fig, ax = plt.subplots(figsize=(10, 6.4), dpi=150)
    ax.barh([i + 0.21 for i in y], before, height=0.38,
            color="#b8c2cc", label="baseline")
    ax.barh([i - 0.21 for i in y], after, height=0.38,
            color="#2f7d5f", label="this repo")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel("metric value (see each case README for definition)")
    ax.set_title("FDE Case Lab — baseline vs engineered solution (all reproducible)",
                 fontsize=11)
    for i, (b, a) in enumerate(zip(before, after)):
        ax.text(b + 1, i + 0.21, f"{b:g}", va="center", fontsize=7.5, color="#666")
        ax.text(a + 1, i - 0.21, f"{a:g}", va="center", fontsize=7.5, color="#2f7d5f")
    ax.set_xlim(0, 118)
    ax.legend(loc="lower right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
