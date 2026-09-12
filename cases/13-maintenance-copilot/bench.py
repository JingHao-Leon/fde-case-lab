"""NO.13 回测：历史复用推荐 + 路由准确率对比。

复现：python cases/13-maintenance-copilot/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_data
from solution import ReuseRecommender, Router, route_accuracy

DATA = Path(__file__).parent / "data" / "workorders.json"
FILL_MIN = 5.0   # 人工完整填写一条月检 5 分钟
WORK_MIN = 480.0


def main() -> None:
    if not DATA.exists():
        d = gen_data()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    rec = ReuseRecommender(d["history"], d["devices"])
    router = Router(d["history"], d["devices"])
    r = rec.audit(d["pending"])

    t_full = len(d["pending"]) * FILL_MIN
    t_saved = t_full * r["chars_saved"]

    print(f"设备 {len(d['devices'])} 台 / 历史月检 {len(d['history'])} 条 / "
          f"本月待填 {len(d['pending'])} 条\n")
    print("月检描述复用：")
    print(f"  自动填充命中率 {r['hit_rate']:.0%}（建议与实际填写逐字一致）")
    print(f"  录入字符节省   {r['chars_saved']:.0%} → 单月省 {t_saved:.0f} 分钟")
    print("\n工单路由 Top1 准确率：")
    print(f"  v0 全塞综合组(现状)   {route_accuracy(router.route_v0, d['pending']):.0%}")
    print(f"  v1 设备类型→技能组    {route_accuracy(router.route_v1, d['pending']):.0%}")
    print(f"  v2 +历史处置多数票    {route_accuracy(router.route_v2, d['pending']):.0%}")
    print("\n案例对照：维保人员'一个表格填半天'的重复劳动被历史复用吸收；"
          "数据沉淀同时让老板第一次看得见哪些项目执行到位、哪些客户存在风险。")


if __name__ == "__main__":
    main()
