"""pytest 共享夹具：确保样例存在，并把项目根加入 sys.path。"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "samples"))

import make_samples

make_samples.main()  # 幂等：每次运行重新生成样例，保证可复现
