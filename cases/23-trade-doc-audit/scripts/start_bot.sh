#!/usr/bin/env bash
# 以 RPC 常驻模式启动外贸单据审查 bot（飞书长连接 + DeepSeek）。
# 前置：bash scripts/setup_bridge.sh 已执行；模型凭证已在 ~/.pi/agent/auth.json。
#
# 用法：
#   bash scripts/start_bot.sh          # 前台运行（Ctrl+C 停止）
#   nohup ... &                        # 或自行放后台
#   bash scripts/stop_bot.sh           # 见下方注释（pkill -f "pi --mode rpc"）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IN="/tmp/pi-rpc-in"
OUT="/tmp/pi-rpc-out.log"

command -v pi >/dev/null 2>&1 || { echo "未找到 pi CLI"; exit 1; }
pgrep -f "pi --mode rpc" >/dev/null && { echo "bot 已在运行（pid $(pgrep -f 'pi --mode rpc' | head -1)）"; exit 0; }

rm -f "$IN" "$OUT"
mkfifo "$IN"

echo "启动 bot（模型: DeepSeek，通道: 飞书长连接）。停止: pkill -f 'pi --mode rpc'"
echo "状态输出: $OUT ；在飞书里找「单据审查助手」发单据即可。"
tail -f /dev/null | pi --mode rpc --provider deepseek --no-session \
  > "$OUT" 2>&1
