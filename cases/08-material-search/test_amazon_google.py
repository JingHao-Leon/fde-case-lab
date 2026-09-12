"""NO.8 真实基准测试：Amazon-Google 商品匹配的 Top1 与 F1。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution", "er_real"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

import er_real


def test_real_benchmark_files_exist():
    for f in ("tableA.csv", "tableB.csv", "train.csv", "test.csv"):
        assert (er_real.DATA_DIR / f).exists(), f"真实基准文件缺失 {f}"


def test_real_top1_and_f1():
    d = er_real.load()
    ids, vec, mat = er_real.build_matcher(d["B"])
    res = er_real.evaluate(d["test"], d["A"], ids, vec, mat)
    assert res["top1_acc"] >= 0.6, f"真实标题 Top1 {res['top1_acc']:.0%} 过低"
    assert res["f1"] >= 0.55, f"真实标题 F1 {res['f1']:.2f} 过低"


def test_deterministic():
    d = er_real.load()
    ids, vec, mat = er_real.build_matcher(d["B"])
    a = er_real.evaluate(d["test"].head(200), d["A"], ids, vec, mat)
    b = er_real.evaluate(d["test"].head(200), d["A"], ids, vec, mat)
    assert a == b
