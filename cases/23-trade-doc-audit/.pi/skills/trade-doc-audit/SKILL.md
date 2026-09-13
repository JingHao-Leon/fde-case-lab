---
name: trade-doc-audit
description: 外贸单据审查——对出货单/装箱单（Excel/PDF/图片）与出口报关单做结构性审查与内容对齐审查，输出飞书友好的审查报告。当用户发来出货单、报关单、装箱单、invoice、packing list 或要求"审单/对单/核对报关单"时使用。
---

# 外贸单据审查（出货单 ↔ 出口报关单）

对"出货单（装箱单/商业发票）"与"中国海关出口货物报关单"做两层审查：

1. **结构审查**：单据自身字段完整性、格式与算术自洽（确定性规则，绝对可靠）
2. **对齐审查**：两单之间的数量/金额/毛净重/件数/收发货人/目的港一致性

**核心原则：所有数字判断由 `engine/audit_cli.py` 确定性完成，你（LLM）只负责"把原始单据抽取成标准 JSON"和"向用户解释结果"。绝不心算核对金额或数量。**

## 工作流程

### 第 1 步：确认材料

- 用户发了文件附件：附件已在本地（消息里会给 `本地路径`；文本文件则直接内嵌内容）。
- 只收到一份单据：对该单做 parse + 抽取后，把 S1 必填清单当 checklist 完成结构审查，并提示用户补发另一份以完成对齐审查。
- 图片附件（报关单拍照）：直接用视觉读图，按 schema 抽取。
- 两个文件都拿到后进入第 2 步。分不清哪个是出货单/报关单时，先 parse 看内容再判断。

### 第 2 步：解析原始单据

工作目录固定为本仓库根目录（`engine/audit_cli.py` 所在处）。解释器用 `ai-projects/.venv/bin/python`（若无则 `python3`，需 openpyxl+pdfplumber）。

```bash
ai-projects/.venv/bin/python engine/audit_cli.py parse <出货单文件> -o work/packing_raw.json
ai-projects/.venv/bin/python engine/audit_cli.py parse <报关单文件> -o work/declaration_raw.json
```

读输出 JSON：`grid`/`pages_text`/`tables` 是原文；`hints` 是解析器已归一化的字段（Excel 出货单通常 80% 字段可直接用）；`notes` 是解析器给你的提示。

PDF 无文本层（扫描件）时：让用户补发清晰照片/截图（图片走视觉），或对 PDF 每页截图后视觉抽取。

### 第 3 步：抽取标准 JSON（LLM 环节）

先看 schema（只在你不确定字段含义时读）：

```bash
ai-projects/.venv/bin/python engine/audit_cli.py schema packing
ai-projects/.venv/bin/python engine/audit_cli.py schema declaration
```

从原文抽取并写出两份标准 JSON（尽量复用 hints，缺的补齐）：

- `work/packing.json` —— `doc_type` 必须为 `packing_list`
- `work/declaration.json` —— `doc_type` 必须为 `export_declaration`

抽取纪律：

- **数字逐位照抄**，不做任何换算；币制用三位代码（USD/EUR/CNY…）
- 出货单 `unit` 保留原文（PCS/CTNS…）；报关单 `unit` 保留申报单位（个/台/千克…）
- 找不到的字段填 `null`（不要编造、不要猜数字）；S1 会把它报为缺失
- 报关单品名用申报的中文品名；出货单品名中文优先（`name`），英文放 `name_en`
- 品名与 HS 编码的对应关系如果单据里明确，务必带上 `hs_code`，能显著提升行匹配质量

### 第 4 步：确定性审查

```bash
ai-projects/.venv/bin/python engine/audit_cli.py audit work/packing.json work/declaration.json -o work/findings.json --report work/report.md
```

退出码 1 = 有 error。读 `work/findings.json`（`verdict`: pass/warn/fail）。

### 第 5 步：复核与答复

1. findings 里 severity=info 的"跨语言无法比对"项（A7 发货人/收货人、A8 目的港）：**由你做语义比对**——如 "Ningbo Chenxi Lighting Import & Export Co., Ltd." vs "宁波晨曦照明进出口有限公司" 是否同一家。比对结论写进回复（"已人工复核一致"或"疑似不一致"）。
2. 你在抽取时发现的可疑点（OCR 模糊、逻辑矛盾但规则没覆盖）主动补充说明。
3. 按 `work/report.md` 的结构向用户输出**完整报告**（飞书消息支持 Markdown 表格）：
   - 先给结论行：`✅ 通过 / ⚠️ 有条件通过 / ❌ 不通过（🔴n 🟡n 🔵n）`
   - 关键值对照表
   - 错误/预警明细表（规则编号、位置、差异值）
   - 你复核 info 项的结论
   - 需要用户补充/确认的事项
4. 语言：中文回复。金额重量保留原始精度，差异用 `+/-` 带方向。

## 常见情形

- **用户只发一份单**：审该单结构（parse 后对照 schema 检查必填——把 S1 的必填清单当 checklist 用），然后提示"请发送另一份单据以完成对齐审查"。
- **文件是 zip/压缩包**：解压到 work/ 后按上述流程处理每个文件。
- **多个品项合并申报**（出货单 5 行 vs 报关单 2 项）：规则引擎已按品名+HS 匹配行，A9 会提示行数差异，属正常，向用户解释即可。
- **CIF/CFR 成交**：A4 金额差异可能是运保费，规则引擎会给 info 提示，请向用户确认申报口径。
- **审查通过**：也要输出关键值对照表，让用户有据可查。
