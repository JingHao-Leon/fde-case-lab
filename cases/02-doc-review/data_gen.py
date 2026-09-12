"""NO.2 车管所网办材料审核：生成办件与材料缺陷合成数据。

场景来自《Datawhale FDE 案例 100》NO.2：群众在线提交身份证、合同、发票、
营业执照等图片材料，人工逐张审核+录入，单件约 15 分钟，日均 700~800 件；
AI 化后单件 3~5 分钟、日均约 1100 件，材料识别率从 70% 磨到 98%。

本生成器产出 2,000 个办件（6 类业务 × 必需材料集 × 字段），按比例植入五类
真实问题：字段缺失、证号校验位错误、跨材料姓名不一致、金额不一致、日期过期，
并对约 9% 的字段标注低 OCR 置信度（模拟"拍摄质量五花八门"）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

BUSINESSES = {
    "抵押登记": ["身份证", "抵押合同", "营业执照", "发票"],
    "转移登记": ["身份证", "购车发票", "登记证书"],
    "变更登记": ["身份证", "营业执照", "变更证明"],
    "补领证书": ["身份证", "申请表"],
    "注销抵押": ["身份证", "抵押合同", "还款证明"],
    "申领号牌": ["身份证", "购车发票", "交强险保单"],
}
ID_WEIGHTS = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
CHECK_CODES = "10X98765432"


def _gen_id(rng: random.Random, broken: bool = False) -> str:
    body = f"33010{rng.randint(0, 9)}{rng.randint(1970, 2005):04d}" \
           f"{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}{rng.randint(100, 999):03d}"
    c = CHECK_CODES[sum(int(a) * b for a, b in zip(body, ID_WEIGHTS)) % 11]
    full = body + c
    if broken:  # 篡改一位数字，破坏校验位（避开末位校验码可能是 X）
        i = rng.randrange(2, 17)
        full = full[:i] + str((int(full[i]) + 1) % 10) + full[i + 1:]
    return full


def _mk_field_ok(rng: random.Random, kind: str) -> dict:
    if kind == "身份证":
        return {"name": rng.choice(["王建国", "李芳", "张伟", "刘洋", "陈静"]),
                "id_number": _gen_id(rng), "conf": 0.99}
    if kind in ("抵押合同", "购车发票"):  # 成交类材料：金额须与发票/合同一致
        return {"party": rng.choice(["王建国", "李芳", "张伟", "刘洋", "陈静"]),
                "amount": 0.0, "deal": True, "conf": 0.97}
    if kind == "营业执照":
        return {"company": rng.choice(["杭州XX汽车服务", "浙XX融资租赁", "宁波XX商贸"]),
                "uscc": _gen_id(rng).upper(), "conf": 0.95}
    if kind == "发票":
        return {"date": f"202{rng.randint(4, 6)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "amount": 0.0, "deal": True, "conf": 0.96}
    if kind in ("交强险保单", "还款证明"):  # 非成交类：金额语义不同，不参与一致性比对
        return {"date": f"202{rng.randint(4, 6)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "amount": round(rng.uniform(1000, 9000), 2), "conf": 0.96}
    return {"date": f"202{rng.randint(4, 6)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "conf": 0.96}


REQUIRED_FIELDS = {
    "身份证": ["name", "id_number"],
    "抵押合同": ["party", "amount"],
    "购车发票": ["party", "amount"],
    "发票": ["date", "amount"],
    "营业执照": ["company", "uscc"],
    "交强险保单": ["date"],
    "还款证明": ["date"],
    "登记证书": ["date"],
    "变更证明": ["date"],
    "申请表": ["date"],
}


def gen_cases(seed: int = 20260913, n: int = 2000) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    names = ["王建国", "李芳", "张伟", "刘洋", "陈静"]
    for i in range(n):
        biz = rng.choice(list(BUSINESSES))
        docs = {}
        defects = set()
        person = rng.choice(names)
        base_amount = round(rng.uniform(5, 30) * 10000, 2)
        for kind in BUSINESSES[biz]:
            f = _mk_field_ok(rng, kind)
            # 让成交类材料共享同一成交金额、当事人引用同一人，构造"一致性"背景
            if f.get("deal"):
                f["amount"] = base_amount
            if "party" in f:
                f["party"] = person
            if "name" in f:
                f["name"] = person
            docs[kind] = f
        # 植入缺陷（约 20% 办件有问题，可叠加）
        if rng.random() < 0.06 and "身份证" in docs:
            docs["身份证"]["id_number"] = _gen_id(rng, broken=True)
            defects.add("证号校验位错误")
        if rng.random() < 0.06 and ("抵押合同" in docs or "购车发票" in docs):
            docs["身份证"]["name"] = rng.choice([x for x in names if x != person])
            defects.add("跨材料姓名不一致")
        if rng.random() < 0.07:
            deal_docs = [x for x, d in docs.items() if d.get("deal")]
            if len(deal_docs) >= 2:  # 至少两张成交材料才有"不一致"可言
                k = rng.choice(deal_docs)
                docs[k]["amount"] = round(base_amount * rng.uniform(0.5, 0.9), 2)
                defects.add("跨材料金额不一致")
        if rng.random() < 0.05:
            k = rng.choice(list(docs))
            fields = [f for f in REQUIRED_FIELDS.get(k, []) if f in docs[k]]
            if fields:  # 必弹真实必填字段，避免"缺陷"实际没发生
                docs[k].pop(rng.choice(fields))
                defects.add("必填字段缺失")
        if rng.random() < 0.05:
            k = rng.choice([x for x in docs if "date" in docs[x]] or [None])
            if k:
                docs[k]["date"] = "2021-01-01"
                docs[k]["expired"] = True
                defects.add("材料过期")
        # 低置信字段（拍摄质量差）
        for k in docs:
            if rng.random() < 0.09:
                docs[k]["conf"] = rng.uniform(0.5, 0.85)
        cases.append({"case_id": f"C{i:05d}", "biz": biz, "docs": docs,
                      "defects": sorted(defects)})
    return cases


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    cases = gen_cases()
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    n_bad = sum(1 for c in cases if c["defects"])
    print(f"生成 {len(cases)} 个办件，其中 {n_bad} 个带缺陷 -> {out/'cases.json'}")


if __name__ == "__main__":
    main()
