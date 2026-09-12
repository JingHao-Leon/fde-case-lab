#!/usr/bin/env bash
# 依次运行全部案例的回测，输出各案例核心指标
set -e
cd "$(dirname "$0")/.."
for d in cases/*/; do
  if [ -f "$d/bench.py" ]; then
    echo "===== $d ====="
    python "$d/bench.py"
    echo
  fi
done
