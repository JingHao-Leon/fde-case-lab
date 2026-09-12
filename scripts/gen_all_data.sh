#!/usr/bin/env bash
# 生成全部案例的合成数据（固定随机种子，结果可复现）
set -e
cd "$(dirname "$0")/.."
for d in cases/*/; do
  if [ -f "$d/data_gen.py" ]; then
    echo "===== $d ====="
    python "$d/data_gen.py"
  fi
done
