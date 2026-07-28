# CommunityOS 总体架构

> **状态：** 正式
> **版本：** v1.2
> **最后更新：** 2026-07-27

---

# 目的

本文档定义 CommunityOS 的整体软件架构。

架构关注的是**系统如何组织**，而不是某个功能如何实现。

所有机器人功能、平台适配器、公共服务均应遵循本文档定义的架构。

---

# 设计目标

CommunityOS 的架构目标：

- 模块化
- 插件导向
- 平台无关
- 易于维护
- 易于扩展
- 自动化优先

任何新增功能都应尽量减少对已有模块的影响。

---

# 总体架构

```text
                  CommunityOS
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
  消息规则服务        公共服务           插件
 (Message Rule)    (Services)      (Plugins)
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   数据库 (SQLite)  指令系统         WebUI
  (Database)    (Command System)  (管理面板)
        │               │               │
        └───────────────┼───────────────┘
                        │
               平台适配层 (Platform Adapter)
                        │
                    NapCat / QQ
```

CommunityOS 分为七个主要层次：

- 消息规则服务（Message Rule Service）— 群消息统一入口，规则匹配与路由
- 公共服务（Services）— 可复用的通用能力
- 插件（Plugins）— 业务功能实现
- 数据库（Database）— SQLite 结构化存储，成员/权限/审核记录
- 指令系统（Command System）— 命令注册、权限检查、冷却、分发
- WebUI — 基于 FastAPI 的轻量管理面板，局域网访问
- 平台适配层（Platform Adapter）— 与聊天平台通信

---

# 消息规则服务

消息规则服务是群消息的统一入口，负责：

- 接收所有群消息
- 按规则匹配（`exact_text`、`contains_phrase`）
- 低权限命令自动路由到指令系统（管理群内免 @bot）
- 违禁词匹配后分发给自动审核插件
- 本身不执行指令或撤回，只做匹配与路由

---

# 指令系统

指令系统是 CommunityOS 的统一命令入口，负责：

- 命令注册与别名管理
- 命令冷却（三级：查询/会话/管理）
- 命令权限检查（User/Admin/Owner）
- 快捷映射（shortcuts，全句 → 完整指令）
- 命令分发与审计日志

---

# 公共服务

公共服务提供可复用的通用能力。

当前已实现：

- 日志（Logger Service）— 按领域分文件（bot/command/image/member/moderation/relationship）
- 配置（Config Service）— 外部 `.env` 配置
- 定时调度（Scheduler Service）— 基于 APScheduler
- 权限（Permission Service）— 三级权限（User/Admin/Owner）
- 会话（Session Service）— 多步交互流程管理
- 节流（Throttle Service）— 按 (user_id, reply_type) 控制回复频率
- 缓存（Cache Service）— 文件缓存，LRU 淘汰
- 运行时（Runtime Service）— 启动时间与运行状态
- 数据库（Database Service）— SQLite 统一存储，aiosqlite 驱动

公共服务不直接响应 QQ 消息。

公共服务仅向插件提供能力。

多个插件共享同一公共服务。

---

# 数据库

CommunityOS 使用 SQLite 作为结构化存储。

设计原则：

- **单文件、零部署** — 数据文件为 `data/communityos.db`
- **Raw SQL** — 无 ORM，依赖仅 `aiosqlite` 一个包
- **不替代日志** — 文本日志保留作为调试备份
- **不替代配置** — `.env` 和 `config/*.json` 保持现状

核心表：

| 表 | 用途 |
|----|------|
| users | 用户标识与首次出现记录 |
| group_memberships | 群成员关系与进出历史 |
| user_permissions | 统一权限（-1 黑名单 → 9 拥有者） |
| moderation_log | 审核操作审计记录 |
| command_log | 指令调用记录（查询层） |

迁移脚本位于 `bot/migrations/`，启动时自动执行未应用的迁移。

---

# 插件

CommunityOS 的所有功能均以插件形式存在。

当前已实现：

```text
plugins/

├── help.py              # 帮助指令
├── status.py            # 运行状态
├── command_dispatcher.py # 指令分发器
├── publish.py           # 批量发布（混淆 + 多群转发）
├── obfuscate.py         # 图片混淆
├── decode.py            # 图片解混淆（三种方式）
├── mute.py              # 禁言 / 解除禁言 / 自禁
├── auto_recall.py       # 违禁词自动撤回
├── auto_complete.py     # 网址自动补全
├── shortcuts.py         # 快捷映射查询
├── friend.py            # 好友申请自动处理
└── member.py            # 群成员变更日志
```

每个插件只负责一个明确职责。

插件之间应尽量保持独立。

新增功能时，应优先新增插件，而不是修改已有插件。

---

# 平台适配层

平台适配层负责与聊天平台通信。

当前支持：

- NapCat（QQ）

未来可扩展：

- Discord
- Telegram
- Matrix
- Web

平台适配层的职责：

- 接收平台事件
- 发送消息
- 上传文件
- 调用平台 API

业务逻辑不得写在平台适配层中。

---

# WebUI

CommunityOS 提供基于 FastAPI 的轻量管理面板，零额外依赖（NoneBot2 已自带 FastAPI）。

