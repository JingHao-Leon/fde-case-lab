"""NO.15 短视频脚本量产流水线：参数化生成 + 多级校验 + 回退机制。

对应 NO.15 的落地架构「字段化输入 → 生成 → 校验/审计 Loop → 人工回退」：

- NaiveWriter    "直接让 AI 写"基线：单一模板硬填，卖点复读、部分脚本夹带
                 违禁词（复现'AI 味'与合规问题的来源）。
- Pipeline       生产流水线：
    G 生成：钩子(5 选 1) + 卖点展开(必覆盖) + 场景细节 + 行动号召，语气随商户风格；
    V 校验器链：口播长度(120~220 字) → 违禁词 → 卖点覆盖 → 结构完整 → 同商户查重；
    R 回退：未过 → 换模板重写一次 → 仍未过 → 人工队列。

口径：首过率 / 终过率 / 人工回退率；同一套校验器也用于评估基线脚本可用率（公平）。
"""
from __future__ import annotations

import re

from data_gen import BANNED

HOOK_T = [
    "在{city}开了{years}年的{shop}", "被问了无数次的{shop}", "打工人的{slot}救星",
    "这家{shop}我憋了半年没说", "{city}的{slot}又被这家店承包了",
]
CTA_T = [
    "评论区扣「{kw}」，我把定位发你", "点击左下角团购直接冲", "先收藏起来，周末就带上家人去",
    "带上闺蜜一起，报我名字还能打折",
]
STYLE_TAIL = {"市井烟火": "就这么实在，不整虚的。", "精致格调": "氛围感直接拉满。",
              "家庭温馨": "带家里人一起来刚刚好。", "潮流打卡": "随手一拍就是大片。"}
DETAIL = [
    "锅气一上来整条街都闻得到", "汤汁一浇下去我口水直接绷不住",
    "面条挂汁那种浓稠感，绝了", "外皮炸得酥脆，咬开还会爆汁",
    "甜度刚刚好，喝完不口干", "肉质嫩到用筷子一拨就散",
]
RECO = [
    "头一回来的直接冲招牌，不会踩雷", "上班族下班过来吃一顿特别解压",
    "周末带爸妈来他们家准没错", "附近写字楼的同学已经替你们踩过点了",
    "这条视频先码住，下馆子的时候翻出来照着点",
]


def _fmt(sells: list[str], shop: dict) -> list[str]:
    return [s.replace("{price}", str(shop["price"])) for s in sells]


class NaiveWriter:
    """单模板硬填：卖点复读、部分脚本夹带违禁词（基线）。"""

    def __init__(self, banned: list[str] | None = None):
        self.banned = banned or []

    def write(self, brief: dict, attempt: int = 0) -> str:
        s = brief["shop"]
        sell = _fmt(brief["sells"], s)
        text = (f"{s['shop']}的{brief['dish']}真的太好吃了！{sell[0]}，{sell[0]}，"
                f"{sell[0]}，我每次来都点{brief['dish']}，{sell[1]}，吃完还想吃，"
                f"你们一定要来试试，真的不骗人，{sell[2]}，好吃到舔盘子！")
        # 40% 的脚本夹带违禁词（模拟无审计直出）
        if sum(map(ord, brief["bid"])) % 5 < 2:
            text = "这家店是全网最低的！" + text
        return text


class Pipeline:
    def __init__(self, banned: list[str] | None = None, variant_seed: int = 13):
        self.banned = banned or []
        self.seen: dict[str, list[str]] = {}
        self.variant_seed = variant_seed

    # ---- 生成 ----
    def _compose(self, brief: dict, variant: int) -> str:
        s = brief["shop"]
        sell = _fmt(brief["sells"], s)
        hook = HOOK_T[(variant + sum(map(ord, brief["bid"]))) % len(HOOK_T)].format(
            city=s["city"], years=s["years"], shop=s["shop"], slot=s["slot"])
        d1 = DETAIL[(variant + len(brief["dish"])) % len(DETAIL)]
        d2 = DETAIL[(variant * 3 + 1) % len(DETAIL)]
        reco = RECO[(variant + 2) % len(RECO)]
        body = (f"他家的{brief['dish']}是招牌，{sell[0]}，端上来{d1}。"
                f"{sell[1]}，{d2}，{reco}，味道真的有点东西，来晚了可别怪我没提醒你，人均{str(s['price'])}元就能吃到这个水准，"
                f"{STYLE_TAIL[s['style']]}")
        cta = CTA_T[(variant + 1) % len(CTA_T)].format(kw=brief["kw"])
        return f"{hook}，{body}{cta}"

    # ---- 校验器链（对所有作者通用，保证口径公平）----
    def validate(self, text: str, brief: dict) -> list[str]:
        errors = []
        n = len(re.sub(r"[，。！？、「」\s]", "", text))
        if not 120 <= n <= 220:
            errors.append(f"口播长度{n}字不在120~220区间")
        hit = [w for w in self.banned if w in text]
        if hit:
            errors.append(f"违禁词:{','.join(hit)}")
        sell = _fmt(brief["sells"], brief["shop"])
        if not any(s in text for s in sell[:2]):
            errors.append("核心卖点未覆盖")
        if text.count("。") < 1 or "，" not in text:
            errors.append("结构不完整")
        prev = self.seen.get(brief["shop"]["shop"], [])
        if any(self._overlap(text, p) > 0.8 for p in prev):
            errors.append("与已有脚本高度重复")
        return errors

    @staticmethod
    def _overlap(a: str, b: str) -> float:
        ga = {a[i:i + 4] for i in range(len(a) - 3)}
        gb = {b[i:i + 4] for i in range(len(b) - 3)}
        return len(ga & gb) / max(1, len(ga | gb))

    # ---- 流水线：生成 → 校验 → 重写 → 回退 ----
    def write(self, brief: dict, attempt: int = 0) -> tuple[str, str]:
        # 变体号与 brief 身份绑定，避免同商户脚本撞模板
        base = self.variant_seed + attempt * 2 + sum(map(ord, brief["bid"])) % 17
        text = self._compose(brief, base)
        if not self.validate(text, brief):
            self.seen.setdefault(brief["shop"]["shop"], []).append(text)
            return text, "passed"
        text2 = self._compose(brief, base + 1)
        if not self.validate(text2, brief):
            self.seen.setdefault(brief["shop"]["shop"], []).append(text2)
            return text2, "passed"
        return text2, "human"


def audit_texts(texts: list[str], briefs: list[dict], banned: list[str]) -> float:
    """用同一套校验器评估任意来源脚本的可用率（不含回退机会，一次直出）。"""
    p = Pipeline(banned=banned)
    ok = sum(1 for t, b in zip(texts, briefs) if not p.validate(t, b))
    return ok / len(texts)


def run_pipeline(briefs: list[dict], banned: list[str]) -> dict:
    p = Pipeline(banned=banned)
    statuses = []
    for b in briefs:
        _, st = p.write(b)
        statuses.append(st)
    first = statuses.count("passed") / len(statuses)  # 近似首过（见 test 拆分口径）
    human = statuses.count("human") / len(statuses)
    return {"first_pass": first, "final_pass": 1 - human, "human": human}
