# Database 数据库设计

> **状态：** 草案
> **版本：** v0.2
> **最后更新：** 2026-07-29

---

## 变更记录

- **v0.2 (2026-07-29):** Round 1 Permission Security Hardening：H1（Owner 保护 defense-in-depth 下沉 DB 层）、H2（BotAdmin 同级保护）、M2（level 值域校验）、M3（clear_user_permissions Owner 保护）、M9（_migrations.applied_at 时间戳统一）；明确白名单能力实现状态（H4）。
- **v0.1 (2026-07-28):** 初始版本，Round 1-5 设计完成。

---

# 1. 目的

本文档定义 CommunityOS 的数据库设计。

当前版本引入 SQLite 作为结构化存储，统一管理成员、权限、审核记录等需要查询的数据，替代纯文本日志 grep 的现状。

---

# 2. 设计原则

- **SQLite 优先** — 单文件、零部署、零配置，与 bot 同生命周期
- **Raw SQL** — 无 ORM，依赖仅 `aiosqlite` 一个包
- **渐进接入** — 表结构一次建好，数据写入按轮次接入各插件
- **不替代日志** — 日志文件保留作为调试备份，数据库是查询层
- **不替代配置文件** — `.env` 和 `config/*.json` 保持现状
- **时间戳格式** — 所有 TEXT 时间字段统一使用 Python `datetime.now().astimezone().isoformat()`，含本地时区偏移（如 `2026-07-28T15:30:00+08:00`）。注意：与 SQLite `datetime('now')`（UTC 无时区）不可直接比较，过期查询需用 Python 端构造时间字符串或在 SQL 端转换
- **时间戳统一（M9）** — `_migrations.applied_at` 亦改用 Python 端 `_now_iso()` 注入，不再使用 SQLite `datetime('now')` 默认值，保证全库时间戳格式一致

---

# 3. 数据模型

## 3.1 权限层级

```text
-1  黑名单  Blacklist      禁止使用任何功能
 0  普通    User           默认等级
 1  白名单  Whitelist      豁免批量清人（防撤回/冷却豁免暂未实现，见注）
 2  群管理  GroupAdmin     仅对应群内有效
 3  管理员  BotAdmin       跨群机器人管理
 9  拥有者  Owner          最高权限
```

4-8 预留未来扩展。

> **白名单能力实现状态（H4）：** database.md 原设计白名单 = "豁免批量清人 / 防撤回 / 冷却豁免"。
> 当前实现中"防撤回"与"冷却豁免"暂未实现（auto_recall 与 dispatcher 仅对 Owner 豁免），
> "豁免批量清人"将在 Round 6 引入。
> 详见 [technical-debt.md H4](../technical-debt.md)。

### 权限模型安全保证

数据库层强制以下安全约束（defense-in-depth，与命令层保护互补）：

| 约束 | 位置 | 说明 |
|------|------|------|
| level 值域校验（M2） | `database.set_permission` | level 不在 `[-1, 9]` 抛 `ValueError` |
| Owner 写保护（H1） | `database.set_permission` | `user_id == OWNER` 且 `level != 9` 抛 `PermissionError` |
| Owner 清除保护（M3） | `database.clear_user_permissions` | `user_id == OWNER` 抛 `PermissionError` |

常量 `LEVEL_MIN = -1`、`LEVEL_MAX = 9` 定义在 [bot/services/database.py](../../bot/services/database.py)，避免与 `services/permission.py` 循环依赖。

> **黑名单语义限制（M1）：** 全局黑名单（group_id=0, level=-1）不覆盖群级权限。若用户同时有全局黑名单与某群级权限，MAX 聚合后该群返回群级权限值，黑名单在该群失效。紧急拉黑多群管理员需在每个群单独移除群级权限。详见 [technical-debt.md M1](../technical-debt.md)。

## 3.2 表结构

### users — 用户

| 列 | 类型 | 说明 |
|----|------|------|
| user_id | INTEGER PRIMARY KEY | QQ 号 |
| first_seen | TEXT | 首次出现时间 |
| last_updated | TEXT | 最后更新时间 |

### group_memberships — 群成员关系

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| user_id | INTEGER NOT NULL | → users.user_id |
| group_id | INTEGER NOT NULL | 群号 |
| status | TEXT NOT NULL | active / left / kicked |
| joined_at | TEXT | 最近入群时间 |
| left_at | TEXT | 最近退群时间 |
| join_count | INTEGER DEFAULT 1 | 累计入群次数 |
| last_event | TEXT | 最近事件: join / leave / kick |

