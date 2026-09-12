"""NO.2 审核引擎测试：校验位、交叉校验、零漏放红线、自动化率、确定性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import gen_cases
from solution import ReviewEngineV1, ReviewEngineV2, audit, check_code_ok

CASES = gen_cases()


def test_check_code():
    ok = [c for c in CASES if c["defects"] == []][0]["docs"]["身份证"]["id_number"]
    assert check_code_ok(ok)
    broken = next(c for c in CASES if "证号校验位错误" in c["defects"])["docs"]["身份证"]["id_number"]
    assert not check_code_ok(broken)


def test_v1_leaks_defects_v2_catches_them():
    """V1 只查齐全性，跨材料不一致/校验位错误会漏放；V2 必须拦住。"""
    m = audit(CASES, ReviewEngineV1())
    assert m["false_accept"] > 0, "V1 若无漏放说明数据未植入可逃逸缺陷"
    m2 = audit(CASES, ReviewEngineV2())
    assert m2["false_accept"] == 0, "V2 存在漏放，触碰政务审核红线"


def test_v2_never_wrongly_rejects_clean_cases():
    m2 = audit(CASES, ReviewEngineV2())
    assert m2["false_block"] == 0, f"V2 误拦干净办件 {m2['false_block']} 件"


def test_v2_auto_rate_above_v1_is_meaningful():
    """V2 的自动通过应仍覆盖大多数干净办件（产能释放的意义所在）。"""
    m2 = audit(CASES, ReviewEngineV2())
    n_clean = sum(1 for c in CASES if not c["defects"])
    assert m2["auto_pass"] / n_clean >= 0.55, "自动通过覆盖率过低"


def test_decision_has_reasons():
    bad = next(c for c in CASES if "跨材料金额不一致" in c["defects"])
    d = ReviewEngineV2().review(bad)
    assert d.action == "reject" and any("金额不一致" in r for r in d.reasons)


def test_deterministic():
    a = audit(CASES[:300], ReviewEngineV2())
    b = audit(CASES[:300], ReviewEngineV2())
    assert a == b
