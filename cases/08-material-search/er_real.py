"""NO.8 真实数据装载与评测：Amazon-Google 商品标题实体匹配基准。

数据来源：Magellan / DeepMatcher 实体匹配基准（Amazon vs Google Products，
结构化商品表 + 人工标注匹配对，研究用途）。训练 6,874 对（正样本 699）、
测试 2,293 对（正样本 234）——真实脏标题：缩写、标点、词序、单位差异。

把 ERP 物料搜索的同一套内核（normalize 归一化 + 字符 n-gram TF-IDF 检索）
放到真实标注数据上检验：
- 检索式匹配：tableA 每个商品在 tableB 中检索 Top1，命中标注对应为正确；
- 成对分类：相似度 ≥ 阈值判匹配（阈值在 train 上调优）→ F1。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from solution import normalize

DATA_DIR = Path(__file__).parent.parent.parent / "datasets" / "amazon_google"


def _doc_title(row) -> str:
    t = str(row.get("title", ""))
    m = str(row.get("manufacturer", "")) if pd.notna(row.get("manufacturer")) else ""
    return normalize(f"{t} {m}") if m else normalize(t)


def load() -> dict:
    A = pd.read_csv(DATA_DIR / "tableA.csv")
    B = pd.read_csv(DATA_DIR / "tableB.csv")
    train = pd.read_csv(DATA_DIR / "train.csv")
    test = pd.read_csv(DATA_DIR / "test.csv")
    b_docs = {r["id"]: _doc_title(r) for _, r in B.iterrows()}
    a_docs = {r["id"]: _doc_title(r) for _, r in A.iterrows()}
    return {"A": a_docs, "B": b_docs, "train": train, "test": test}


def build_matcher(b_docs: dict[str, str]):
    from sklearn.feature_extraction.text import TfidfVectorizer

    ids = list(b_docs)
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    mat = vec.fit_transform([b_docs[i] for i in ids])
    return ids, vec, mat


def top1_match(query: str, ids: list[str], vec, mat) -> tuple[str, float]:
    q = vec.transform([normalize(query)])
    sims = (mat @ q.T).toarray().ravel()
    i = int(sims.argmax())
    return ids[i], float(sims[i])


def evaluate(pairs: pd.DataFrame, a_docs: dict, ids: list[str], vec, mat,
             margin: float = 0.05) -> dict:
    """检索即匹配：A 商品在 B 库中检索 Top1，Top1 命中标注对应 → 判匹配。

    召回口径（match 检索）：对标注为匹配的对，Top1 是否恰好是标注对应商品。
    绝对相似度在真实同域标题间不具区分度（全都很高），因此用 Top1 命中而非
    阈值判定——这也是主数据查重"归一化键优先、模糊分数只做候选"的原因。
    """
    tp = fp = fn = top1_hit = top1_total = 0
    for _, p in pairs.iterrows():
        gid, s = top1_match(a_docs[p["ltable_id"]], ids, vec, mat)
        match = gid == p["rtable_id"] and s >= margin
        pred = 1 if match else 0
        tp += pred == 1 and p["label"] == 1
        fp += pred == 1 and p["label"] == 0
        fn += pred == 0 and p["label"] == 1
        if p["label"] == 1:
            top1_total += 1
            top1_hit += gid == p["rtable_id"]
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {"f1": f1, "precision": precision, "recall": recall,
            "top1_acc": top1_hit / max(1, top1_total)}
