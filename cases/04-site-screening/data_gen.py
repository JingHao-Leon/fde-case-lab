"""NO.4 城市规划选址：生成候选地块与规划约束/指标数据。

场景来自《Datawhale FDE 案例 100》NO.4：规划院的潜力用地分析——领导一句
"识别潜力用地"，下面要查资料、跑 GIS、跨部门讨论，跨部门报告要 3~5 天；
AI 后 10~20 分钟出可推敲的报告。关键判断：模型负责理解，专业工具负责计算，
规则硬约束一票否决，不搞"多智能体博弈"。

数据模型（200 块候选地块）：
- 硬约束（一票否决）：历史文化保护线、生态红线、地震断裂带避让；
- 软指标（加权评分）：面积达标度、道路通达度、市政管网覆盖、污水承载余量、
  公服配套半径、土地成本系数；
- 专家 gold 排序：由另一组"专家权重"生成（与系统默认权重不同），检验一致性。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

HARD_CONSTRAINTS = ["历史文化保护线", "生态红线", "断裂带避让区"]
SOFT = ["面积达标", "道路通达", "市政管网", "污水承载", "公服配套", "土地成本"]


def gen_parcels(seed: int = 20260913, n: int = 200) -> list[dict]:
    rng = random.Random(seed)
    parcels = []
    for i in range(n):
        p = {
            "pid": f"L{i:03d}",
            "area_ha": round(rng.uniform(0.5, 12), 1),
            "roads": rng.randint(1, 4),                     # 邻接道路数
            "utility": rng.uniform(0.2, 1.0),               # 市政管网覆盖率
            "sewage_headroom": rng.uniform(0, 1),           # 污水承载余量
            "pub_service_m": rng.randint(100, 3000),        # 到公服中心距离
            "cost_index": rng.uniform(0.4, 1.6),            # 土地成本系数（越低越好）
            "constraint": rng.choices(
                [None] + HARD_CONSTRAINTS, weights=[0.82, 0.07, 0.07, 0.04])[0],
        }
        parcels.append(p)
    return parcels


# 专家 gold 权重（模拟"多部门讨论后"的排序依据，与系统默认权重不同）
EXPERT_W = {"area": 0.10, "road": 0.25, "utility": 0.15, "sewage": 0.15,
            "service": 0.20, "cost": 0.15}


def expert_score(p: dict) -> float | None:
    if p["constraint"]:
        return None
    s = (EXPERT_W["area"] * min(1.0, p["area_ha"] / 8)
         + EXPERT_W["road"] * p["roads"] / 4
         + EXPERT_W["utility"] * p["utility"]
         + EXPERT_W["sewage"] * p["sewage_headroom"]
         + EXPERT_W["service"] * (1 - min(1.0, p["pub_service_m"] / 3000))
         + EXPERT_W["cost"] * (1.6 - p["cost_index"]) / 1.2)
    return round(s, 4)


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    parcels = gen_parcels()
    for p in parcels:
        p["expert_score"] = expert_score(p)
    valid = sum(1 for p in parcels if not p["constraint"])
    (out / "parcels.json").write_text(json.dumps(parcels, ensure_ascii=False), encoding="utf-8")
    print(f"候选地块 {len(parcels)} 块（触碰硬约束 {len(parcels)-valid} 块）-> {out/'parcels.json'}")


if __name__ == "__main__":
    main()
