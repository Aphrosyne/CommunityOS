# Bot 框架 Bootstrap 记录

> **日期：** 2026-06-28
> **框架：** NoneBot2 + FastAPI + OneBot V11 适配器
> **结果：** ✅ 群内 @机器人，正常回复

---

## 踩坑记录

### 1. `bot/platform/` 与 Python 标准库 `platform` 冲突

**现象：** `AttributeError: module 'platform' has no attribute 'python_implementation'`

**原因：** `bot/platform/` 目录遮蔽了 Python 标准库的 `platform` 模块。

**解决：** 重命名为 `bot/adapters/`。

---

### 2. `nonebot.load_plugins("plugins")` 加载不到插件

**现象：** `已加载插件: []`

**原因：** 相对路径解析失败，NoneBot2 无法从 project_root 找到插件目录。

**解决：** 改用 `nonebot.load_plugin("plugins.greet")` 按模块路径逐个加载。后续插件多了再统一处理。

---

### 3. `from services.config import ...` 找不到模块

**现象：** `ModuleNotFoundError: No module named 'bot'`

**原因：** `bot/` 不在 Python 的 `sys.path` 中，插件无法导入同级的 `services` 包。

**解决：** `main.py` 中加入 `sys.path.insert(0, str(PROJECT_ROOT))`，并创建 `bot/__init__.py` 使其成为 Python 包。

---

### 4. NapCat 反向 WebSocket 配置

**关键理解：**
- NapCat **WebSocket 服务器**（host + port）：NapCat 被动等待连接
- NapCat **WebSocket 客户端**（URL）：NapCat 主动连接外部

FastAPI 驱动下 NoneBot2 是 HTTP 服务器，NapCat 必须以**客户端**身份连接。

**NapCat 配置：** 新建 WebSocket 客户端 → URL 填 `ws://127.0.0.1:8080/onebot/v11/ws`

---

### 5. 403 Forbidden — Access Token

**现象：** NapCat 连接到 `/onebot/v11/ws` 后立即被 403 拒绝。

**解决：**
- `.env` 中设置 `ONEBOT_ACCESS_TOKEN=communityos`
- NapCat WebSocket 客户端 URL 变为 `ws://127.0.0.1:8080/onebot/v11/ws?access_token=communityos`

两边 token 一致后握手通过。

---

### 6. `~fastapi` vs `~httpx` 驱动选择

- `~fastapi`：NoneBot2 启动 HTTP 服务，NapCat 主动连接（选了这个）
- `~httpx`：NoneBot2 主动连接 NapCat 的 WebSocket 服务器

`.env` 中 `DRIVER=~fastapi`。`.env` 需在 `nonebot.init()` 前通过 `dotenv.load_dotenv()` 显式加载。

---

## 当前可工作配置

**.env 关键项：**
```ini
DRIVER=~fastapi
ONEBOT_ACCESS_TOKEN=communityos
GREETING_REPLY=你好呀 这里是柳千语
```

**NapCat：**
- WebSocket 客户端 → `ws://127.0.0.1:8080/onebot/v11/ws?access_token=communityos`
