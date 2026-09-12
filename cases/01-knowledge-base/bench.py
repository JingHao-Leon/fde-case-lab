"""NO.1 知识库回测：三种检索方案在干净/带噪语料上的检索质量对比。

复现：python cases/01-knowledge-base/bench.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_gen import MAT_ALIAS, PARAM_ALIAS, PROC_ALIAS, add_ingest_noise, gen_corpus
from solution import GlossaryNormalizer, HybridSearch, KeywordSearch, TfidfSearch, evaluate

DATA = Path(__file__).parent / "data" / "corpus.json"


def main() -> None:
    if not DATA.exists():
        corpus = gen_corpus()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    corpus = json.loads(DATA.read_text(encoding="utf-8"))
    cards, queries = corpus["cards"], corpus["queries"]
    noisy = add_ingest_noise(cards, parse_rate=0.95)
    glossary = GlossaryNormalizer({**MAT_ALIAS, **PROC_ALIAS, **PARAM_ALIAS})

    rows = [
        ("关键词搜索(现状)", KeywordSearch(cards), False),
        ("TF-IDF(裸)", TfidfSearch(cards), False),
        ("混合检索(裸)", HybridSearch(cards, use_mmr=False), False),
        ("混合+词表归一化", HybridSearch(cards, use_mmr=False, normalizer=glossary), True),
    ]
    print(f"语料 {len(cards)} 张经验卡 / {len(queries)} 条新人高频问题 "
          f"(95% 解析率噪声模拟)\n")
    print(f"{'方案':<16}{'干净 Recall@5':>13}{'Top1':>8}{'MRR@10':>8}{'带噪 Recall@5':>14}")
    print("-" * 62)
    for name, s, use_gloss in rows:
        m = evaluate(s, queries)
        if use_gloss:
            noisy_s = HybridSearch(noisy, use_mmr=False, normalizer=glossary)
        elif isinstance(s, KeywordSearch):
            noisy_s = KeywordSearch(noisy)
        else:
            noisy_s = type(s)(noisy)
        mn = evaluate(noisy_s, queries)
        t0 = time.perf_counter()
        s.search(queries[0]["q"])
        lat = (time.perf_counter() - t0) * 1000
        print(f"{name:<16}{m['recall_at5']:>12.1%}{m['top1']:>8.1%}{m['mrr_at10']:>8.1%}"
              f"{mn['recall_at5']:>13.1%}  首查{lat:.0f}ms")
    print("\n验收线（原案例）：问题召回片段准确率 ≥ 80%。"
          "词表归一化把口语查询与书面经验卡对齐后达标；"
          "这也对应案例8的结论——检索质量的第一杠杆是把'不同叫法对上号'。")


if __name__ == "__main__":
    main()
