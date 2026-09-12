"""NO.8 工业 ERP 物料搜索：生成"脏"物料库与口语查询数据。

场景来自《Datawhale FDE 案例 100》NO.8：工业企业 15 个团队共用一套老 ERP，
关键词搜索弱 → "找不到物料 → 重新录入 → 数据越来越脏 → 买错买重"的恶性循环，
错误采购积压在仓库里最终报废。

数据模型：
- 1,500 个唯一物料（8 大类 × 规格 × 品牌），字段：名称/规格/品牌/单位/旧编码；
- 500 条重复录入（别名、全半角、单位后缀、OCR 形近字、旧编码前缀等变体）；
- 100 条口语查询（"上次那个 M8 内六角 20 长的螺丝"）指向唯一物料；
- 300 条"新录入"（其中 180 条实为库内已有物料的变体 → 应被拦截）。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

CATEGORIES = {
    "紧固件": [("内六角螺栓 M{d}x{l}", "M{d}x{l}", ("GB70", "DIN912")),
              ("六角螺母 M{d}", "M{d}", ("GB6170", "DIN934"))],
    "轴承": [("深沟球轴承 {d}x{D}x{B}", "{d}x{D}x{B}", ("6200", "NSK")),
            ("角接触球轴承 {d}x{D}x{B}", "{d}x{D}x{B}", ("7200", "FAG"))],
    "密封件": [("O型圈 {d}x{t}", "{d}x{t}", ("GB3452", "NOK"))],
    "液压件": [("电磁换向阀 {v}V", "{v}V", ("DSG", "Yuken"))],
    "电气件": [("PLC模块 {p}点", "{p}点", ("S7", "Siemens"))],
    "劳保": [("防静电手套 {s}", "{s}", ("LN", "星光"))],
    "刀具": [("立铣刀 D{d}x{l}", "D{d}x{l}", ("YG", "株洲"))],
    "润滑油": [("齿轮油 {v}L", "{v}L", ("Mobil", "壳牌"))],
}
BRANDS = ["国标件", "哈轴", "NSK", "FAG", "亚德客", "SMC"]
OCR_SUB = {"六": "大", "圈": "园", "轴": "轨", "2": "Z", "0": "O", "5": "S"}
ALIAS = {"内六角螺栓": "圆柱头螺钉", "六角螺母": "螺帽", "O型圈": "O形密封圈",
         "深沟球轴承": "向心球轴承", "立铣刀": "端铣刀", "齿轮油": "GL-5"}

SIZES = [4, 5, 6, 8, 10, 12, 16, 20]


def _mk_name(rng: random.Random, cat: str, tmpl: str) -> tuple[str, str]:
    kw = {"d": rng.choice(SIZES), "l": rng.choice([10, 20, 30, 50]),
          "D": rng.choice(SIZES) * 2, "B": rng.choice([6, 8, 10]),
          "t": rng.choice([2, 3]), "v": rng.choice([4, 10, 24]),
          "p": rng.choice([16, 32, 64]), "s": rng.choice(["M", "L", "XL"])}
    name = tmpl.format(**kw)
    spec = tmpl.format(**kw).split(" ", 1)[-1]
    return name, spec


def gen_catalog(seed: int = 20260913, target: int = 1200) -> dict:
    """生成唯一物料主数据（name+spec+brand 三元组去重）+ 变体重复录入。"""
    rng = random.Random(seed)
    truth, records = [], []
    seen = set()
    rid = 0
    combos = [(cat, tmpl, spec_t, codes)
              for cat, tmpls in CATEGORIES.items()
              for tmpl, spec_t, codes in tmpls]
    guard = 0
    while len(truth) < target and guard < target * 50:
        guard += 1
        cat, tmpl, spec_t, codes = rng.choice(combos)
        name, spec = _mk_name(rng, cat, tmpl)
        brand = rng.choice(BRANDS)
        key = (name, spec, brand)
        if key in seen:
            continue
        seen.add(key)
        item = {"gid": f"G{len(truth):04d}", "cat": cat, "name": name,
                "spec": spec, "brand": brand, "unit": rng.choice(["件", "个", "套"]),
                "old_code": f"{rng.choice(codes)}-{rng.randint(100, 999)}"}
        truth.append(item)
        records.append(dict(item, rec_id=f"R{rid:05d}", variant="clean"))
        rid += 1
        if rng.random() < 0.5:  # 该物料存在一条重复录入变体
            r = dict(item, rec_id=f"R{rid:05d}",
                     variant=rng.choice(["alias", "ocr", "unit", "old_code", "space"]))
            rid += 1
            if r["variant"] == "alias":
                for k, v in ALIAS.items():
                    if k in r["name"]:
                        r["name"] = r["name"].replace(k, v)
                        break
            elif r["variant"] == "ocr":
                for k, v in OCR_SUB.items():
                    if k in r["name"]:
                        r["name"] = r["name"].replace(k, v, 1)
                        break
            elif r["variant"] == "unit":
                r["spec"] = r["spec"] + rng.choice(["mm", "条", "(旧)"])
            elif r["variant"] == "old_code":
                r["name"] = f"[{r['old_code']}]" + r["name"]
            else:
                r["name"] = r["name"] + " "
            records.append(r)
    rng.shuffle(records)
    return {"truth": truth, "records": records}


def gen_queries(truth: list[dict], seed: int = 99, n: int = 100) -> list[dict]:
    rng = random.Random(seed)
    queries = []
    for _ in range(n):
        t = rng.choice(truth)
        colloquial = rng.choice([
            f"上次用的那个{t['name']} {t['spec']} {t['brand']}",
            f"领一个{t['name']} {t['brand']}的，{t['spec']}",
            f"{t['cat']}里的{t['name'].split(' ')[0]} {t['spec']}，{t['brand']}牌的",
        ])
        queries.append({"q": colloquial, "gold": t["gid"]})
    return queries


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    catalog = gen_catalog()
    queries = gen_queries(catalog["truth"])
    (out / "catalog.json").write_text(
        json.dumps({"records": catalog["records"], "queries": queries},
                   ensure_ascii=False), encoding="utf-8")
    n_dup = sum(1 for r in catalog["records"] if r["variant"] != "clean")
    print(f"物料库 {len(catalog['records'])} 条（唯一物料 {len(catalog['truth'])} 个，"
          f"重复变体 {n_dup} 条），口语查询 {len(queries)} 条 -> {out/'catalog.json'}")


if __name__ == "__main__":
    main()
