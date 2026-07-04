# CommunityOS 部署指南

> **最后更新：** 2026-07-04

---

## 前置条件

| 组件 | 最低版本 | 下载 |
|------|---------|------|
| Python | 3.9+ | https://www.python.org/downloads/ |
| NapCat | 最新版 | https://github.com/NapNeko/NapCatQQ/releases |
| Git | 任意 | https://git-scm.com/downloads |
| QQ 账号 | — | 用于机器人登录 |

---

## 部署步骤

### 1. 安装 Python

下载安装 Python 3.9+，勾选「Add to PATH」。

### 2. 安装 NapCat

按 NapCat 官方文档安装并登录机器人 QQ。推荐使用 Win64 安装包。

### 3. 下载 CommunityOS

```bash
git clone https://github.com/Aphrosyne/CommunityOS.git
cd CommunityOS
```

### 4. 一键安装

双击运行 `bot/setup.bat`，自动完成：
- 创建 Python 虚拟环境
- 安装依赖包
- 复制配置模板（`.env`、`shortcuts.json`、`keywords.json`）

### 5. 编辑配置

打开 `bot/.env`，填写以下必要项：

```ini
OWNER=你的QQ号              # 机器人所有者
ADMINS=管理员QQ号1,管理员2    # Bot 管理员
MANAGED_GROUPS=群号1,群号2    # 受管理的群
FRIEND_VERIFY_ANSWER=你的答案  # 好友验证答案
```

其他配置保持默认即可。

### 6. 配置 NapCat WebSocket

打开 NapCat 设置 → 网络配置 → 新建 **WebSocket 客户端**（不是 WebSocket 服务器）：

- URL：`ws://127.0.0.1:8080/onebot/v11/ws`
- Access Token：`communityos`

注意：URL 和 Token 在 NapCat WebUI 中是分开的两个输入框。

### 7. 启动机器人

双击运行 `bot/start.bat`，或命令行：

```bash
cd bot
venv\Scripts\activate.bat
python main.py
```

看到 `Uvicorn running on http://127.0.0.1:8080` 和 `Bot XXXXXXXX connected` 表示启动成功。

### 8. 测试

在管理群发送 `帮助`（无需 @bot），应收到命令列表。私聊机器人发 `帮助` 同样可用。

---

## 常见问题

**NapCat 无法连接：** 检查 WebSocket 客户端 URL 是否正确，确认 `access_token` 与 `.env` 一致。

**图片发送失败：** 让用户添加机器人为 QQ 好友后再试。

**禁言无效：** 确认机器人在该群有管理员权限。

---

## 更新

```bash
git pull
cd bot
pip install -r requirements.txt
python main.py
```
