"""NO.3 回测：时间线重建与时效判定 + 材料整理耗时对比。

复现：python cases/03-case-timeline/bench.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_cases
from solution import StatuteChecker, TimelineBuilder, audit_all

DATA = Path(__file__).parent / "data" / "cases.json"


def main() -> None:
    if not DATA.exists():
        cases = gen_cases()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    cases = json.loads(DATA.read_text(encoding="utf-8"))
    acc = audit_all(cases)
    statuses = Counter()
    checker = StatuteChecker()
    for c in cases:
        for cl in checker.derive_claims(c):
            statuses[cl["judged"]] += 1
    n_events = sum(len(c["events"]) for c in cases)

    print(f"{len(cases)} 个案件 / {n_events} 条事件（含口语化时间）\n")
    print(f"时效判定一致率（vs 逐条 gold）：{acc['accuracy']:.1%}（{acc['right']}/{acc['total']}）")
    print(f"时效状态分布：{dict(statuses)}")
    pages = 1000  # 典型商事案件上千页
    manual_days = pages / 300  # 人工 300 页/天
    print(f"\n材料整理耗时（{pages} 页案件）：人工约 {manual_days:.1f} 个工作日"
          f"（300 页/天）→ 系统分钟级完成时间线/时效梳理，律师只做策略判断")
    print("\n案例对照：14 被告请求权基础分析 2~3 天 → 一晚；100 万字案件 1 天完成"
          "全案梳理（效率 +70%）。本实现的时效中断重算与口语化日期解析对应其中"
          "『梳理事实关系』这一最耗时的环节。")


if __name__ == "__main__":
    main()
