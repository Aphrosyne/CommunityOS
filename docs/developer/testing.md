# Testing 测试规范

> **状态：** 草案
> **版本：** v0.1
> **最后更新：** 2026-07-27

---

# 1. 测试目标

保证核心逻辑在脱离 QQ 环境的情况下可验证。

任何业务逻辑测试必须可以在没有 QQ 连接的情况下运行：

```bash
pytest
```

而不是：

```
先启动 QQ → 进群测试 → 观察回复
```

---

# 2. 测试分层

## 单元测试

测试单个模块的纯逻辑：

- 权限服务（Permission Service）
- 指令解析（Command Parser）
- 冷却系统（Cooldown）
- 缓存服务（Cache Service）
- 配置服务（Config Service）

特点：

- 不启动机器人
- 不连接 OneBot
- 不访问真实文件（必要时使用 `tmp_path`）
- 纯 `async def` 函数，pytest-asyncio 执行

## 集成测试

测试多个模块的协作链路：

```text
构造 Mock 事件
    ↓
指令分发器
    ↓
权限检查
    ↓
插件处理
    ↓
验证 Mock Bot 调用
```

特点：

- 使用 NoneBot2 pydantic 事件模型构造假事件
- Mock 所有平台 API（`bot.send`、`bot.delete_msg` 等）
- 验证的是「调用是否正确」，不是「QQ 是否真的发消息了」

---

# 3. Mock 约定

共享 fixture 放在 `tests/conftest.py`，pytest 自动发现，测试函数通过参数名注入。

## MockBot

```python
@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send = AsyncMock()
    bot.delete_msg = AsyncMock()
    bot.set_group_kick = AsyncMock()
    bot.set_group_ban = AsyncMock()
    return bot
```

## MockEvent

使用 NoneBot2 原生 pydantic 模型，不依赖真实 QQ：

```python
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message

@pytest.fixture
def make_group_event():
    def _make(user_id=123456, group_id=789012, raw_message=""):
        return GroupMessageEvent(
            time=1234567890,
            self_id=111111,
            post_type="message",
            message_type="group",
            sub_type="normal",
            user_id=user_id,
            group_id=group_id,
            message=Message(raw_message),
            raw_message=raw_message,
            font=0,
            sender=GroupMessageEvent.Sender(
                user_id=user_id, nickname="测试用户"
            ),
            message_id=1,
            message_seq=1,
        )
    return _make
```

---

# 4. 目录结构

```text
tests/
├── conftest.py              # 共享 fixture: mock_bot, mock_event
├── unit/
│   ├── test_permission.py   # 权限检查
│   ├── test_command.py      # 指令解析与冷却
│   └── test_cache.py        # 缓存读写与淘汰
└── integration/
    └── test_message_flow.py # 消息 → 指令分发 → 权限 → 插件
```

---

# 5. 优先覆盖范围

不要一开始全覆盖。按以下顺序逐步添加：

| 优先级 | 模块 | 理由 |
|--------|------|------|
| 1 | Permission Service | 涉及安全，权限判断出错后果严重 |
| 2 | Command System | 用户交互入口，改坏所有指令都挂 |
| 3 | Message Rule | 管 `@bot` 和自动撤回，误触发会刷屏 |
| 4 | Cache Service | 已有持久化，缓存逻辑独立易测 |

---

# 6. 测试原则

- 业务逻辑测试必须可在无 QQ 环境下运行
- 每个测试只验证一件事
- 测试名描述场景：`test_user_without_permission_is_blocked`
- 不追求覆盖率数字
- 代码快速变化时，只为核心逻辑写测试

---

# 7. 当前不要做的事

- 不追求 100% 覆盖率
- 不为每个插件写几十个测试
- 不引入 CI/CD 流水线
- 不做 E2E 测试（需要真实 QQ）
- 不做自动发布

目标：**防止核心逻辑回归**，不是测试驱动开发。

---

# 8. 相关文档

- [总体架构](../architecture.md)
- [插件开发指南](../developer/plugin-development.md)
- [数据库设计](../design/database.md)
