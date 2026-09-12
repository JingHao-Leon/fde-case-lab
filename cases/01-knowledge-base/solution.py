"""NO.1 知识库检索求解器：关键词基线 / TF-IDF / BM25+TF-IDF混合+MMR。

对应 NO.1 案例的验收指标「问题召回片段准确率 ≥ 80%」：
- KeywordSearch   字面最长公共子串占比打分（对应用户随手做的"关键词搜索"）
- TfidfSearch     字符 n-gram TF-IDF + 余弦（中文免分词的标准做法）
- HybridSearch    BM25(char-bigram) × 0.5 + TF-IDF × 0.5 融合，
                  可选 MMR 多样性重排（λ=0.7），兼顾相关性与去冗余。

统一接口 `search(query, k) -> list[(card_id, score)]`，评测器通用。
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def char_bigrams(s: str) -> list[str]:
    s = "".join(s.split())
    return [s[i : i + 2] for i in range(len(s) - 1)] or [s]


class GlossaryNormalizer:
    """领域词表归一化：把口语别名/叫法映射到书面对称谓。

    对应原案例中 FDE 的实打实工作——"把同一个物料/工艺的不同叫法对上号"。
    检索质量的第一杠杆不是换模型，而是把词汇对齐（query 与 doc 同侧归一化）。
    """

    def __init__(self, alias_to_canon: dict[str, str]):
        self.pairs = sorted(alias_to_canon.items(), key=lambda kv: -len(kv[0]))

    def normalize(self, text: str) -> str:
        for alias, canon in self.pairs:
            text = text.replace(alias, canon)
        return text

    def normalize_corpus(self, cards: list[dict]) -> list[dict]:
        return [{**c, "text": self.normalize(c["text"])} for c in cards]


class KeywordSearch:
    def __init__(self, cards: list[dict]):
        self.docs = [(c["id"], set(c["text"])) for c in cards]

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        qs = set(query)
        scored = [(cid, len(qs & ds) / max(1, len(qs))) for cid, ds in self.docs]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]


class TfidfSearch:
    def __init__(self, cards: list[dict]):
        self.ids = [c["id"] for c in cards]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.mat = self.vec.fit_transform([c["text"] for c in cards])

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        q = self.vec.transform([query])
        sims = (self.mat @ q.T).toarray().ravel()
        top = np.argsort(-sims)[:k]
        return [(self.ids[i], float(sims[i])) for i in top]


class BM25:
    def __init__(self, cards: list[dict], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids = [c["id"] for c in cards]
        docs = [char_bigrams(c["text"]) for c in cards]
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / self.N
        self.tf = [Counter(d) for d in docs]
        self.dl = [len(d) for d in docs]
        df = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        q = Counter(char_bigrams(query))
        scores = np.zeros(self.N)
        for t, qn in q.items():
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in range(self.N):
                f = self.tf[i].get(t, 0)
                if f:
                    scores[i] += idf * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl))
        top = np.argsort(-scores)[:k]
        return [(self.ids[i], float(scores[i])) for i in top]


class HybridSearch:
    """词表归一化 + BM25/TF-IDF 凸组合 + 可选 MMR 去冗余重排。"""

    def __init__(self, cards: list[dict], alpha: float = 0.5, use_mmr: bool = True,
                 mmr_lambda: float = 0.7, normalizer: GlossaryNormalizer | None = None):
        if normalizer is not None:
            cards = normalizer.normalize_corpus(cards)
        self.normalizer = normalizer
        self.bm25 = BM25(cards)
        self.tfidf = TfidfSearch(cards)
        self.card_by_id = {c["id"]: c["text"] for c in cards}
        self.alpha = alpha
        self.use_mmr = use_mmr
        self.mmr_lambda = mmr_lambda
        self._tfidf_mat = self.tfidf.mat
        self._id2row = {cid: i for i, cid in enumerate(self.tfidf.ids)}

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        if self.normalizer is not None:
            query = self.normalizer.normalize(query)
        b = dict(self.bm25.search(query, k=50))
        t = dict(self.tfidf.search(query, k=50))
        bmax, tmax = max(b.values(), default=1.0), max(t.values(), default=1.0)
        bmax, tmax = bmax or 1.0, tmax or 1.0  # 全零得分时退化为纯另一路
        cands = set(b) | set(t)
        fused = {cid: self.alpha * b.get(cid, 0) / bmax + (1 - self.alpha) * t.get(cid, 0) / tmax
                 for cid in cands}
        ranked = sorted(fused.items(), key=lambda x: -x[1])
        if not self.use_mmr:
            return ranked[:k]
        return self._mmr(ranked, k)

    def _mmr(self, ranked: list[tuple[str, float]], k: int) -> list[tuple[str, float]]:
        picked: list[str] = []
        scores: list[float] = []
        cand = [cid for cid, _ in ranked[:40]]
        while cand and len(picked) < k:
            best, best_val = None, -1e9
            for cid in cand:
                rel = dict(ranked)[cid]
                div = 0.0
                if picked:
                    p = self._tfidf_mat[[self._id2row[cid]]]
                    M = self._tfidf_mat[[self._id2row[p_] for p_ in picked]]
                    div = float((p @ M.T).max())
                val = self.mmr_lambda * rel - (1 - self.mmr_lambda) * div
                if val > best_val:
                    best, best_val = cid, val
            picked.append(best)
            scores.append(dict(ranked)[best])
            cand.remove(best)
        return list(zip(picked, scores))


def evaluate(searcher, queries: list[dict], k: int = 5) -> dict:
    hits = mrr = top1 = 0
    for q in queries:
        res = searcher.search(q["q"], k=10)
        ids = [cid for cid, _ in res]
        if q["gold"] in ids[:k]:
            hits += 1
        if ids and ids[0] == q["gold"]:
            top1 += 1
        for rank, cid in enumerate(ids, 1):
            if cid == q["gold"]:
                mrr += 1 / rank
                break
    n = len(queries)
    return {"recall_at5": hits / n, "top1": top1 / n, "mrr_at10": mrr / n}
