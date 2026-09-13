"""NO.21 建筑消防施工图：生成建筑空间与消防规范简表。

场景来自《Datawhale FDE 案例 100》NO.21：建筑消防施工图——每处设施的位置、
间距、参数都要对照规范；一个项目数百个空间，绘制+规范核对要数天，AI 生成
后 30 分钟出初稿。核心原则：AI 负责按规范生成，人负责审核决策。

数据模型：
- 规范简表：空间类型 → 危险等级 → (K 值, 喷头最大间距, 保护半径, 保护面积)；
- 30 个空间（办公/走廊/商铺/车库/设备房），尺寸随机。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

# 危险等级 → 喷淋参数（规范简表：K 值、最大间距 m、保护半径 m、单头保护面积 m²）
HAZARD_SPEC = {
    "轻危险级": {"K": 80, "S_max": 4.4, "R": 3.11, "A": 20.0},
    "中危险级I": {"K": 80, "S_max": 3.6, "R": 2.55, "A": 12.5},
    "中危险级II": {"K": 115, "S_max": 3.4, "R": 2.40, "A": 11.5},
}
SPACE_HAZARD = {
    "办公": "轻危险级", "走廊": "中危险级I", "商铺": "中危险级II",
    "车库": "中危险级II", "设备房": "中危险级II",
}
HYDRANT_R = 25.0   # 室内消火栓保护半径（m，简表值）
EXTINGUISHER_M = 20.0  # 灭火器最大保护距离（m，简表值）


def gen_spaces(seed: int = 20260913, n: int = 30) -> list[dict]:
    rng = random.Random(seed)
    spaces = []
    for i in range(n):
        stype = rng.choices(list(SPACE_HAZARD), weights=[5, 3, 2, 2, 1])[0]
        L = round(rng.uniform(6, 40), 1)
        W = round(rng.uniform(3, 18), 1)
        spaces.append({"sid": f"SP{i:02d}", "type": stype,
                       "name": f"{stype}{i:02d}", "L": L, "W": W,
                       "hazard": SPACE_HAZARD[stype]})
    return spaces


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    spaces = gen_spaces()
    (out / "building.json").write_text(json.dumps(
        {"spaces": spaces,
         "hazard_spec": HAZARD_SPEC,
         "hydrant_r": HYDRANT_R,
         "extinguisher_m": EXTINGUISHER_M}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"生成 {len(spaces)} 个空间（总面积 "
          f"{sum(s['L']*s['W'] for s in spaces):.0f} m²）-> {out/'building.json'}")


if __name__ == "__main__":
    main()
