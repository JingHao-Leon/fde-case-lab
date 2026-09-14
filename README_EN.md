# FDE Case Lab (EN)

> 中文完整版：[README.md](README.md)（本文件为英文精简版）

A runnable engineering lab for **Forward Deployed Engineering (FDE)** —
17 case projects distilled from the *Datawhale FDE Case 100* collection
(24 real enterprise AI deployment cases, Sept 2026), each shipped as
**data generator + solver + pytest suite + benchmark script**, plus
**10 installable AI-agent skills** distilled from the same corpus.

[![CI](https://github.com/JingHao-Leon/fde-case-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/JingHao-Leon/fde-case-lab/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-151%20passing-brightgreen)](#quick-start)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![benchmark](docs/benchmark.png)

## Highlights (all reproducible with one command)

| Project | Metric | Result | vs baseline |
|---|---|---|---|
| [01 KB retrieval](../cases/01-knowledge-base) | Recall@5 | **99.2%** (97.1% noisy) | keyword 66.2% |
| [02 document review](../cases/02-doc-review) | accuracy / false-accept | **100% / 0** | 15× human throughput |
| [03 case timeline](../cases/03-case-timeline) | statute-of-limitations agreement | **96.3%** | 1000 pages: days → minutes |
| [04 site screening](cases/04-site-screening) | Top-10 overlap w/ expert | **90%** | 0.5 ms for 200 parcels |
| [05 influencer CRM](cases/05-influencer-crm) | NDCG@10 | **90.3%** | followers-only 0.4%; cycle -34% |
| [06 truck loading](cases/06-truck-loading) | first-truck load | **97.1 m³** | planner: 5 h → seconds |
| [08 material search](cases/08-material-search) | dedup blocking / real-title Top1 | **0 false blocks** / 67.9% | keyword Top1 10% |
| [09 finance audit](cases/09-finance-audit) | issue recall / false-pass | **100% / 0** | 78% auto-pass |
| [10 reconciliation](cases/10-reconciliation) | net-diff restoration error | **-93.8%** | 6.3 s vs 100 min manual |
| [13 maintenance copilot](cases/13-maintenance-copilot) | autofill hit-rate | **77%** | routing 0% → 100% |
| [15 content pipeline](cases/15-content-pipeline) | first-pass usability | **100%** | raw LLM writing 0% |
| [16 semantic-layer agent](cases/16-network-analytics) | routing / stability | **100% / 100%**, 0.3 ms | sampled agent 20% / 0% |
| [17 quoting engine](cases/17-quoting-engine) | quote MAPE | **9.2%** | expert estimate 58.4% |
| [20 ops visibility](cases/20-ops-visibility) | document-level alerts | **29 real-time** | month-end check: 1 |
| [21 fire-safety drawings](cases/21-fire-drawing) | compliance pass-rate | **100%** | habit baseline 60% |
| [22 replenishment × ads](cases/22-replenishment-ads) | total cost (real UCI demand) | **-67.5%** | fill-rate 83.6% |

## Quick start

```bash
pip install numpy scikit-learn pandas pytest
make test    # 151 tests (~40 s)
make bench   # run all benchmarks
```

## Agent skills

10 installable `SKILL.md` files distilled from the same corpus
(`fde-discovery`, `kb-build`, `doc-review`, `record-link`, `state-reminder`,
`recon-chain`, `cost-quote`, `content-pipeline`, `semantic-layer`,
`timeline-check`). Feasibility study: [skills/RESEARCH.md](skills/RESEARCH.md).

## Data

Two projects run on real public data (UCI Online Retail, CC BY 4.0;
Magellan/DeepMatcher Amazon-Google labeled benchmark); the other 14 use
seeded synthetic data mimicking each case's scale and planted defects.
Sources & licenses: [datasets/README.md](datasets/README.md).

## License

MIT.
