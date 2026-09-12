"""NO.8 物料搜索求解器：归一化 + 字符 n-gram 检索，三档方案。

对应 NO.8 的落地 = "数据清洗标准化 + 语义检索"两件事：

- normalize()        归一化：全半角统一、单位后缀剥离、旧编码前缀剥离、
                     别名映射（圆柱头螺钉↔内六角螺栓）。这是 FDE 的真实工作量。
- KeywordSearch      关键词包含匹配（老 ERP 的搜索体验基线）。
- NormalizedTfidf    归一化 + TF-IDF(char 2-4 gram) 余弦。
- FuzzyHybrid        归一化 + BM25(char-bigram) 0.5 + TF-IDF 0.5 融合。

两个业务任务：
- 口语查询命中（搜索）：Top1 / Top5 命中唯一物料 gid；
- 重复录入拦截（主数据）：新记录检索已库，Top1 与记录同为 gid 且相似度
  超阈值 → 拦截。报告拦截率与误拦率。
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ALIAS = {"圆柱头螺钉": "内六角螺栓", "螺帽": "六角螺母", "O形密封圈": "O型圈",
         "向心球轴承": "深沟球轴承", "端铣刀": "立铣刀", "GL-5": "齿轮油"}
OLD_CODE_RE = re.compile(r"^\[[a-z0-9]+-\d+\]")
UNIT_RE = re.compile(r"(mm|条|\(旧\)|旧)$")
PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+")
FILLER = ["上次用的那个", "上次那个", "用的那个", "领一个", "领个", "上次", "里",
          "多大", "用的", "一个", "那个", "的"]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).strip().lower()
    t = t.replace("×", "x")
    while UNIT_RE.search(t):
        t = UNIT_RE.sub("", t.strip())
    t = OLD_CODE_RE.sub("", t)
    for f in FILLER:
        t = t.replace(f, "")
    t = PUNCT_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for alias, canon in ALIAS.items():
        t = t.replace(alias, canon)
    return t


def _doc(r: dict) -> str:
    return normalize(f"{r['name']} {r['spec']} {r['brand']}")


def _bigrams(s: str) -> list[str]:
    return [s[i:i + 2] for i in range(len(s) - 1)] or [s]


class KeywordSearch:
    """老 ERP 式关键词匹配：要求查询词是记录名的包含子串。"""

    def __init__(self, records: list[dict]):
        self.recs = [(r["gid"], r["name"]) for r in records]

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        q = query.strip()
        hits = [(gid, 1.0 if q in name else 0.5) for gid, name in self.recs if q in name]
        if not hits:  # 退化为字符重合
            qs = set(q)
            hits = [(gid, len(qs & set(name)) / len(qs)) for gid, name in self.recs]
        hits.sort(key=lambda x: -x[1])
        return hits[:k]


class NormalizedTfidf:
    def __init__(self, records: list[dict]):
        self.ids = [r["gid"] for r in records]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.mat = self.vec.fit_transform([_doc(r) for r in records])

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        q = self.vec.transform([normalize(query)])
        sims = (self.mat @ q.T).toarray().ravel()
        top = np.argsort(-sims)[:k]
        return [(self.ids[i], float(sims[i])) for i in top]


class FuzzyHybrid:
    def __init__(self, records: list[dict]):
        self.ids = [r["gid"] for r in records]
        self.meta = {r["gid"]: r for r in records}
        # 归一化精确键：清洗标准化后的 (名称, 规格, 品牌) —— 查重的第一道闸
        self.key_index = {
            (normalize(r["name"]), normalize(r["spec"]), r.get("brand")): r["gid"]
            for r in records}
        docs = [_bigrams(_doc(r)) for r in records]
        self.tf = [Counter(d) for d in docs]
        self.dl = np.array([len(d) for d in docs])
        self.avgdl = self.dl.mean()
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: np.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.k1, self.b = 1.5, 0.75
        self.tfidf = NormalizedTfidf(records)

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        qd = Counter(_bigrams(normalize(query)))
        bm = np.zeros(len(self.ids))
        for t, qn in qd.items():
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t, 0)
                if f:
                    bm[i] += idf * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl))
        t = dict(self.tfidf.search(query, k=50))
        bmax = bm.max() or 1.0
        tmax = max(t.values(), default=1.0) or 1.0
        fused = {gid: 0.5 * v / tmax + 0.5 * bmv / bmax
                 for gid, bmv, v in ((gid, bm[i], t.get(gid, 0.0))
                                     for i, gid in enumerate(self.ids))}
        top = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return top

    def is_duplicate(self, record: dict, threshold: float = 0.75,
                     exclude_gid: str | None = None) -> str:
        """重复录入三态判定：

        - "exact"   归一化键（清洗后的 名称+规格+品牌）完全一致 → 自动拦截；
        - "suspect" 模糊高分同品牌同规格（OCR 形近字变体）→ 送人工确认；
        - "new"     放行。

        设计原则：自动拦截必须零误报，拿不准的进人工队列——这正是
        Human-in-the-loop 在主数据治理里的落点。
        """
        key = (normalize(record["name"]), normalize(record["spec"]), record.get("brand"))
        gid0 = self.key_index.get(key)
        if gid0 is not None and gid0 != exclude_gid:
            return "exact"
        hits = self.search(f"{record['name']} {record['spec']} {record['brand']}", k=5)
        spec_canon = normalize(record["spec"])
        for gid, score in hits:
            if gid == exclude_gid or score < threshold:
                continue
            m = self.meta[gid]
            if (m.get("brand") == record.get("brand") and m.get("cat") == record.get("cat")
                    and normalize(m["spec"]) == spec_canon):
                return "suspect"
        return "new"