UNIQUE(user_id, group_id)

> **存根记录语义：** 首次部署过渡期，无入群历史记录的用户直接退群/被踢时，插入 `joined_at=NULL, join_count=0, last_event=leave/kick` 的存根行，保留用户痕迹。文本日志是源数据，DB 是查询层。

### user_permissions — 权限

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| user_id | INTEGER NOT NULL | → users.user_id |
| group_id | INTEGER NOT NULL DEFAULT 0 | 0 = 全局生效 |
| level | INTEGER NOT NULL | -1 ~ 9 |
| granted_by | INTEGER | 授予者 → users.user_id |
| granted_at | TEXT | 授予时间 |
| expires_at | TEXT | NULL = 永久 |
| reason | TEXT | 备注原因 |

UNIQUE(user_id, group_id, level)

### moderation_log — 审核记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| user_id | INTEGER | 被操作者 |
| operator_id | INTEGER | 操作者（0 = 系统操作） |
| group_id | INTEGER | 在哪个群（0 = 全局权限操作） |
| action | TEXT NOT NULL | mute / unmute / mute_denied / auto_recall / permission_set / permission_denied |
| reason | TEXT | 原因 |
| timestamp | TEXT NOT NULL | 操作时间 |
| details | TEXT | 附加信息（JSON 字符串，见下方说明） |

> **无外键约束（Q1-A）：** `user_id`、`operator_id` 不添加 `REFERENCES users(user_id)`。审计日志优先级高于数据完整性约束——被操作用户可能不存在于 `users` 表，`operator_id` 可能为系统操作（0），日志写入应尽可能成功，不因用户不存在而失败。写入逻辑（`log_moderation`）不调用 `upsert_user`。
>
> **action 值域（Q2-A）：** 沿用现有文本日志命名，保证数据库日志与 `moderation.log` 文本日志可互相对照：`mute` / `unmute` / `mute_denied` / `auto_recall` / `permission_set` / `permission_denied`。不重新设计命名，后续 UI 展示可再做映射。
>
> **details 字段格式（Q5-A）：** 以 JSON 字符串存储于 TEXT 列。写入前由 Python `json.dumps()` 序列化（`ensure_ascii=False, default=str`），读取时由 `json.loads()` 反序列化。`details=None` 写入 NULL。不新增 `duration`、`keywords` 等固定列。示例：`{"duration": 60, "type": "normal"}`。
>
> **不记录权限拒绝（Q3-A）：** `permission_denied` 仅在管理操作被拒绝时（如对 Owner 执行降级）记录；`command_dispatcher` 的常规权限拒绝不写入 `moderation_log`（高频正常事件，避免无意义记录），保留文本日志即可。

### command_log — 指令记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| user_id | INTEGER | 调用者 |
| group_id | INTEGER | 调用所在群（私聊 0，Q6-B） |
| command_name | TEXT NOT NULL | 命令名称（shortcut 命中时记录最终命令名，Q8-A） |
| raw_text | TEXT | 原始消息文本（Python 端截断至 200 字符，Q5-A；None → NULL） |
| result | TEXT | success / error（其他状态本轮不记录，见下方说明） |
| timestamp | TEXT NOT NULL | 调用时间 |

> **无外键约束（Q1-A）：** `user_id` 不添加 `REFERENCES users(user_id)`。指令日志是行为审计日志，未注册用户也可执行指令，写入不应依赖 `users` 表存在。`log_command` 不调用 `upsert_user`。
>
> **私聊 group_id（Q6-B）：** 私聊场景 `group_id=0`，与 `command_dispatcher.py` 现有逻辑一致，与 `user_permissions.group_id=0` 全局语义统一，避免 NULL 特殊处理。
>
> **raw_text 截断（Q5-A）：** 写入前由 Python 端 `raw_text[:200]` 截断至 200 字符，`None` 写入 NULL。
>
> **不记录的状态（Q2-A / Q3-A / Q4-A）：** `command_log` 只记录实际执行的指令（result=success/error）。以下情况不写入：
> - 黑名单拦截（Q2-A，静默忽略）
> - 冷却期拦截（Q3-A，高频正常事件）
> - 权限拒绝（Q4-A，与 `moderation_log` 设计一致）
> - 未注册命令、参数校验失败、group_only 场景不符（均静默 return）
>
> **shortcut 命中（Q8-A）：** 快捷映射触发后按最终命令名记录，不增加 shortcut 标记字段。
>
> **写入失败处理：** `command_dispatcher` 调用 `log_command` 失败时仅记日志不抛出，不影响指令执行结果。

