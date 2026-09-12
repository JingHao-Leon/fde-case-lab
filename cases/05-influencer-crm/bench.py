"""NO.5 回测：三档匹配排序质量 + 提醒系统的漏催与履约周期。

复现：python cases/05-influencer-crm/bench.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import gen_pipeline, gen_world
from solution import (
    FollowersRanker,
    MatchRanker,
    RuleRanker,
    fulfillment_cycles,
    hit_at_k,
    ndcg_at_k,
    simulate_missed_followup,
)

DATA = Path(__file__).parent / "data" / "world.json"


def main() -> None:
    if not DATA.exists():
        w = gen_world()
        w["pipeline"] = gen_pipeline()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    w = json.loads(DATA.read_text(encoding="utf-8"))
    infl, products, gold = w["influencers"], w["products"], w["gold"]
    eval_products = [p for p in products if p["pid"] in gold]

    print(f"达人 {len(infl)} / 商品 {len(products)} / 评测商品 {len(eval_products)} 个\n")
    print(f"{'匹配方案':<20}{'NDCG@10':>9}{'HitRate@10':>11}")
    print("-" * 42)
    for name, cls in (("粉丝量降序(人工现状)", FollowersRanker),
                      ("类目+转化率规则", RuleRanker),
                      ("标签×粉丝段×转化率", MatchRanker)):
        r = cls()
        nd = sum(ndcg_at_k(r.rank(p, infl), set(gold[p["pid"]])) for p in eval_products) / len(eval_products)
        ht = sum(hit_at_k(r.rank(p, infl), set(gold[p["pid"]])) for p in eval_products) / len(eval_products)
        print(f"{name:<20}{nd:>8.1%}{ht:>10.1%}")

    tracks = w["pipeline"]
    miss = simulate_missed_followup(tracks)
    uncov, cov = fulfillment_cycles(tracks)
    print(f"\n履约提醒（30 天 × {len(tracks)} 达人）：")
    print(f"  漏催次数：人工翻表抽查 {miss['human_missed']} 次 vs 系统提醒 {miss['system_missed']} 次")
    print(f"  平均履约周期：低提醒覆盖 {uncov:.1f} 天 vs 高提醒覆盖 {cov:.1f} 天 "
          f"（- {(1 - cov / uncov) * 100:.0f}%）")
    print("\n案例对照：履约周期约 30 天 → 试运行后约 18 天；运营从'每天翻表催人'变为"
          "'处理系统拉出的待办'。AI 先筛达人、人再沟通——高价值达人的商务关系仍留给人。")


if __name__ == "__main__":
    main()
