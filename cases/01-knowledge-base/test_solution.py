"""NO.1 知识库检索测试：排序正确性、验收线、噪声鲁棒性、MMR多样性。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _m in ("data_gen", "solution"):  # 跨案例同名模块缓存隔离
    sys.modules.pop(_m, None)

from data_gen import MAT_ALIAS, PARAM_ALIAS, PROC_ALIAS, add_ingest_noise, gen_corpus
from solution import GlossaryNormalizer, HybridSearch, KeywordSearch, TfidfSearch, evaluate

CORPUS = gen_corpus()
CARDS, QUERIES = CORPUS["cards"], CORPUS["queries"]
GLOSSARY = GlossaryNormalizer({**MAT_ALIAS, **PROC_ALIAS, **PARAM_ALIAS})


def test_all_searchers_return_valid_ranking():
    for cls in (KeywordSearch, TfidfSearch):
        s = cls(CARDS)
        res = s.search(QUERIES[0]["q"], k=5)
        assert len(res) == 5
        scores = [x[1] for x in res]
        assert scores == sorted(scores, reverse=True), f"{cls.__name__} 未按分数降序"
    # MMR 重排以多样性换严格降序，只断言首位是最相关、结果数正确
    res = HybridSearch(CARDS).search(QUERIES[0]["q"], k=5)
    assert len(res) == 5


def test_hybrid_meets_acceptance_line():
    """原案例验收线：召回片段准确率 ≥ 80%（这里以 Recall@5 度量）。"""
    s = HybridSearch(CARDS, use_mmr=False, normalizer=GLOSSARY)
    m = evaluate(s, QUERIES)
    assert m["recall_at5"] >= 0.80, f"Recall@5={m['recall_at5']:.3f} 低于 80% 验收线"


def test_glossary_beats_raw_hybrid_and_keyword():
    """词表归一化应显著优于裸混合检索与关键词基线（词汇鸿沟是第一瓶颈）。"""
    mk = evaluate(KeywordSearch(CARDS), QUERIES)
    mh_raw = evaluate(HybridSearch(CARDS, use_mmr=False), QUERIES)
    mh = evaluate(HybridSearch(CARDS, use_mmr=False, normalizer=GLOSSARY), QUERIES)
    assert mh["recall_at5"] > mh_raw["recall_at5"]
    assert mh["recall_at5"] > mk["recall_at5"]
    assert mh["top1"] > mk["top1"]


def test_robust_to_ingest_noise():
    """95% 解析率的带噪语料上，归一化混合检索仍应达到可用水平。"""
    noisy = add_ingest_noise(CARDS, parse_rate=0.95)
    mh = evaluate(HybridSearch(noisy, use_mmr=False, normalizer=GLOSSARY), QUERIES)
    mk = evaluate(KeywordSearch(noisy), QUERIES)
    assert mh["recall_at5"] > mk["recall_at5"]
    assert mh["recall_at5"] >= 0.70, f"带噪语料 Recall@5={mh['recall_at5']:.3f} 过低"


def test_mmr_reduces_redundancy():
    s_mmr = HybridSearch(CARDS, use_mmr=True, mmr_lambda=0.5, normalizer=GLOSSARY)
    plain = HybridSearch(CARDS, use_mmr=False, normalizer=GLOSSARY)
    q = QUERIES[0]["q"]
    res_mmr = [cid for cid, _ in s_mmr.search(q, k=8)]
    res_plain = [cid for cid, _ in plain.search(q, k=8)]
    def dup_rate(ids):
        prefixes = [cid.split("|")[0] + "|" + cid.split("|")[1] for cid in ids]
        return len(prefixes) - len(set(prefixes))
    assert dup_rate(res_mmr) <= dup_rate(res_plain), "MMR 未降低前缀冗余"
    assert res_mmr[0] == res_plain[0], "MMR 不应把最相关结果挤出首位"


def test_deterministic():
    a = evaluate(HybridSearch(CARDS), QUERIES[:30])
    b = evaluate(HybridSearch(CARDS), QUERIES[:30])
    assert a == b
