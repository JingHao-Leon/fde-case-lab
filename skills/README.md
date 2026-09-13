# FDE Skills · 基于 Datawhale FDE 案例 100 的可行技能包

把 24 个真实企业落地案例中反复出现的 FDE 方法论，提炼成 AI 编码代理
（Claude Code / Cursor / Codex 等）可安装的技能。可行性研究全文见
[RESEARCH.md](./RESEARCH.md)（24 案例全量映射 + 五维评分 + 分级结论）。

## 安装

把对应技能目录复制进 agent 的技能目录即可（与
[FDEOps](https://github.com/suboss87/FDEOps) 的安装约定兼容）：

```bash
npx skills add JingHao-Leon/fde-case-lab --skill doc-review   # 若装有 skills CLI
# 或手动：cp -r skills/doc-review ~/.claude/skills/
```

## 技能索引（一级，随附可运行参考实现）

| 技能 | 一句话 | 覆盖案例 | 参考实现 |
|---|---|---|---|
| [fde-discovery](./fde-discovery/SKILL.md) | 把模糊抱怨变成可验证的问题定义 | 02/08/13/20 | —（访谈引导） |
| [kb-build](./kb-build/SKILL.md) | 经验知识库构建 + 80% 验收线 | 01/11 | cases/01 |
| [doc-review](./doc-review/SKILL.md) | 单据审核分流，误放=0 红线 | 02/09/19 | cases/02, 09 |
| [record-link](./record-link/SKILL.md) | 实体归一/查重/对账差异分类 | 08/10 | cases/08, 10 |
| [state-reminder](./state-reminder/SKILL.md) | 履约状态机 SLA 提醒 | 05/13 | cases/05 |
| [recon-chain](./recon-chain/SKILL.md) | 订单链路对账与异常告警 | 20 | cases/20 |
| [cost-quote](./cost-quote/SKILL.md) | 成本模型+校准飞轮报价 | 17/23 | cases/17 |
| [content-pipeline](./content-pipeline/SKILL.md) | 内容量产：生成+校验+回退 | 12/15 | cases/15 |
| [semantic-layer](./semantic-layer/SKILL.md) | 确定性语义层问答 | 16 | cases/16 |
| [timeline-check](./timeline-check/SKILL.md) | 时间线重建+期限检查 | 03 | cases/03 |

## 二级候选（参考实现已有，SKILL.md 暂不发布）

`site-screen`（04 选址筛查）、`load-optimize`（06 3D 装箱）、
`spec-geometry`（21 消防规范生成）、`inventory-ads`（22/24 补货×广告联动）、
`data-audit`（24 效果基线设计）——需人工关键节点多或规范工程量大，
研究结论见 RESEARCH.md 第二节。

## 明确不做成技能的工作

业务陪跑、一把手推动、组织与 KPI 调整（案例 07/14/18 的核心）——
这是 FDE 的人格化职责，Agent 只能做会议纪要与待办跟踪。
