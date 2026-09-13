"""PDF 抽取（报关单/装箱单 PDF）：输出文本页与表格网格，供 agent 按 schema 抽取。

文本型 PDF 可直接抽取；扫描件/照片无文本层，此处会返回空文本并在
notes 里提示 agent 改用视觉（图片输入）识别。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:  # CI 最小依赖环境（仅 openpyxl）下保持可导入，调用时再报错
    pdfplumber = None


def parse(path: str | Path, max_pages: int = 10) -> dict[str, Any]:
    path = Path(path)
    pages_text: list[str] = []
    tables: list[list[list[str]]] = []
    notes: list[str] = []

    if pdfplumber is None:
        raise RuntimeError(
            "未安装 pdfplumber（pip install pdfplumber）；"
            "或改用图片方式由模型视觉识别后按 schema 抽取。"
        )

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:max_pages]:
            text = page.extract_text() or ""
            pages_text.append(text)
            for tb in page.extract_tables():
                clean = [[(c or "").strip() for c in row] for row in tb]
                tables.append(clean)

    joined = "".join(pages_text).strip()
    if not joined:
        notes.append("PDF 无文本层（扫描件或照片导出）。请将文件页转成图片由模型视觉识别后按 schema 填写。")

    return {
        "source_file": path.name,
        "kind": "unknown_pdf",
        "pages_text": pages_text,
        "tables": tables[:50],
        "notes": notes,
    }
