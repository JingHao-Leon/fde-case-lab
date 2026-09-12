"""NO.5 TikTok 达人建联：生成达人/商品/履约状态合成数据。

场景来自《Datawhale FDE 案例 100》NO.5：头部电商的 TAP 业务——达人找人难
（大海捞针）、商品匹配难（上万选品池）、履约周期长约 30 天（运营天天人工"催"）。
AI 落地 = 匹配排序（AI 先筛、人再沟通）+ 履约状态机自动提醒（AI 催、人处理）。

数据模型：
- 500 达人：主类目/内容标签/粉丝量/历史转化率/响应率；
- 100 商品：类目/卖点标签/客单价；
- 隐含"真实匹配函数"生成每个商品的优质达人集合（gold），只可观测其特征规律；
- 履约轨迹：120 个达人 30 天的状态流水（建联→寄样→收样→创作→提交）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

CATS = ["美妆", "家居", "3C", "服饰", "食品", "母婴"]
TAGS = ["开箱", "测评", "剧情", "穿搭", "好物分享", "剧情植入"]


def gen_world(seed: int = 20260913) -> dict:
    rng = random.Random(seed)
    influencers = []
    for i in range(500):
        cat = rng.choice(CATS)
        tags = rng.sample(TAGS, 2)
        followers = int(rng.lognormvariate(10.5, 1.2))
        conv = min(0.5, max(0.01, rng.gauss(0.12, 0.05)))
        influencers.append({
            "iid": f"I{i:04d}", "cat": cat, "tags": tags, "followers": followers,
            "hist_conv": round(conv, 3), "reply_rate": round(rng.uniform(0.2, 0.95), 2),
        })
    products = []
    for j in range(100):
        cat = rng.choice(CATS)
        products.append({"pid": f"P{j:03d}", "cat": cat,
                         "tags": rng.sample(TAGS, 2),
                         "price": round(rng.uniform(30, 400), 1)})
    # 隐含真实匹配：类目一致 + (标签重叠 或 粉丝在 1万-50万 黄金段) × 转化率门槛
    def good_for(p: dict) -> set[str]:
        out = set()
        for inf in influencers:
            if inf["cat"] != p["cat"] or inf["hist_conv"] < 0.08:
                continue
            tag_overlap = len(set(inf["tags"]) & set(p["tags"]))
            golden = 10_000 <= inf["followers"] <= 500_000
            if tag_overlap >= 1 and (golden or inf["hist_conv"] > 0.2):
                out.add(inf["iid"])
        return out

    eval_products = products[:30]
    gold = {p["pid"]: sorted(good_for(p)) for p in eval_products}
    return {"influencers": influencers, "products": products, "gold": gold}


def gen_pipeline(seed: int = 7, n: int = 120, days: int = 30) -> list[dict]:
    """履约状态流水：每天每达人处于 5 状态之一；转移概率受'是否被提醒'影响。

    双组实验：manual 组（人工翻表抽查，每日 30% 提醒覆盖）vs
    system 组（提醒引擎，每日 85% 覆盖），用于回测提醒对履约周期的影响。
    """
    rng = random.Random(seed)
    states = ["建联", "寄样", "收样", "创作", "提交"]
    tracks = []
    for i in range(n):
        regime = "system" if i % 2 == 0 else "manual"
        cover = 0.85 if regime == "system" else 0.30
        track = []
        state = 0
        for d in range(days):
            reminded = rng.random() < cover
            boost = 1.6 if reminded else 1.0
            p_adv = {"建联": 0.25 * boost, "寄样": 0.30 * boost,
                     "收样": 0.22 * boost, "创作": 0.18 * boost, "提交": 0.0}[states[state]]
            if rng.random() < min(0.9, p_adv):
                state = min(state + 1, 4)
            track.append({"day": d, "state": states[state], "reminded": reminded})
        tracks.append({"iid": f"I{i:04d}", "regime": regime, "track": track,
                       "finish_day": next((t["day"] for t in track
                                           if t["state"] == "提交"), None)})
    return tracks


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    world = gen_world()
    world["pipeline"] = gen_pipeline()
    (out / "world.json").write_text(json.dumps(world, ensure_ascii=False), encoding="utf-8")
    print(f"生成 {len(world['influencers'])} 达人 / {len(world['products'])} 商品 / "
          f"30 个商品匹配 gold / {len(world['pipeline'])} 条履约轨迹 -> {out/'world.json'}")


if __name__ == "__main__":
    main()
