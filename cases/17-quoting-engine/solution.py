"""NO.17 非标报价求解器：老师傅基线 / 规则库成本模型 / 校准飞轮 + 置信分流。

对应 NO.17 的落地路径「图纸结构化 → 企业规则库匹配 → 人工校准回填」：

- ExpertQuote      老师傅基线：单位重量历史均价 × 重量（不看工艺/批量细节，
                   复现"经验估值"的粗粒度）。
- RuleQuote        企业成本规则库：显式参数（规则库单价/标准工时/工时费率/
                   批量折扣/管理费率）逐项核算——结构化、可解释，但参数与
                   真实世界存在系统性偏差（数据库没跟上市场价）。
- CalibratedQuote  数据飞轮：用 N 条"人工校准后的历史报价"拟合工艺级修正系数
                   （岭回归，特征=工艺/材料/公差哑变量 + log 数量），把规则库
                   拉回真实世界。对应"AI 报价 → 人审 → 回填 → 下次更准"。

置信分流：结构化字段置信度 < 0.9 的送人工复核。原案例验收：相关工作量 -50%
（这里以"人工需复核的字段占比"度量，目标 <50%）。
"""
from __future__ import annotations

import numpy as np
from data_gen import FINISH, MATERIALS, PROCESSES, TOL

# —— 企业成本规则库（显式参数，注意与 data_gen 里的隐性真实参数有系统性偏差）——
RULE_RATE = 55.0          # 工时费率（库里的旧标准）
RULE_HOUR = {"车削": 1.0, "铣削": 1.5, "钻镗": 1.1, "磨削": 1.4}
RULE_DISCOUNT = 0.15
RULE_MGMT = 0.10


def rule_cost(spec: dict) -> float:
    density, price = MATERIALS[spec["material"]]
    weight = density * spec["volume_cm3"] / 1000
    material = weight * price
    labor = RULE_HOUR[spec["process"]] * TOL[spec["tolerance"]] * RULE_RATE
    qty_factor = max(0.5, (spec["qty"] / 100) ** (-RULE_DISCOUNT))
    core = (material + labor) * qty_factor
    return core + FINISH[spec["finish"]] * 0.4 + core * RULE_MGMT


class ExpertQuote:
    """老师傅快速估法：按「材料×工艺」心算"材料费按重 + 加工费按件"。

    每组拟合 报价 = a + b×重量（a≈加工费锚点，b≈材料价），但批量折扣、
    表面处理、公差细档全靠均摊——隐性经验无法规模化的根因。
    """

    def fit(self, specs: list[dict]) -> ExpertQuote:
        groups: dict[tuple[str, str], list[tuple[float, float]]] = {}
        for s in specs:
            w = MATERIALS[s["material"]][0] * s["volume_cm3"] / 1000
            groups.setdefault((s["material"], s["process"]), []).append((w, s["expert_price"]))
        self.model = {}
        for g, pts in groups.items():
            ws = np.array([p[0] for p in pts])
            ys = np.array([p[1] for p in pts])
            b, a = np.polyfit(ws, ys, 1)
            self.model[g] = (float(a), float(b))
        self.global_ab = (float(np.mean([v[0] for v in self.model.values()])),
                          float(np.mean([v[1] for v in self.model.values()])))
        return self

    def quote(self, spec: dict) -> float:
        weight = MATERIALS[spec["material"]][0] * spec["volume_cm3"] / 1000
        a, b = self.model.get((spec["material"], spec["process"]), self.global_ab)
        return float((a + b * weight) * TOL[spec["tolerance"]])


class RuleQuote:
    def quote(self, spec: dict) -> float:
        return rule_cost(spec)


class CalibratedQuote:
    """规则库 + 校准残差回归（数据飞轮）。"""

    def __init__(self):
        self.beta = None

    @staticmethod
    def _features(spec: dict) -> list[float]:
        proc = [1.0 if spec["process"] == p else 0.0 for p in PROCESSES]
        tol = [TOL[spec["tolerance"]], spec["qty"] ** -0.5]
        return [1.0, rule_cost(spec)] + proc + tol

    def fit(self, specs: list[dict]) -> CalibratedQuote:
        X = np.array([self._features(s) for s in specs])
        y = np.array([s["expert_price"] for s in specs])
        # 岭回归（小样本防过拟合），特征已含截距
        lam = 1e-3 * len(specs)
        A = X.T @ X + lam * np.eye(X.shape[1])
        A[0, 0] -= lam  # 截距不惩罚
        self.beta = np.linalg.solve(A, X.T @ y)
        return self

    def quote(self, spec: dict) -> float:
        return float(np.dot(self._features(spec), self.beta))


def human_review_ratio(specs: list[dict], threshold: float = 0.9) -> float:
    """结构化置信分流：低置信字段送人工。真实场景字段置信度由抽取模型给出，
    这里按字段数 × 缺失/歧义比例模拟（对应图纸质量参差）。"""
    total = reviewed = 0
    for s in specs:
        fields = ["material", "process", "tolerance", "volume_cm3", "qty", "finish"]
        total += len(fields)
        n_flag = sum(1 for f in fields if s.get(f) in (None, "", 0))
        # 图纸扫描质量：给每条询价固定数量的"低置信字段"
        n_flag = max(n_flag, s.get("low_conf_fields", 0))
        reviewed += min(n_flag, len(fields))
    return reviewed / total


def mape(preds, specs) -> float:
    return float(np.mean([abs(p - s["true_cost"]) / s["true_cost"] for p, s in
                          zip(preds, specs)]))
