# Database Roadmap 数据库实施路线

> **状态：** Round 1-5 已完成，Round 6 暂缓
> **版本：** v0.2
> **最后更新：** 2026-07-29

---

# 1. 概述

本文档将 database.md 定义的设计拆分为 5+1 轮原子级任务（Round 6 暂缓）。

每轮任务为一个独立 commit，包含代码实现和对应的 pytest 测试。`pytest` 全绿才提交。

---

# 2. 任务拆分

## Round 1 — 基础设施

> **状态：** ✅ 已完成

**目标：** 数据库文件可创建，迁移脚本可执行。

**实现：**

- 新增依赖 `aiosqlite` 到 `requirements.txt`
- 创建 `bot/migrations/001_create_tables.sql`（users、group_memberships、user_permissions、moderation_log、command_log，5 张表 + 索引）
- 创建 `bot/services/database.py`：连接管理、迁移执行、启动时自动建表
- `bot/core/__init__.py` 启动钩子调用 `database.setup()`

**pytest：**

- `test_migration.py` — 验证新数据库 5 张表存在且结构正确
- `test_database.py` — 验证连接正常，读写基本 SQL

**验证：**

- `cd bot && python test_check.py` 输出表结构检查通过
- 启动机器人无异常

---

## Round 2 — 用户与成员

> **状态：** ✅ 已完成

**目标：** 用户和群成员关系可记录、可查询。

**实现：**

- `database.py` 新增：`upsert_user(user_id)`、`record_membership(user_id, group_id, event)`
- `plugins/member.py` 接入：join → status=active，leave → status=left，kick → status=kicked
- `plugins/friend.py` 接入：好友申请通过后调用 `upsert_user`

**pytest：**

- `test_user.py` — 新用户创建、重复用户不重复插入
- `test_membership.py` — 入群状态变更、退群时间记录、反复进出 join_count 递增

**验证：**

- 拉一个测试号进群再踢出 → `group_memberships` 表中出现对应记录且 status 正确

---

## Round 3 — 权限系统

> **状态：** ✅ 已完成

**目标：** 权限判断从读 `.env` 切换为读数据库，支持运行时增删。

**实现：**

- 启动时 `.env` 中的 `OWNER=` 作为种子写入 `user_permissions`（level=9）
- `database.py` 新增：`get_permission(user_id, group_id) → int`、`grant_permission(...)`、`revoke_permission(...)`
- `services/permission.py` 重写：从数据库读权限替代读 `.env`
- `plugins/command_dispatcher.py` 接口适配：调用 `check()` 时多传 `group_id`
- 新增命令：`/admin add @user`、`/admin remove @user`、`/blacklist add @user`、`/blacklist remove @user`（Admin+ 可执行）

**pytest：**

- `test_permission_db.py` — 三级权限检查、黑名单拦截、白名单豁免、群级权限优先于全局、过期权限自动失效

**验证：**

- Owner 仍能正常使用所有指令（无回退）
- Admin 能执行 `/admin add @测试号` → 测试号可用管理指令
- 黑名单用户发送指令被静默忽略

---

## Round 4 — 审核日志

> **状态：** ✅ 已完成（v1.2.0，2026-07-29）

**目标：** 管理操作有结构化审计记录。

**实现：**

- `database.py` 新增：`log_moderation(action, user_id, operator_id, group_id, reason, details)`
- `plugins/mute.py` 接入：禁言/解禁时写入 `moderation_log`
- `plugins/auto_recall.py` 接入：违禁词撤回时写入

**pytest：**

- `test_moderation_log.py` — 写入一条记录、按用户查询审核历史、按群查询、字段完整性

**验证：**

- 执行一次禁言 → `moderation_log` 表中有对应记录（action=mute, operator_id, user_id 正确）

---

## Round 5 — 指令日志

> **状态：** ✅ 已完成（v1.2.0，2026-07-29）

**目标：** 指令调用有结构化查询层。

**实现：**

- `database.py` 新增：`log_command(user_id, group_id, command_name, raw_text, result)`
- `plugins/command_dispatcher.py` 接入：每次指令执行后写入（`command.log` 文本日志保留不变）

**pytest：**

- `test_command_log.py` — 写入一条指令记录、验证字段完整性、文本截断

**验证：**

- 执行 `/status` → `command_log` 表出现一条记录，command_name=status, result=success

---

## Round 6 — 批量查询 + 成员扫描（暂缓）

**目标：** 批量查询 API + 群成员扫描录入数据库。

**实现：**

- `database.py` 新增：`get_active_members(group_id) → list`、`get_kickable_members(group_id) → list`（level ≤ 0）
- 新增 `services/member_scanner.py`：调用 OneBot `get_group_member_list` 扫描群成员，upsert 到 `users` 和 `group_memberships` 表
- 批量清人豁免已在 Round 3 的 `user_permissions` 中天然支持

**pytest：**

- `test_batch.py` — 批量查询活跃成员、白名单及以上自动豁免
- `test_member_scanner.py` — 模拟 API 返回，验证 upsert 正确

**验证：**

- 调用扫描函数 → `group_memberships` 表中出现当前群成员记录
- 批量查询函数返回结果正确

> **此轮在 WebUI 和批量管理功能开发时接入，当前暂缓执行。**

---

# 3. 每轮约束

- 一个 commit，独立可回滚
- 新增 pytest 覆盖本轮全部改动
- pytest 全绿 + 手动验收通过才进入下一轮
- 不改动未接入的插件
- 不删除或修改现有 `*.log` 文本日志

---

# 4. 相关文档

- [数据库设计](../design/database.md)
- [测试规范](../developer/testing.md)
- [总体架构](../architecture.md)
