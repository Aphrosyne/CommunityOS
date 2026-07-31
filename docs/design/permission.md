# Permission Service 权限服务

> **状态：** 正式
> **版本：** v1.1
> **最后更新：** 2026-07-29

---

## 变更记录

- **v1.1 (2026-07-29):** 升级到 9 级权限模型，反映 Database Round 1-5 实现；新增 defense-in-depth 安全保证（H1/H2/M2/M3）；更新白名单能力状态。
- **v1.0 (2026-07-02):** 初始版本，三级权限模型（User/Admin/Owner）。

---

## 1. 目的

权限服务是 CommunityOS 的统一权限服务，负责判断用户是否有权执行某项操作。

它的目标是避免权限判断散落在各个插件中，使所有插件使用一致的权限模型和检查方式。

权限服务关注的是：

* 用户拥有什么权限；
* 某项操作需要什么权限；
* 是否允许执行。

权限服务不负责具体业务逻辑，也不负责执行命令。

---

## 2. 设计原则

### 统一检查

所有需要权限控制的功能，均通过权限服务判断权限。

插件不应自行维护管理员列表，也不应在业务代码中直接比较用户标识。

---

### 最小权限

每项操作只要求完成该操作所需的最低权限。

普通用户可使用公开功能；管理操作仅对管理员开放；系统级操作仅对 Owner 开放。

---

### 显式声明

命令和功能应明确声明所需权限等级。

权限要求不应隐藏在业务逻辑内部。

---

### 默认拒绝

当权限配置缺失、权限等级未知或权限判断失败时，系统默认拒绝执行受保护操作。

公开功能除外。

---

### 可扩展

权限服务的基础模型应支持未来增加：

* 黑名单；
* 白名单；
* 群级权限；
* 临时权限；
* 角色权限；
* 外部平台角色同步。

这些能力不属于当前版本范围，但不应破坏基础权限模型。

---

## 3. 权限等级

当前版本（v1.1）采用 9 级权限模型，与 [database.md §3.1](database.md) 一致。

| 等级 | 名称       | 说明                                       |
| ---- | ---------- | ------------------------------------------ |
| -1   | Blacklist  | 黑名单，禁止使用任何功能。                 |
| 0    | User       | 普通用户，可使用公开功能。默认等级。       |
| 1    | Whitelist  | 白名单，豁免批量清人（防撤回/冷却豁免暂未实现，见 §12）。 |
| 2    | GroupAdmin | 群管理员，仅对应群内有效（群级权限）。     |
| 3    | BotAdmin   | 跨群机器人管理。                           |
| 9    | Owner      | 机器人所有者，最高权限。                   |

权限等级具有继承关系，高等级权限自动包含低等级权限：

```text
Owner (9)
  ↓
BotAdmin (3)
  ↓
GroupAdmin (2) [仅群内]
  ↓
Whitelist (1)
  ↓
User (0)

Blacklist (-1) 独立存在，禁止任何功能。
```

例如，Owner 可以执行 BotAdmin、GroupAdmin、Whitelist 和 User 权限的操作。

### 等级间操作权限（Q13-A / H2）

为防止横向越权（peer privilege escalation），权限修改操作遵循以下规则：

- **Owner 保护**：target 为 Owner（level=9）时，任何人都不可降级或拉黑。
  保护由 `.env OWNER` 配置与 DB 层双层强制（defense-in-depth，见 §6）。
- **同级保护**（H2）：非 Owner 操作者不可影响权限等级 ≥ 自身的用户。
  即 BotAdmin 之间互相禁止降权/拉黑；同级互操作的紧急场景必须由 Owner 完成。

详见 [bot/plugins/admin.py](../../bot/plugins/admin.py) 的 `_apply` 函数。

---

## 4. 权限来源

当前版本（v1.1）的权限来源为：

