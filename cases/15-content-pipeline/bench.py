"""NO.15 回测：人工基线 / 直接 AI 写 / 流水线 三种生产方式的可用率与单条人工耗时。

复现：python cases/15-content-pipeline/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import BANNED, gen_briefs
from solution import NaiveWriter, audit_texts, run_pipeline

DATA = Path(__file__).parent / "data" / "briefs.json"
WORK_MIN = 480.0  # 每人每天 8 小时


def main() -> None:
    if not DATA.exists():
        briefs = gen_briefs()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps({"briefs": briefs, "banned": BANNED},
                                   ensure_ascii=False), encoding="utf-8")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    briefs, banned = d["briefs"], d["banned"]
    n = len(briefs)

    base_texts = [NaiveWriter(banned).write(b) for b in briefs]
    base_ok = audit_texts(base_texts, briefs, banned)
    pipe = run_pipeline(briefs, banned)

    # 单条人工耗时（分钟）：写作/修改 + 审查
    t_human = 24.0                    # 人工写作 24 分钟/条，质量可靠
    t_ai_direct = 0.2 + 4.0           # 生成即得，但几乎每条要人工大改（可用率低）
    t_pipe = 0.2 + pipe["human"] * 3.0 + 1.0  # 机器生成 + 抽检1min + 回退件重做3min

    print(f"文案任务 {n} 条（本地生活餐饮商户），校验口径：长度/违禁词/卖点覆盖/结构/查重\n")
    print(f"{'生产方式':<18}{'一次可用率':>9}{'人工耗时/条':>10}{'单人日交付':>9}")
    print("-" * 50)
    print(f"{'人工写作(现状)':<18}{'100%':>8}{t_human:>9.1f}min{WORK_MIN/t_human:>8.0f}条")
    print(f"{'直接AI写(基线)':<18}{base_ok:>8.0%}{t_ai_direct:>9.1f}min"
          f"{WORK_MIN/t_ai_direct:>8.0f}条")
    print(f"{'流水线+校验+回退':<17}{pipe['final_pass']:>8.0%}{t_pipe:>9.1f}min"
          f"{WORK_MIN/t_pipe:>8.0f}条")
    print(f"\n说明：流水线人工回退率 {pipe['human']:.0%}，人工角色从'写'退到'审'；"
          "校验器吸收了违禁词、卖点缺失、同商户撞模板等'AI 味'问题。")
    print("案例对照：高峰一天 200~300 条文案的产能缺口，靠'字段化经验 + 校验规则 + "
          "回退机制'补上——运营的 Know-how 变成了流水线的参数。")


if __name__ == "__main__":
    main()
