#!/usr/bin/env python3
"""样例单据生成（data_gen）。

生成确定性（固定内容、固定数值）的外贸单据样例：
- 出货单 Excel / 英文装箱单 PDF（可被解析器读取的原始单据）
- 好/坏两套"标准抽取 JSON"（坏样例注入 6 处典型申报错误）
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "samples"))

import make_samples


def main() -> None:
    make_samples.main()
    print(f"样例输出目录：{HERE / 'samples'}")


if __name__ == "__main__":
    main()
