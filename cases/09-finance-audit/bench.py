"""NO.9 回测：科目映射 + 双角色交叉复核的直通率与风险检出。

复现：python cases/09-finance-audit/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_bills
from solution import audit

DATA = Path(__file__).parent / "data" / "bills.json"


def main() -> None:
    if not DATA.exists():
        bills = gen_bills()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(bills, ensure_ascii=False), encoding="utf-8")
    bills = json.loads(DATA.read_text(encoding="utf-8"))
    r = audit(bills)
    manual_min_per_bill = 8.0  # 人工判断+录入 8 分钟/张

    print(f"报销单 {r['total']} 张（其中问题单 {r['issue_total']} 张）\n")
    print(f"科目映射准确率：{r['subject_acc']:.1%}（规则引擎，可解释）")
    print(f"自动直通率：    {r['auto_rate']:.1%}（确定单 AI 直通，人只看风险队列）")
    print(f"问题检出率：    {r['recall']:.1%}（{r['issue_caught']}/{r['issue_total']}）")
    print(f"误放（问题却直通）：{r['missed']} 张 —— 财务红线，必须为 0")
    print(f"折算：人工 {manual_min_per_bill:.0f} 分钟/张 → 直通后人工只需审"
          f" {r['total'] - r['auto_rate'] * r['total']:.0f} 张风险单")
    print("\n案例对照：财务流程从半个月~一个月 → 1~2 天（AI 判断 + 监督 + RPA 执行）；"
          "人从'处理所有单据'退到'处理风险队列'。本实现未含 RPA 环节。")


if __name__ == "__main__":
    main()
