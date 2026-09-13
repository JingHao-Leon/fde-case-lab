"""NO.22 真实数据装载：UCI Online Retail（英国电商真实流水）→ SKU×日需求矩阵。

数据来源：UCI Machine Learning Repository - Online Retail (ID 352, CC BY 4.0)
Chen, Sain, Guo (2012)，541,909 笔真实交易（2010-12-01 ~ 2011-12-09）。

清洗口径（保证补货回测的业务语义成立）：
- 剔除取消单（Quantity<=0）与无单价/超高价长尾（UnitPrice<=0 或 >300）；
- 取交易量 Top 200 的 SKU；
- 日历窗：数据最后 240 天（含 2011 年 12 月旺季尖峰）；
- 缺失日需求记 0（真实零售的间歇性需求，比泊松合成更难）。
输出：与 solution.run_all 同构的 (demand, price, lead, budget) 矩阵。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_XLSX = Path(__file__).parent / "data" / "raw" / "Online Retail.xlsx"
PROCESSED = Path(__file__).parent / "retail_daily.csv"  # 提交进 git，保证离线可复现
N_SKU = 200
N_DAYS = 240


def build_from_xlsx(xlsx: Path = RAW_XLSX, out: Path = PROCESSED) -> pd.DataFrame:
    df = pd.read_excel(xlsx)
    df = df[(df.Quantity > 0) & (df.UnitPrice > 0) & (df.UnitPrice <= 300)]
    df["day"] = df.InvoiceDate.dt.date
    sku_qty = df.groupby("StockCode").Quantity.sum().sort_values(ascending=False)
    top = sku_qty.head(N_SKU).index
    df = df[df.StockCode.isin(top)]
    daily = df.groupby(["StockCode", "day"]).Quantity.sum().unstack(fill_value=0)
    # 对齐到统一日历的最后 240 天
    all_days = sorted(daily.columns)[-N_DAYS:]
    daily = daily.reindex(columns=all_days, fill_value=0).head(N_SKU)
    price = df.groupby("StockCode").UnitPrice.median().reindex(daily.index)
    daily.columns = [str(c) for c in daily.columns]
    daily.insert(0, "unit_price", price.round(2).values)
    out.parent.mkdir(exist_ok=True)
    daily.to_csv(out)
    return daily


def load() -> dict:
    """优先读已提交的真实数据 CSV；不存在时才回退合成数据。"""
    if PROCESSED.exists():
        daily = pd.read_csv(PROCESSED, index_col=0)
        return {
            "source": "UCI Online Retail (real)",
            "demand": daily.values.astype(int).tolist(),
            "prices": daily.unit_price.tolist(),
            "skus": daily.index.tolist(),
            "days": daily.columns[1:].tolist(),
        }
    from data_gen import gen_demand
    d = gen_demand()
    return {"source": "synthetic (fallback)", "demand": d["demand"],
            "prices": d["unit_price"], "skus": None,
            "days": [str(i) for i in range(len(d["demand"][0]))]}


if __name__ == "__main__":
    if RAW_XLSX.exists():
        daily = build_from_xlsx()
        print(f"已从真实流水构建：{daily.shape[0]} SKU × {daily.shape[1]-1} 天 "
              f"→ {PROCESSED}")
    else:
        print("未找到原始 xlsx；run 时可直接使用已提交的 retail_daily.csv")
