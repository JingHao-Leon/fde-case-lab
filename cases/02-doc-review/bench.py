"""NO.2 回测：V1 基础规则 vs V2 交叉校验+置信度分流 的审核质量与产能折算。

产能折算口径：人工审核 15min/件；V2 自动通过件人工 0 分钟，
review 件 3 分钟（只看低置信材料），reject 件 2 分钟（核对退回理由）；
按 8 小时工作日折算日产能，对照案例"日均 700-800 → 约 1100 件"。

复现：python cases/02-doc-review/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_cases
from solution import ReviewEngineV1, ReviewEngineV2, audit

DATA = Path(__file__).parent / "data" / "cases.json"
WORK_SECONDS = 8 * 3600
MANUAL_MIN = 15.0


def throughput(cases: list[dict], engine) -> float:
    total_min = 0.0
    for c in cases:
        d = engine.review(c)
        if d.auto:
            continue
        total_min += 3.0 if d.action == "review" else 2.0
    return WORK_SECONDS / 60 / (total_min / len(cases)) if total_min else 99999


def uplift_conf(cases: list[dict], delta: float) -> list[dict]:
    """模拟识别率打磨：所有材料 OCR 置信度整体上移（字段级缺陷不受影响）。"""
    out = []
    for c in cases:
        docs = {k: {**v, "conf": min(0.99, v.get("conf", 1.0) + delta)} for k, v in c["docs"].items()}
        out.append({**c, "docs": docs})
    return out


def main() -> None:
    if not DATA.exists():
        cases = gen_cases()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    cases = json.loads(DATA.read_text(encoding="utf-8"))
    print(f"办件 {len(cases)} 个（其中 {sum(1 for c in cases if c['defects'])} 个带缺陷）\n")
    print(f"{'引擎':<24}{'审核准确率':>9}{'自动通过率':>9}{'漏放':>5}{'误拦':>5}{'折算日产能':>10}")
    print("-" * 70)
    for name, cs, eng in (
        ("V1 基础规则(齐全性)", cases, ReviewEngineV1()),
        ("V2 交叉校验+置信分流", cases, ReviewEngineV2()),
        ("V2+识别率打磨(+0.12)", uplift_conf(cases, 0.12), ReviewEngineV2()),
    ):
        m = audit(cs, eng)
        t = throughput(cs, eng)
        print(f"{name:<24}{m['accuracy']:>8.1%}{m['auto_rate']:>8.1%}"
              f"{m['false_accept']:>5}{m['false_block']:>5}{t:>9.0f}件")
    print(f"\n人工基线：{WORK_SECONDS/60/MANUAL_MIN:.0f} 件/日（15min/件）")
    print("说明：产能折算只计'审核+复核'环节；原案例 1100 件/日还叠加了 RPA 自动填单、"
          "系统流转等环节的耗时节省。V1 漏放 317 件 = 政务红线，直接出局。")


if __name__ == "__main__":
    main()
