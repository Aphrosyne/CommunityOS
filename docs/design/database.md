# Database 数据库设计

> **状态：** 草案
> **版本：** v0.1
> **最后更新：** 2026-07-28

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

---

# 3. 数据模型

## 3.1 权限层级

```text
-1  黑名单  Blacklist      禁止使用任何功能
 0  普通    User           默认等级
 1  白名单  Whitelist      豁免批量清人 / 防撤回 / 冷却豁免
 2  群管理  GroupAdmin     仅对应群内有效
 3  管理员  BotAdmin       跨群机器人管理
 9  拥有者  Owner          最高权限
```

4-8 预留未来扩展。

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
| operator_id | INTEGER | 操作者 |
| group_id | INTEGER | 在哪个群 |
| action | TEXT NOT NULL | mute / unmute / kick / warn / blacklist_add / blacklist_remove / whitelist_add |
| reason | TEXT | 原因 |
| timestamp | TEXT NOT NULL | 操作时间 |
| details | TEXT | 附加信息（JSON） |

### command_log — 指令记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| user_id | INTEGER | 调用者 |
| group_id | INTEGER | 调用所在群（私聊 NULL） |
| command_name | TEXT NOT NULL | 命令名称 |
| raw_text | TEXT | 原始消息文本（截断至 200 字符） |
| result | TEXT | success / cooldown_blocked / permission_denied / error |
| timestamp | TEXT NOT NULL | 调用时间 |

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
├── 001_initial.sql      # 建全部 5 张表 + 索引
└── 002_xxx.sql          # 后续变更
```

## 执行

启动时自动检查并执行未应用的迁移，跟踪记录在 `data/migration_state` 或数据库内 `_migrations` 表中。

## 首次部署

新环境首次启动时，Owner 从 `.env` 中的 `OWNER=` 作为种子写入 `user_permissions`（level=9），之后 Owner 可通过命令管理其他权限。

---

# 6. 接入计划

| 轮次 | 接入插件 | 写入表 |
|------|----------|--------|
| 1 | — | 建表 + migration 框架 |
| 2 | member.py, friend.py | users, group_memberships |
| 3 | mute.py, auto_recall.py | moderation_log |
| 4 | Permission Service | user_permissions（读写） |
| 5 | command_dispatcher.py | command_log |

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