当前 `command.log` 文本日志保留，此表作为查询层逐步启用。

---

# 4. 核心查询

## 获取用户在某群的有效权限

```sql
SELECT MAX(level) FROM user_permissions
WHERE user_id = ?
  AND group_id IN (0, ?)
  AND (expires_at IS NULL OR expires_at > datetime('now'))
```

## 获取群内活跃成员数

```sql
SELECT COUNT(*) FROM group_memberships
WHERE group_id = ? AND status = 'active'
```

## 获取某用户的所有审核记录

```sql
SELECT * FROM moderation_log
WHERE user_id = ?
ORDER BY timestamp DESC
LIMIT 50
```

## 批量清人（筛选可踢出成员）

```sql
SELECT gm.user_id FROM group_memberships gm
LEFT JOIN user_permissions up
  ON up.user_id = gm.user_id AND (up.group_id = gm.group_id OR up.group_id IS NULL)
WHERE gm.group_id = ?
  AND gm.status = 'active'
  AND (up.level IS NULL OR up.level <= 0)
```

---

# 5. 迁移策略

## 目录

```text
bot/migrations/
├── 001_create_tables.sql          # 建全部 5 张表 + 索引
├── 002_add_audit_indexes.sql      # 审计日志按 action / command_name 查询索引
└── 003_xxx.sql                    # 后续变更
```

## 命名规范（L3）

**迁移文件名必须使用 3 位数字前缀**（`NNN_描述.sql`），因为 `_run_migrations` 按 `f.name` 字典序排序执行。零填充保证 `002_` 在 `010_` 之前、`010_` 在 `100_` 之前。无前缀或非零填充（如 `10_xxx.sql`）会导致执行顺序错乱。

示例：
- ✅ `001_create_tables.sql`
- ✅ `002_add_audit_indexes.sql`
- ❌ `10_xxx.sql`（会被排到 `002_` 之前）
- ❌ `xxx.sql`（无序号前缀，字典序不可预期）

## 执行

启动时自动检查并执行未应用的迁移，跟踪记录在 `data/migration_state` 或数据库内 `_migrations` 表中。

## 时间戳与 `expires_at` 比较约束（L4）

- 所有时间戳列（`first_seen` / `last_updated` / `applied_at` / `timestamp` / `expires_at` 等）统一使用 Python 端 `_now_iso()` 注入的 ISO 8601 含本地时区偏移格式（如 `2026-07-31T15:30:00+08:00`），见 M9。
- `get_permission` 的 `expires_at > ?` 字符串比较依赖 `expires_at` 与查询时传入的 `_now_iso()` 使用**相同的时区偏移**。当前实现两者都来自 `_now_iso()`，时区一致，比较安全。
- **约束**：调用 `set_permission` 传 `expires_at` 时，必须使用 `_now_iso()` 同款格式（含时区偏移的 ISO 8601）。传入 UTC 无时区或不同时区偏移会导致比较结果错误。
- 未来若引入跨时区客户端（WebUI），应在 Service 层统一归一化为 UTC 或统一时区后再写入。

## 首次部署

新环境首次启动时，Owner 从 `.env` 中的 `OWNER=` 作为种子写入 `user_permissions`（level=9），之后 Owner 可通过命令管理其他权限。

---

# 6. 接入计划

| 轮次 | 接入插件 | 写入表 |
|------|----------|--------|
| 1 | — | 建表 + migration 框架 |
| 2 | member.py, friend.py | users, group_memberships |
| 3 | Permission Service | user_permissions（读写） |
| 4 | mute.py, auto_recall.py, admin.py | moderation_log |
| 5 | command_dispatcher.py | command_log |
| 6 | WebUI | 批量查询 API |

> 详细任务拆分见 [database-roadmap.md](database-roadmap.md)。

每轮独立提交，不影响现有功能。

---

# 7. 当前版本范围

Database v0.1 包含：

- SQLite + aiosqlite 选型
- 5 张核心表的 Schema
- 权限层级统一模型
- 迁移脚本框架
- Permission Service 重构为数据库读写

当前版本不包含：

- 数据库备份自动化（手动 `cp communityos.db`）
- 多实例同步
- 数据可视化 / 统计面板
- ORM 抽象层

---

# 8. 相关文档

- [总体架构](../architecture.md)
- [权限服务](../design/permission.md)
- [插件开发指南](../developer/plugin-development.md)
