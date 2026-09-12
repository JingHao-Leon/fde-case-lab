"""NO.17 报价引擎测试：阶梯单调、MAPE 层次关系、飞轮收益、置信分流。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

import numpy as np

from data_gen import gen_specs
from solution import CalibratedQuote, ExpertQuote, RuleQuote, human_review_ratio, mape

SPECS = gen_specs()
TRAIN = SPECS[:150]
TEST = SPECS[150:]


def test_expert_baseline_and_rule_model_beat_naive_constant():
    """常识校验：任何模型都应好于"全部按均价报"。"""
    const = [np.mean([s["expert_price"] for s in TRAIN])] * len(TEST)
    m_const = mape(const, TEST)
    m_rule = mape([RuleQuote().quote(s) for s in TEST], TEST)
    assert m_rule < m_const


def test_flywheel_improves_over_rule_model():
    """数据飞轮：校准后 MAPE 应显著低于裸规则库。"""
    m_rule = mape([RuleQuote().quote(s) for s in TEST], TEST)
    cal = CalibratedQuote().fit(TRAIN)
    m_cal = mape([cal.quote(s) for s in TEST], TEST)
    assert m_cal < m_rule * 0.8, f"飞轮收益不足: rule={m_rule:.3f} cal={m_cal:.3f}"


def test_more_calibration_more_gain():
    """校准样本越多，MAPE 单调下降（飞轮滚起来的证据）。"""
    m30 = mape([CalibratedQuote().fit(SPECS[:30]).quote(s) for s in TEST], TEST)
    m150 = mape([CalibratedQuote().fit(SPECS[:150]).quote(s) for s in TEST], TEST)
    assert m150 < m30


def test_quantity_discount_monotone():
    """阶梯报价：同规格下单价随数量单调不增。"""
    cal = CalibratedQuote().fit(TRAIN)
    base = {"material": "304", "process": "铣削", "finish": "镀锌",
            "tolerance": "精密", "volume_cm3": 120.0, "qty": 100}
    unit_prices = []
    for q in (10, 50, 100, 500, 1000):
        s = {**base, "qty": q, "low_conf_fields": 0}
        unit_prices.append(cal.quote(s) / q)
    assert all(a >= b - 1e-9 for a, b in zip(unit_prices, unit_prices[1:]))


def test_human_review_below_half():
    """原案例验收：相关工作量减少 50% 以上 → 送审字段占比 < 50%。"""
    specs = gen_specs(seed=7, n=200)
    specs = [{**s, "low_conf_fields": 1} for s in specs]  # 每张图纸平均 1 个低置信字段
    assert human_review_ratio(specs) < 0.5


def test_deterministic():
    a = mape([CalibratedQuote().fit(TRAIN).quote(s) for s in TEST], TEST)
    b = mape([CalibratedQuote().fit(TRAIN).quote(s) for s in TEST], TEST)
    assert a == b