* `.env OWNER`：Owner 用户标识，启动时种子写入 `user_permissions` 表。
* `.env ADMINS`：BotAdmin 用户标识列表，启动时种子写入（覆盖语义）。
* 管理指令 `/botadmin` `/groupadmin` `/whitelist` `/blacklist` `/perm` 动态修改。

权限数据由 SQLite 数据库存储（见 [database.md](database.md)），由 `services/permission.py` 作为统一入口，插件不应绕过该入口直接读写 `user_permissions` 表。

### 种子写入行为（M4 待定）

`seed_from_env()` 在每次启动时用 `set_permission` 覆盖写入 Owner 与 BotAdmin 记录。当前行为：

- 运行时降级 BotAdmin 的操作会在下次重启后被回滚为 `.env ADMINS` 中声明的等级。
- Owner 记录每次刷新为 level=9（受 H1 保护，允许维持等级，禁止降级）。

该行为是否在后续版本改为"仅在不存在时插入"（INSERT OR IGNORE 语义）待定，见 [technical-debt.md M4](../technical-debt.md)。

---

## 5. Bot Admin 与群管理员

当前版本中的 `Admin` 指的是 **Bot Admin**（机器人管理员）。

Bot Admin 由机器人配置文件维护，拥有跨群的机器人管理权限。该权限不依赖 QQ 群内的管理员身份。

QQ 群管理员属于群平台提供的角色，只在对应群内有效。群管理员身份不自动转换为 Bot Admin，也不自动获得机器人管理权限。

未来如需支持群治理功能，可在 Permission Service 中新增群上下文权限，例如 `GroupAdmin` 或 `GroupModerator`。该类权限仅对当前群生效，权限等级低于 Bot Admin。

当前版本不实现群管理员自动识别或同步。

---

## 6. 权限检查模型

权限服务提供统一的权限判断能力。

概念流程如下：

```text
用户请求
    ↓
命令 / 插件
    ↓
权限服务
    ↓
获取用户权限等级
    ↓
比较所需权限
    ↓
允许 / 拒绝
```

命令或功能声明所需权限等级。

权限服务根据用户身份返回判断结果。

插件根据结果决定是否继续执行。

### Owner 特权

Owner 是机器人运行与维护的最高权限主体。

在当前版本中，Owner 可以跳过功能冷却限制，用于测试、维护和紧急处理。

Owner 的冷却豁免仅适用于功能使用频率限制，不应绕过以下限制：

* 单次图片数量上限；
* 文件格式与大小限制；
* 会话状态限制；
* 任务处理中限制；
* 系统安全限制。

BotAdmin 与 User 均遵循正常冷却规则。

冷却豁免应由公共冷却机制结合 Permission Service 统一处理，Plugin 不应自行判断 Owner 身份。

### Owner 保护 defense-in-depth（H1 / M3）

Owner 是系统最高权限主体，不可被降级或拉黑。保护机制分两层：

1. **命令层**（[bot/plugins/admin.py](../../bot/plugins/admin.py) `_apply`）：检查 target_level >= Owner 时拒绝，写 `permission_denied` 审计日志。
2. **数据库层**（[bot/services/database.py](../../bot/services/database.py)）：
   - `set_permission(user_id == OWNER, level != 9)` 抛 `PermissionError`（H1）。
   - `clear_user_permissions(user_id == OWNER)` 抛 `PermissionError`（M3）。

`.env OWNER` 是 Owner 身份的权威源，DB 状态损坏（误删、迁移失败）时命令层保护仍可能失效，但 DB 层兜底保证无法通过直写 API 破坏 Owner。这是 defense-in-depth 设计。

### level 值域校验（M2）

`database.set_permission` 在写入前校验 `level ∈ [-1, 9]`，超出范围抛 `ValueError`。防止 WebUI 或未来插件传非法 level 值破坏权限模型。常量 `LEVEL_MIN = -1`、`LEVEL_MAX = 9` 定义在 `services/database.py`，与 `Level` 类对应。


---

