"""NO.4 选址筛查求解器：硬约束一票否决 + 软指标加权评分 + 依据输出。

对应 NO.4 的关键判断「规则交给规则引擎，计算交给工具，人负责决策」：

- SiteScreener
    Step1 硬约束筛查：触碰历史文化保护线/生态红线/断裂带 → 直接淘汰（零漏筛）；
    Step2 软指标归一化（面积/道路/管网/污水/公服/成本，全部映射到 0~1）；
    Step3 默认权重加权 → Top-K 推荐名单，每块地附"依据明细"（一文一图一表）。

- 评价：Top-10 推荐与专家 gold 排序的 Top-10 重合率（Spearman 相关）；
  硬约束零漏筛；筛查耗时对比（人工 1 小时/地块 → 毫秒级全量）。
"""
from __future__ import annotations

DEFAULT_W = {"area": 0.20, "road": 0.15, "utility": 0.20, "sewage": 0.15,
             "service": 0.15, "cost": 0.15}
HARD = {"历史文化保护线", "生态红线", "断裂带避让区"}


def _soft_scores(p: dict) -> dict:
    return {
        "area": min(1.0, p["area_ha"] / 8),
        "road": p["roads"] / 4,
        "utility": p["utility"],
        "sewage": p["sewage_headroom"],
        "service": 1 - min(1.0, p["pub_service_m"] / 3000),
        "cost": max(0.0, (1.6 - p["cost_index"]) / 1.2),
    }


class SiteScreener:
    def __init__(self, weights: dict | None = None, area_target_ha: float = 8.0):
        self.w = weights or DEFAULT_W
        self.area_target = area_target_ha

    def hard_violation(self, p: dict) -> str | None:
        return p.get("constraint") or None

    def score(self, p: dict) -> tuple[float | None, dict]:
        """返回 (总分, 依据明细)；触碰硬约束返回 None。"""
        v = self.hard_violation(p)
        if v:
            return None, {"rejected_by": v}
        s = _soft_scores(p)
        total = sum(self.w[k] * s[k] for k in self.w)
        return round(total, 4), s

    def screen(self, parcels: list[dict], top_k: int = 10) -> dict:
        rejected, scored = [], []
        for p in parcels:
            v = self.hard_violation(p)
            if v:
                rejected.append({"pid": p["pid"], "rejected_by": v})
                continue
            total, detail = self.score(p)
            scored.append({"pid": p["pid"], "score": total,
                           "detail": {k: round(v_, 3) for k, v_ in detail.items()}})
        scored.sort(key=lambda x: -x["score"])
        return {
            "valid": len(scored),
            "rejected": rejected,
            "top": scored[:top_k],
            "report": self._report(rejected, scored[:top_k]),
        }

    @staticmethod
    def _report(rejected: list, top: list) -> str:
        lines = [f"一票否决淘汰 {len(rejected)} 块："
                 + "、".join(f"{r['pid']}({r['rejected_by']})" for r in rejected[:3])
                 + ("等" if len(rejected) > 3 else ""),
                 "推荐 Top10（评分/依据见明细表）："
                 + "、".join(t["pid"] for t in top)]
        return "\n".join(lines)


def topk_overlap(a: list[str], b: list[str], k: int = 10) -> float:
    sa, sb = set(a[:k]), set(b[:k])
    return len(sa & sb) / k


def spearman(rank_a: dict[str, int], rank_b: dict[str, int]) -> float:
    common = set(rank_a) & set(rank_b)
    if len(common) < 2:
        return 0.0
    d2 = sum((rank_a[x] - rank_b[x]) ** 2 for x in common)
    n = len(common)
    return 1 - 6 * d2 / (n * (n * n - 1))
