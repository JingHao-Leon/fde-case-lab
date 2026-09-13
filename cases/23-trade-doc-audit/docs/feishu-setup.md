# 飞书应用配置指南（企业自建应用）

> 目标：拿到 `App ID` + `App Secret`，让 bot 通过 **WebSocket 长连接**收发消息（无需公网 IP / 域名 / 备案）。

## 1. 创建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app) → **创建企业自建应用**，名称随意（如"单据审查助手"）。
2. 进入应用 → 左侧 **凭证与基础信息**，记录 `App ID` 和 `App Secret`。

## 2. 开启机器人能力

左侧 **应用能力 → 添加应用能力** → 选择 **机器人**。

## 3. 事件订阅（长连接方式）

1. 左侧 **事件与回调** → 订阅方式选择 **使用长连接接收事件**（不要选 webhook，无需公网地址）。
2. **添加事件**：`接收消息 im.message.receive_v1`。

## 4. 开通权限

左侧 **权限管理**，搜索并开通：

| 权限 | 用途 |
|---|---|
| `im:message`（获取与发送单聊、群组消息） | 收发消息、回复审查报告 |
| `im:message:send_as_bot` | 以机器人身份发消息 |
| `im:message.group_at_msg:readonly` | 群聊 @ 机器人时接收（群聊用） |
| `im:message.p2p_msg:readonly` | 私聊消息 |
| `im:resource`（读取与上传图片/文件资源） | **下载用户发送的出货单/报关单文件（必需）** |

## 5. 发布版本

**版本管理与发布** → 创建版本 → 提交发布（企业自建应用一般管理员自动通过）。

## 6. 启动 bot

```bash
bash scripts/setup_bridge.sh          # 安装 pi-feishu-lark 并应用二进制附件补丁

FEISHU_APP_ID=cli_xxx \
FEISHU_APP_SECRET=xxx \
pi                                     # 在本仓库根目录启动
```

pi 启动后执行 `/feishu start`（首次会引导校验 App ID/Secret）。看到连接成功后，在飞书里找到机器人发消息即可。

常用命令（pi 内）：

- `/feishu status` 查看连接状态
- `/feishu autostart` 开机自动连接
- 群聊默认需要 @机器人；私聊直接说话

## 常见问题

| 现象 | 处理 |
|---|---|
| 发文件后 bot 说"文件类型不支持" | 补丁未应用，重跑 `scripts/setup_bridge.sh`，然后 `/feishu restart` |
| bot 不回群消息 | 确认群聊里 @ 了机器人；或确认开通了 `group_at_msg` 权限 |
| 事件收不到 | 应用未发布版本；或事件订阅没选"长连接"方式 |
| 发消息没权限 | 检查 `im:message` 系列权限并重新发布版本 |
| 模型没配 | 在 pi 里 `/model` 选择已登录的模型（首次运行 `pi` 会引导登录） |