设计原则：

- 只做观察与触发，不插入消息处理链路
- 所有操作通过现有 Service 层，不绕过插件体系
- 浏览器请求和 QQ 消息共享同一个 asyncio 事件循环，不阻塞被动功能

当前功能：

- 系统运行状态查看
- 已加载插件列表
- 日志文件实时查看
- 快捷键 / 关键词 / 运行时配置热重载

访问方式：

- 机器人启动后自动挂载
- 局域网内浏览器打开 `http://<机器人IP>:8080/ui/`

---

# 测试架构

CommunityOS 采用双层测试策略，优先保证核心服务稳定，避免 QQ 环境依赖。

## 单元测试

测试对象：

- 权限服务（Permission Service）
- 指令解析器（Command Parser）
- 冷却系统（Cooldown）
- 缓存服务（Cache Service）

特点：

- 纯函数测试，不启动机器人
- 不依赖 NoneBot2、NapCat 或 QQ
- `pytest` 直接运行，秒级反馈

## 集成测试

测试链路：

```text
构造 Mock 事件 → Plugin handler → Service 调用 → 验证结果
```

特点：

- 使用 NoneBot2 的 pydantic 事件模型构造假事件
- Mock `bot.send()` 和平台 API，不连接真实 QQ
- 覆盖单步指令核心链路（help、status、mute 等）
- 多步会话测试暂缓

目录结构：

```text
tests/
├── unit/           # 纯函数单元测试
└── integration/    # Mock 事件集成测试
```

---

# 请求流程

群消息典型流程：

```text
QQ 群事件

↓

NapCat

↓

平台适配层

↓

消息规则服务
  ├─ 命令规则命中 → 指令系统 → 插件 → 公共服务 → 回复
  ├─ 审核规则命中 → auto_recall 插件 → 撤回
  └─ 未命中 → 忽略

↓

QQ 群
```

私聊消息直接由指令系统处理。

WebUI 请求路径：

```text
浏览器 (局域网)

↓

FastAPI /ui/api/*

↓

Core / Service（同进程函数调用）

↓

JSON 返回
```

WebUI 的所有操作与 QQ 指令走相同的 Service 层，区别仅在于输入来源。HTTP 请求和 QQ 消息共享同一个 asyncio 事件循环，浏览器操作不会阻塞机器人被动功能。

---

# 插件生命周期

插件统一由 NoneBot2 管理。

生命周期包括：

- 加载（Load）
- 启用（Enable）
- 停用（Disable）
- 重载（Reload）
- 卸载（Unload）

插件不应自行管理生命周期。

---

# 配置

所有配置均采用外部配置文件。

代码中不得硬编码：

- QQ 号
- 群号
- Token
- API Key
- 路径

配置通过 `.env` 和 `config/*.json` 提供，应支持未来统一管理。

---

# 日志

所有重要操作均应记录日志。

日志按业务领域分文件：

| 日志文件 | 用途 |
|----------|------|
| `bot.log` | 系统运行、启动、异常 |
| `command.log` | 指令执行 |
| `image.log` | 图片业务 |
| `member.log` | 群成员事件 |
| `moderation.log` | 管理操作审计 |
| `relationship.log` | 好友关系事件 |

日志由日志服务统一管理。控制台输出与文件独立控制。

---

# 错误处理

任何插件发生异常时：

- 不应导致机器人整体退出。
- 应记录错误日志。
- 应尽量继续运行其他插件。

插件之间应相互隔离。

---

# 目录结构

当前实际目录结构：

```text
bot/

├── core/               # 启动与生命周期钩子
├── services/           # 公共服务
├── plugins/            # 业务插件
├── ui/                 # WebUI 静态文件与 API
├── migrations/         # 数据库迁移脚本（.sql）
├── config/             # 配置文件（.json，gitignored）
├── data/               # 运行时数据（gitignored）
├── logs/               # 日志文件（gitignored）
├── main.py             # 入口
├── .env                # 环境配置（gitignored）
├── .env.example        # 配置模板
├── setup.bat           # 一键安装
├── start.bat           # 一键启动
└── requirements.txt    # Python 依赖

tests/
├── unit/               # 单元测试（纯函数）
└── integration/        # 集成测试（Mock 事件）
```

每个目录职责明确。

避免不同职责混合。

---

# 设计原则

CommunityOS 在开发过程中遵循以下原则：

- 单一职责
- 模块解耦
- 配置与代码分离
- 新增插件优于修改已有插件
- 稳定优先于复杂

---

# 不涵盖的内容

本文档不讨论：

- 社区治理
- 群规
- NapCat 部署方式（见 `deployment.md`）
- 插件内部实现
- 图片处理流程（见 `image-pipeline.md`）
- 指令系统细节（见 `command-system.md`）
- WebUI 设计与 API（见 `webui.md`）
- 测试策略与规范（见 `testing.md`）
- 数据库设计（见 `database.md`）

上述内容将在对应文档中说明。

---

# 结语

CommunityOS 希望通过清晰的模块划分，构建一个长期可维护的社区自动化系统。

平台可以变化。

插件可以增加。

实现可以重构。

整体架构应保持稳定，并持续支撑社区的发展。