## 7. 指令系统集成

指令系统是权限服务的主要调用方之一。

每个命令可以声明最低权限等级。

例如：

| 命令类型                     | 最低权限 |
| ---------------------------- | -------- |
| 帮助、状态、混淆、发布、解图 | User     |
| 管理操作、群设置、审核操作   | Admin    |
| 系统配置、插件控制、维护操作 | Owner    |

指令分发器在执行命令前完成权限检查。

权限不足时，命令不进入插件执行流程。

---

## 8. 插件集成

插件可以依赖权限服务完成业务内权限判断。

适用场景包括：

* 多步骤会话中的权限确认；
* 非命令触发的管理操作；
* 群事件处理；
* 自动化任务执行。

插件不应自行实现权限等级比较。

---

## 9. 权限不足处理

当用户权限不足时，系统应：

* 拒绝执行受保护操作；
* 返回简短、明确的提示；
* 记录权限拒绝事件；
* 不泄露管理员名单、Owner 身份或内部配置。

权限不足提示不应包含系统敏感信息。

---

## 10. 与其他服务的关系

### 配置服务

权限服务从配置服务获取 Owner 和 Admin 配置。

---

### 指令系统

指令系统在命令分发前调用权限服务完成权限检查。

---

### 日志服务

权限拒绝事件记录到 `moderation.log`，格式如下：

```text
action=permission_denied operator=<user_id> group=<group_id> target=0 result=denied reason=command=<name> required_level=<level>
```

权限检查成功的事件不单独记录（由 `command.log` 记录命令执行）。

当前版本不单独创建 `permission.log`。

---

### 会话服务

会话在需要权限确认时可调用权限服务。

会话不自行维护用户权限状态。

---

## 11. 当前版本范围

权限服务 v1.1 包含：

* 9 级权限模型（Blacklist/User/Whitelist/GroupAdmin/BotAdmin/Owner）；
* 基于 `.env` 与数据库存储的双重权限来源（Owner/BotAdmin 种子 + 动态修改）；
* 统一权限检查接口（`get_level` / `check` / `is_owner` / `is_blacklisted`）；
* 指令分发器权限接入（命令声明 `permission` + dispatcher 统一检查）；
* 权限拒绝提示与 `moderation.log` 审计日志记录；
* 管理指令 `/botadmin` `/groupadmin` `/whitelist` `/blacklist` `/perm`（英文别名 sba/sga/swl/sbl/spm）；
* Owner 保护 defense-in-depth（命令层 + 数据库层双层，H1/M3）；
* BotAdmin 同级保护（H2）；
* `set_permission` level 值域校验（M2）。

当前版本不包含：

* 白名单的"防撤回"与"冷却豁免"能力（见 §12）；
* 全局黑名单覆盖群级权限（黑名单语义限制，见 [technical-debt.md M1](../technical-debt.md)）；
* Web 管理面板；
* 临时权限过期触发清理；
* 多机器人实例权限同步。

---

## 12. 后续规划

后续版本可逐步增加：

* 白名单的防撤回与冷却豁免能力（与 database.md §3.1 设计一致）；
* 全局黑名单覆盖群级权限（解决 M1）；
* 权限变更审计日志的查询接口（Round 6 WebUI 接入）；
* 临时权限；
* Web 管理面板；
* 多机器人实例权限同步。

这些能力应建立在当前统一权限模型之上，而不改变插件使用方式。

---

## 13. 总结

权限服务是 CommunityOS 的公共基础服务之一。

它通过统一的权限等级和检查接口，将权限判断从插件中抽离出来，使命令、会话和未来的管理功能可以使用一致的权限模型。

当前版本优先解决基础权限识别和命令保护问题，为后续社区治理和管理功能提供稳定基础。

---

## 14. 相关文档

- [指令系统](../design/command-system.md)
- [插件开发指南](../developer/plugin-development.md)
- [总体架构](../architecture.md)
