"""NO.16 电信网络数据分析：生成基站 KPI/告警数据并植入故障事件。

场景来自《Datawhale FDE 案例 100》NO.16：美国头部电信运营商，分析师人工写 SQL
回答"哪个基站坏了/影响多大"，按天计；客户自建的"提示词 Agent"答案不稳定。
本生成器：50 基站 × 7 天 × 24 小时 KPI（接通率/掉线率/流量），并在基站 S17
植入 6 小时故障事件（掉线率飙升 + 告警 + 流量迁移），供"哪个基站故障、影响
多大、根因是什么"类问题做确定性评测。
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

import numpy as np

N_SITES = 50
N_DAYS = 7
FAULT_SITE = "S17"
FAULT_START, FAULT_HOURS = 96, 6  # 第 5 天 0 点起 6 小时


def build_db(path: Path) -> sqlite3.Connection:
    rng = random.Random(20260913)
    npr = np.random.default_rng(42)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE sites(site_id TEXT PRIMARY KEY, city TEXT, users INT);
        CREATE TABLE kpi(site_id TEXT, day INT, hour INT, drop_rate REAL,
                         setup_rate REAL, traffic_gb REAL);
        CREATE TABLE alarms(site_id TEXT, day INT, hour INT, alarm_type TEXT);
        """
    )
    cities = ["杭州", "宁波", "温州", "绍兴", "嘉兴"]
    sites = [(f"S{i:02d}", cities[i % len(cities)], rng.randint(2, 30) * 1000)
             for i in range(N_SITES)]
    cur.executemany("INSERT INTO sites VALUES(?,?,?)", sites)

    kpi, alarms = [], []
    for sid, _, users in sites:
        base_drop = rng.uniform(0.002, 0.02)
        base_setup = rng.uniform(0.985, 0.999)
        base_traffic = users / 1000 * rng.uniform(0.8, 1.2)
        for d in range(N_DAYS):
            for h in range(24):
                idx = d * 24 + h
                drop = max(0.0005, npr.normal(base_drop, base_drop * 0.25))
                setup = min(1.0, npr.normal(base_setup, 0.002))
                busy = 1.6 if 19 <= h <= 22 else (0.5 if h <= 6 else 1.0)
                traffic = base_traffic * busy * float(npr.uniform(0.9, 1.1))
                if idx >= FAULT_START and idx < FAULT_START + FAULT_HOURS and sid == FAULT_SITE:
                    drop = rng.uniform(0.28, 0.45)   # 掉线率飙升
                    setup = rng.uniform(0.80, 0.90)  # 接通率恶化
                    traffic *= 0.35                  # 用户流量迁移
                    if rng.random() < 0.8:
                        alarms.append((sid, d, h, rng.choice(["传输中断", "板卡告警"])))
                elif rng.random() < 0.001:
                    alarms.append((sid, d, h, "电源告警"))
                kpi.append((sid, d, h, round(drop, 5), round(setup, 5), round(traffic, 2)))
    cur.executemany("INSERT INTO kpi VALUES(?,?,?,?,?,?)", kpi)
    cur.executemany("INSERT INTO alarms VALUES(?,?,?,?)", alarms)
    conn.commit()
    return conn


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    conn = build_db(out / "network.db")
    n = conn.execute("SELECT COUNT(*), (SELECT COUNT(*) FROM alarms) FROM kpi").fetchone()
    print(f"network.db：KPI {n[0]} 行，告警 {n[1]} 条，故障站 {FAULT_SITE} "
          f"(第{FAULT_START//24+1}天起 {FAULT_HOURS} 小时)")


if __name__ == "__main__":
    main()
