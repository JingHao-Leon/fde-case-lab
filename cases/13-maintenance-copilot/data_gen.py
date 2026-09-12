"""NO.13 消防维保工单：生成设备台账 + 历史月检记录 + 待填工单。

场景来自《Datawhale FDE 案例 100》NO.13：消防维保企业，一线维保大量时间耗在
重复填表——某些设备每个月出现同样的异常，月检描述基本是复制上个月的。
AI 介入点：历史记录复用推荐（自动填充）+ 工单路由。

数据模型：
- 60 台设备（5 类 × 客户 × 楼层），每类设备有固定的"惯发异常"模板与处置方式；
- 2,400 条历史月检记录（60 设备 × 40 个月）；
- 60 条"本月待填"工单：80% 与该设备历史异常一致（复用场景），20% 新异常。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DEVICES = {
    "烟感探测器": ("烟感探测器误报，现场无烟，复位后正常", "清洁除尘并复位"),
    "消火栓泵": ("消火栓泵启动按钮反馈异常，主备泵切换正常", "紧固端子并试运行"),
    "防火卷帘": ("防火卷帘下降不到位，差 30cm", "调整限位器并联动测试"),
    "应急照明": ("应急照明灯具充电指示灯不亮", "更换电池模块"),
    "喷淋末端": ("末端试水装置压力表读数偏低", "清洗过滤器并复测压力"),
}
TEAMS = {"烟感探测器": "探测组", "消火栓泵": "水系统组", "防火卷帘": "联动组",
         "应急照明": "电气组", "喷淋水" if False else "喷淋末端": "水系统组"}


def gen_data(seed: int = 20260913, n_dev: int = 60, months: int = 40) -> dict:
    rng = random.Random(seed)
    devices = []
    for i in range(n_dev):
        dtype = rng.choice(list(DEVICES))
        devices.append({"dev_id": f"D{i:02d}", "type": dtype,
                        "cust": f"物业{rng.randint(1, 12):02d}",
                        "floor": f"{rng.randint(1, 22)}F",
                        "issue": DEVICES[dtype][0], "fix": DEVICES[dtype][1]})
    history = []
    for m in range(months):
        for dev in devices:
            chronic = rng.random() < 0.72  # 该设备本月复发惯发异常
            desc = dev["issue"] if chronic else "巡检正常，功能测试通过"
            fix = dev["fix"] if chronic else "无"
            history.append({"dev_id": dev["dev_id"], "month": m,
                            "desc": desc, "fix": fix,
                            "team": TEAMS[dev["type"]]})
    # 本月待填工单：80% 复发（可复用），20% 新异常（不可复用）
    pending = []
    for dev in devices:
        if rng.random() < 0.8:
            desc, fix, reuse = dev["issue"], dev["fix"], True
        else:
            desc, fix, reuse = "设备通信板卡故障，需更换配件", "更换通信板并联调", False
        pending.append({"dev_id": dev["dev_id"], "desc": desc, "fix": fix,
                        "team": TEAMS[dev["type"]], "reuse": reuse})
    rng.shuffle(pending)
    return {"devices": devices, "history": history, "pending": pending}


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    data = gen_data()
    (out / "workorders.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"设备 {len(data['devices'])} 台 / 历史月检 {len(data['history'])} 条 / "
          f"本月待填 {len(data['pending'])} 条 -> {out/'workorders.json'}")


if __name__ == "__main__":
    main()
