"""NO.15 本地生活短视频脚本量产：生成商户档案与文案任务。

场景来自《Datawhale FDE 案例 100》NO.15：抖音本地生活代运营，高峰一天要
200~300 条文案；好的文案靠少数运营的经验，无法规模化；直接让 AI 写"AI 味"重、
商户差异照顾不到。解法：把运营经验拆成业务字段 → 参数化生成 → 多级校验 →
不合格回退人工。

数据模型：
- 40 个餐饮商户档案（类型/主推菜品/活动/卖点/客群/语气），每个 8 条文案任务；
- 违禁词表（广告法绝对化用语）、各商户历史"好文案"片段（用于风格与查重）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

STYLES = ["市井烟火", "精致格调", "家庭温馨", "潮流打卡"]
TYPES = ["连锁餐厅", "高端酒店", "独立小店", "火锅烧烤", "茶饮咖啡"]
BANNED = ["最好吃", "第一", "绝无仅有", "顶级", "全网最低", "史上最强"]
HOOKS = ["在{city}开了{years}年的{shop}", "被问了无数次的{shop}", "打工人的{slot}救星",
         "这家{shop}我憋了半年没说", "{city}的{slot}又被这家店承包了"]
SELLS = ["现点现做", "老板亲自掌勺", "回头客占比一半", "本地食材每天现送",
         "人均{price}元吃到扶墙", "工作日免排队"]
CTAS = ["评论区扣{kw}，我发你定位", "点击左下角团购直接冲", "先收藏，周末就去",
        "带上闺蜜，报我名字打折"]


def gen_briefs(seed: int = 20260913, n_shops: int = 40, per_shop: int = 8) -> list[dict]:
    rng = random.Random(seed)
    cities = ["西安", "成都", "长沙", "郑州", "兰州"]
    slots = ["午餐", "晚餐", "下午茶", "夜宵"]
    briefs = []
    for s in range(n_shops):
        shop = {
            "shop": f"蜀香{rng.choice(['居','坊','阁','灶'])}{s:02d}" if rng.random() < 0.5
                    else f"{rng.choice(['粤','湘','川','渝'])}味轩{s:02d}",
            "city": rng.choice(cities), "type": rng.choice(TYPES),
            "style": rng.choice(STYLES), "slot": rng.choice(slots),
            "years": rng.randint(2, 15), "price": rng.randint(29, 199),
        }
        sells = rng.sample(SELLS, 3)
        for i in range(per_shop):
            briefs.append({
                "bid": f"B{s:02d}{i:02d}", "shop": shop,
                "dish": rng.choice(["毛血旺", "椒麻鸡", "烤鱼", "小炒黄牛肉", "杨枝甘露",
                                    "牛油果轻食碗", "手工水饺", "炭火肥肠"]),
                "sells": sells, "kw": rng.choice(["1", "好吃", "冲"]),
            })
    return briefs


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    briefs = gen_briefs()
    (out / "briefs.json").write_text(
        json.dumps({"briefs": briefs, "banned": BANNED}, ensure_ascii=False), encoding="utf-8")
    print(f"生成 {len(briefs)} 条文案任务（{len(set(b['shop']['shop'] for b in briefs))} 家商户）"
          f"，违禁词 {len(BANNED)} 个 -> {out/'briefs.json'}")


if __name__ == "__main__":
    main()
