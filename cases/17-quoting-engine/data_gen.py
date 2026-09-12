"""NO.17 非标制造报价：生成图纸需求 + 隐性"真实成本"数据。

场景来自《Datawhale FDE 案例 100》NO.17：柔性制造企业（多品种小批量），
报价依赖老师傅看图纸→拆需求→估工艺→核成本；响应慢、报价准确率直接影响利润。
AI 落地方式：图纸信息结构化 → 企业成本规则库匹配 → 人工校准回填（数据飞轮）。

本生成器模拟"真实世界"：
- 600 条历史询价（材料 × 工艺 × 尺寸 × 数量 × 表面处理 × 公差等级）；
- 真实成本由一组**隐性参数**生成（真实材料价、真实工时系数、真实批量折扣——
  对应老师傅脑子里的账），与"企业规则库"里的显式参数存在系统性偏差；
- 校准样本：每条历史报价附老师傅修正后的价格（人工校准回填的数据）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

MATERIALS = {  # (密度 g/cm3, 规则库单价 元/kg)
    "Q235": (7.85, 4.2), "304": (7.93, 13.5), "316L": (7.98, 22.0),
    "6061": (2.70, 18.0), "H13": (7.80, 15.5),
}
PROCESSES = ["车削", "铣削", "钻镗", "磨削"]
FINISH = {"无": 0.0, "发黑": 80.0, "镀锌": 150.0, "阳极氧化": 220.0}
TOL = {"普通": 1.0, "精密": 1.35, "高精": 1.8}

# —— 隐性真实参数（老师傅脑子里的账，与规则库存在系统性偏差）——
TRUE_PRICE = {"Q235": 4.6, "304": 14.2, "316L": 23.5, "6061": 19.0, "H13": 17.0}
TRUE_HOUR = {"车削": 1.15, "铣削": 1.35, "钻镗": 0.9, "磨削": 1.7}  # 小时/件
TRUE_RATE = 62.0          # 真实工时费率 元/h
TRUE_DISCOUNT = 0.22      # 真实批量折扣强度：单价 × (数量/100)^-0.22 封顶 1
TRUE_MGMT = 0.085         # 真实管理费率


def true_cost(spec: dict) -> float:
    density, _ = MATERIALS[spec["material"]]
    weight = density * spec["volume_cm3"] / 1000  # kg
    material = weight * TRUE_PRICE[spec["material"]]
    labor = TRUE_HOUR[spec["process"]] * TOL[spec["tolerance"]] * TRUE_RATE
    finish = FINISH[spec["finish"]]
    qty_factor = max(0.45, (spec["qty"] / 100) ** (-TRUE_DISCOUNT))
    return (material + labor) * qty_factor + finish * 0.4 + \
        (material + labor) * qty_factor * TRUE_MGMT


def gen_specs(seed: int = 20260913, n: int = 600) -> list[dict]:
    rng = random.Random(seed)
    specs = []
    for i in range(n):
        L, W, H = (rng.uniform(2, 40), rng.uniform(2, 30), rng.uniform(1, 15))
        spec = {
            "id": f"RFQ{i:04d}",
            "material": rng.choice(list(MATERIALS)),
            "process": rng.choice(PROCESSES),
            "finish": rng.choices(list(FINISH), weights=[5, 2, 2, 1])[0],
            "tolerance": rng.choices(list(TOL), weights=[6, 3, 1])[0],
            "volume_cm3": round(L * W * H, 1),
            "qty": rng.choice([5, 10, 20, 50, 100, 200, 500, 1000]),
        }
        # 老师傅报价 = 真实成本 × 留余量(1.04~1.10) ± 经验噪声(σ=2%)
        rng2 = random.Random(seed * 31 + i)
        noise = float(np.exp(rng2.gauss(0, 0.02)))
        spec["expert_price"] = round(true_cost(spec) * rng.uniform(1.04, 1.10) * noise, 1)
        spec["true_cost"] = round(true_cost(spec), 1)
        specs.append(spec)
    return specs


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    specs = gen_specs()
    (out / "rfqs.json").write_text(json.dumps(specs, ensure_ascii=False), encoding="utf-8")
    print(f"生成 {len(specs)} 条历史询价（含老师傅报价与隐性真实成本）-> {out/'rfqs.json'}")


if __name__ == "__main__":
    main()
