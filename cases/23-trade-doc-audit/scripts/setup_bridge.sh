#!/usr/bin/env bash
# 安装并配置飞书桥（pi-feishu-lark 补丁版）。
#
# 本仓库 vendor/ax-feishu-bridge 已内置二进制附件补丁（Excel/PDF 下载落盘、
# 路径注入 prompt），以本地路径方式安装给 pi，不受上游更新影响。
#
# 用法：bash scripts/setup_bridge.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/ax-feishu-bridge"

command -v pi >/dev/null 2>&1 || { echo "未找到 pi CLI，请先安装：npm install -g @earendil-works/pi-coding-agent"; exit 1; }

# 若曾用 npm 源安装过官方版，先移除（避免启动时拉取未打补丁的版本覆盖）
if pi list 2>/dev/null | grep -q "npm:pi-feishu-lark"; then
  echo "==> 移除官方 npm 版（未打补丁）"
  pi remove npm:pi-feishu-lark || true
fi

echo "==> 安装补丁版 ax-feishu-bridge（本地路径）"
pi install "$VENDOR"

echo "==> 校验补丁已生效"
FOUND="$(find "$HOME/.pi" -name "attachments.ts" -path "*feishu*" 2>/dev/null | head -1)"
if [ -n "$FOUND" ] && grep -q "trade-doc-audit patch" "$FOUND"; then
  echo "    OK: $FOUND"
else
  echo "    警告：未在安装目录中找到补丁标记，启动 pi 后请检查扩展加载日志。"
fi

cat <<'EOF'

完成。凭证配置（二选一）：
  A) 写入 ~/.pi/agent/feishu/config.pi.json：
     {"appId": "cli_xxx", "appSecret": "xxx", "autoStart": true}
  B) 启动时用环境变量：FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx pi

启动：在本仓库根目录运行 pi（首次运行按提示登录模型），飞书连接自动建立
（或执行 /feishu start）。然后在飞书里给机器人"单据审查助手"发单据即可。
EOF
