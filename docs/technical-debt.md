# Technical Debt 技术债追踪

> **状态：** 活跃
> **版本：** v0.2
> **最后更新：** 2026-07-31
> **来源：** Database Round 1-5 Code Review（2026-07-29）

---

# 1. 目的

本文档是 CommunityOS 项目级技术债管理文档，**不是 bug list**。

记录已知问题、风险、当前状态、未来处理方向与优先级，避免后续开发遗忘。

新条目通过 Code Review、设计评审或运维事件录入；处理完成的条目移至 §9 已解决清单，不直接删除，保留历史可追溯。

---

# 2. 优先级定义

| 优先级 | 含义 | 处理时机 |
|--------|------|----------|
| High | 阻塞下一阶段开发或存在安全风险 | 进入 Round 6 前必须处理 |
| Medium | 影响可维护性或潜在 bug | Round 6 期间处理 |
| Low | 优化项，无即时风险 | 后续阶段按需处理 |
| Deferred | 暂不处理 | 触发条件出现时再评估 |

---

# 3. High Priority Debt

进入 Database Round 6（WebUI / 批量查询）前必须处理。

## H1 Owner 保护依赖数据库状态

**当前问题：**
Owner 保护逻辑只查 `user_permissions` 表（[bot/plugins/admin.py:80-81](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py#L80-L81)、[bot/plugins/admin.py:233-234](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py#L233-L234)）。`seed_from_env()` 是 Owner 写入 DB 的唯一来源；若 `database.setup()` 后 `seed_from_env()` 抛异常，或运维误删 Owner 记录，DB 中 Owner 不存在，`get_level(owner, 0)` 返回 0。

**风险：**
- 数据库异常、权限记录损坏时，Owner 保护失效。
- 任何 BotAdmin 即可 `/blacklist add @owner`。
- 违反 project_memory 硬约束"Owner (level=9) cannot be demoted or blacklisted"。

**当前状态：** 未修复。

**未来方向：**
增加 `.env OWNER` 环境配置级保护，与 DB 检查形成 defense-in-depth。在 `database.set_permission` / `clear_user_permissions` 内部拒绝 `user_id == OWNER` 的写操作（数据层兜底），命令层保留显式提示。

**关联文件：** [bot/plugins/admin.py](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py), [bot/services/permission.py](file:///c:/AphrosyneData/CommunityOS/bot/services/permission.py), [bot/services/database.py](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py)

---

## H2 BotAdmin 同级权限保护

**当前问题：**
`/whitelist` 和 `/blacklist` 的 `permission=Level.BotAdmin`（[bot/plugins/admin.py:341-353](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py#L341-L353)），而 `_apply` 只检查 `target_level >= Level.Owner`（[bot/plugins/admin.py:80-81](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py#L80-L81)）。一个 BotAdmin 可以 `/blacklist add @另一BotAdmin`，目标用户全局被拉黑、所有群里若没有 group-level 权限即被静默屏蔽。

**风险：**
- 管理员之间互相降权、拉黑的横向越权（peer privilege escalation）。
- 紧急情况下 Owner 不在线时无法快速止损。
- 违反 permission.md §5"Bot Admin 拥有跨群的机器人管理权限"——同级之间不应能互相操作。

**当前状态：** 未修复。

**未来方向：**
在 `_apply` 中加 same-level 保护——若 `target_level >= operator_level`（且 operator 不是 Owner），拒绝。或更简单：把 `/whitelist` `/blacklist` 的 target 限制为 `target_level < Level.BotAdmin`，对 BotAdmin 的操作只能由 Owner 通过 `/botadmin remove` 完成。

**关联文件：** [bot/plugins/admin.py](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py)

---

## H3 Dispatcher 修改 event.message

**当前问题：**
shortcut 命中后 dispatcher 直接 mutate 共享 event 对象（[bot/plugins/command_dispatcher.py:93-94](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py#L93-L94)）：

```python
event.message.clear()
event.message.extend(new_msg)
```

NoneBot2 把同一 `MessageEvent` 分发给所有 priority 的 matcher（dispatcher 用 `block=False`）。

**风险：**
- 影响其他 matcher 获取原始消息。
- 文本日志/审核日志记录的不是用户实际发送内容。
- 未来在 dispatcher 之后注册的 matcher 会读到被改写的消息。
- WebUI 接入后通过事件总线回放会读到错误内容。

**当前状态：** 未修复。

**未来方向：**
使用 `Message.copy()` 保存原消息，shortcut 展开结果存到 `state["expanded_message"]` 传给 handler，而不是原地修改 `event.message`。

**关联文件：** [bot/plugins/command_dispatcher.py](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py)

---

## H4 白名单能力与设计不一致

**当前问题：**
[docs/design/database.md §3.1](file:///c:/AphrosyneData/CommunityOS/docs/design/database.md) 明确白名单 = "豁免批量清人 / 防撤回 / 冷却豁免"，但实现中：

- [bot/plugins/auto_recall.py:74](file:///c:/AphrosyneData/CommunityOS/bot/plugins/auto_recall.py#L74) 只对 Owner 豁免。
- [bot/plugins/command_dispatcher.py:122](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py#L122) 只对 Owner 豁免冷却。
- [bot/services/permission.py:11-14](file:///c:/AphrosyneData/CommunityOS/bot/services/permission.py#L11-L14) 注释把白名单降级为"豁免批量清人（后续轮次）"。

**风险：**
- 部署者读 database.md 会认为白名单有"防撤回"作用，部署后才发现没有。
- spec compliance 偏差未在任何文档记录。

**当前状态：** 未修复，未在 design doc 同步。

**未来方向：**
二选一——
1. 实现 `is_whitelisted(user_id, group_id)` 并在 auto_recall、dispatcher 冷却处加豁免，统一为 whitelist exemption service。
2. 更新 database.md §3.1，明确声明"白名单的防撤回/冷却豁免推迟到 Round 6+ 实现"。

无论哪种，design doc 必须与代码一致。

**关联文件：** [bot/plugins/auto_recall.py](file:///c:/AphrosyneData/CommunityOS/bot/plugins/auto_recall.py), [bot/plugins/command_dispatcher.py](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py), [docs/design/database.md](file:///c:/AphrosyneData/CommunityOS/docs/design/database.md), [docs/design/permission.md](file:///c:/AphrosyneData/CommunityOS/docs/design/permission.md)

---

## H5 缺少 Dispatcher 集成测试

**当前问题：**
[tests/](file:///c:/AphrosyneData/CommunityOS/tests/) 目录全部 7 个测试文件都是 [bot/services/database.py](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py) Repository 层的单元测试，**没有一个测试**覆盖：

- command dispatcher 流程测试
- permission 流程测试
- plugin 行为测试

具体缺口：
- 黑名单用户发送命令 → 被静默拦截
- 权限不足用户发送命令 → 写 `permission_denied` 文本日志、不写 command_log
- shortcut 命中后 `command_log.command_name` 记录的是最终命令名（Q8-A 核心决策）
- `MatcherException` 被当 success 写入 command_log
- 私聊 `group_id=0` 传到 `log_command`
- Owner 冷却豁免生效
- 黑名单用户不消耗冷却

[docs/developer/testing.md §3](file:///c:/AphrosyneData/CommunityOS/docs/developer/testing.md) 承诺的 `MockBot` / `MockEvent` fixture 在 [tests/conftest.py](file:///c:/AphrosyneData/CommunityOS/tests/conftest.py) 中**完全没实现**，只有 `tmp_db_path` 和 `db`。

**风险：**
- testing.md §5 把 Permission Service 和 Command System 列为优先级 1/2，但 Command System 完全没测。
- 进入 WebUI 阶段后回归风险高，WebUI 会调用同样的 Service 层。

**当前状态：** 未修复。

**未来方向：**
- 在 [tests/conftest.py](file:///c:/AphrosyneData/CommunityOS/tests/conftest.py) 实现 testing.md §3 承诺的 `MockBot` / `MockEvent` fixture。
- 新增 [tests/integration/](file:///c:/AphrosyneData/CommunityOS/tests/) 目录。
- 至少补 3-5 个集成测试：黑名单拦截、权限拒绝路径、shortcut→final-name 日志、MatcherException 路径、私聊 group_id=0。

**关联文件：** [tests/conftest.py](file:///c:/AphrosyneData/CommunityOS/tests/conftest.py), [docs/developer/testing.md](file:///c:/AphrosyneData/CommunityOS/docs/developer/testing.md)

---

# 4. Medium Priority Debt

Round 6 期间处理。

## M1 全局黑名单可被群级权限穿透

**当前问题：**
[bot/services/database.py:283-304](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L283-L304) `get_permission` 用 `MAX(level)` 聚合全局+群级。用户有 `group_id=0, level=-1`（全局黑名单）且 `group_id=A, level=3`（A 群 BotAdmin）时，在 A 群查询返回 `MAX(-1, 3)=3`，黑名单失效。

**风险：**
- 紧急拉黑一个在多群有 group-level 权限的用户，必须在每个群单独 `/groupadmin remove`。
- 紧急响应失效。

**未来方向：**
在 database.md 增加一节"黑名单语义限制"，明确全局黑名单不覆盖群级权限。或引入"硬黑名单"概念（特殊的 level=-1 + group_id=-1 全局生效不可被 MAX 覆盖）。

---

## M4 seed_from_env 权限种子行为需要明确

**当前问题：**
[bot/services/permission.py:105-128](file:///c:/AphrosyneData/CommunityOS/bot/services/permission.py#L105-L128) 每次启动都 `set_permission(OWNER, 0, 9)` 和 `set_permission(admin_id, 0, 3)`。如果运维在运行时 `/botadmin remove @某admin`（level=0），下次重启 `seed_from_env` 会把他重新种子为 level=3。

**风险：**
- 运行时降级会在重启后回滚，运维操作不可预期。
- "种子"与"权威源"语义混淆。

**未来方向：**
二选一——
1. 文档明确"ADMINS 是种子源，运行时降级会在重启后回滚"。
2. `seed_from_env` 改为"仅在记录不存在时插入"（INSERT OR IGNORE 语义）。

---

## M5 database.setup() 失败恢复

**当前问题：**
[bot/services/database.py:65-84](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L65-L84) 如果 `_run_migrations` 抛异常，`self._conn` 已经赋值但连接处于未知状态（可能 PRAGMA 没设、迁移半应用）。再次调 `setup()` 直接 `return`，跳过迁移重试。

**风险：**
- 本地调试时若 try/except 包住 `database.setup()` 重试，会得到"看似就绪但实际未迁移"的连接。
- 半升级状态比不升级更危险。

**当前状态：** 已在 Round 4 修复（见 §9）。

---

## M8 mute.py 未检查 target 级别

**当前问题：**
[bot/plugins/mute.py:140](file:///c:/AphrosyneData/CommunityOS/bot/plugins/mute.py#L140) 只 `if await is_owner(target_id)` 拦 Owner。一个 BotAdmin 调用 `/禁言 @另一BotAdmin` 会成功执行。

**风险：**
- 与 H2 同源，但 mute 直接产生平台副作用（真禁言），影响更直接。

**未来方向：**
在 mute 前 `target_level = await get_level(target_id, group_id)`，若 `target_level >= operator_level` 且 operator 非 Owner 则拒绝。

---

## M9 _migrations.applied_at 时间戳格式不一致

**当前问题：**
[bot/services/database.py:91-96](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L91-L96) 用 SQLite 的 `datetime('now')`（UTC 无时区），其它表用 `_now_iso()`（本地带时区）。[docs/design/database.md §2](file:///c:/AphrosyneData/CommunityOS/docs/design/database.md) 明确说"与 SQLite datetime('now')（UTC 无时区）不可直接比较"。

**风险：**
- 当前只用于人读，不影响查询。
- 未来按迁移时间筛选会踩坑。
- 破坏"统一时间戳格式"原则。

**当前状态：** 已在 Round 1 修复（见 §9）。

---

# 5. Documentation Debt

文档与实现脱节。

## D1 permission.md 落后于实现

**当前问题：**
[docs/design/permission.md §3](file:///c:/AphrosyneData/CommunityOS/docs/design/permission.md) 仍是"User / Admin / Owner 三级权限模型"。

实际已经升级为：
- Blacklist (-1)
- User (0)
- Whitelist (1)
- GroupAdmin (2)
- BotAdmin (3)
- Owner (9)

permission.md §11 "当前版本不包含：黑名单、白名单、群级角色、动态权限修改、数据库存储"——这些 Round 3 已全部实现，文档未同步。

**风险：**
- 新协作者基于错误文档理解权限模型。
- 安全审查者无法对照文档判断实现是否合规。

**当前状态：** 已在 Round 1 修复（permission.md v1.1，见 §9），Round 5 确认同步。

---

## D2 testing.md 承诺的 fixture 与目录未落地

**当前问题：**
[docs/developer/testing.md §3](file:///c:/AphrosyneData/CommunityOS/docs/developer/testing.md) 声明：
- `MockBot` fixture
- `MockEvent` fixture
- `tests/integration/` 目录

但 [tests/conftest.py](file:///c:/AphrosyneData/CommunityOS/tests/conftest.py) 中**完全没有实现** MockBot/MockEvent，只有 `tmp_db_path` 和 `db`。tests/integration/ 目录不存在。

**风险：**
- 文档承诺不兑现，新协作者按文档写集成测试会失败。
- H5 的 dispatcher 集成测试无法写。

**未来方向：**
- 在 conftest.py 实现 MockBot / MockEvent fixture（按 testing.md §3 模板）。
- 创建 tests/integration/ 目录。
- 与 H5 修复同步进行。

**当前状态：** 已在 Round 2 修复（conftest.py 实现 mock_bot / make_group_event / make_private_event，tests/integration/ 目录已创建，见 §9），Round 5 确认同步。

---

## D3 roadmap / command-system 命令名称变更未记录

**当前问题：**
[docs/design/database-roadmap.md Round 3](file:///c:/AphrosyneData/CommunityOS/docs/design/database-roadmap.md) 写的是 `/admin add` `/blacklist add`，但实际命令名是 `/botadmin` `/blacklist`，且别名已改为英文缩写（sba/sga/swl/sbl/spm）。

[docs/design/command-system.md](file:///c:/AphrosyneData/CommunityOS/docs/design/command-system.md) 也未记录这些变更。

project_memory 已记录"Admin commands use English aliases: sba (botadmin), sga (groupadmin), swl (whitelist), sbl (blacklist), spm (perm)"，但 design doc 未同步。

**风险：**
- 文档与实际命令名不一致。
- 用户/运维按文档使用错误命令名。

**未来方向：**
- database-roadmap.md Round 3 段落更新命令名。
- command-system.md §11 已实现命令列表同步实际名称与别名。

**当前状态：** 已在 Round 5 修复（见 §9）。

---

# 6. Low Priority Debt

后续优化项，无即时风险。

## L1 database logger 落到 bot.log

[bot/services/database.py:36](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L36) `get_logger("database")`，但 [bot/services/logger.py:24-30](file:///c:/AphrosyneData/CommunityOS/bot/services/logger.py#L24-L30) 的 `_DOMAIN_FILES` 没有 "database" 项，DB 异常混进 bot.log。

**当前状态：** 已在 Round 4 修复（见 §9）。

---

## L2 ADMINS env 解析无 try/except

[bot/services/config.py:32](file:///c:/AphrosyneData/CommunityOS/bot/services/config.py#L32) `int(x.strip())` 对 `"abc"` 抛 ValueError，模块加载失败 → bot 起不来。

**当前状态：** 已在 Round 4 修复（见 §9）。

---

## L3 Migration 文件名排序依赖零填充

[bot/services/database.py:105-109](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L105-L109) `sorted(key=lambda f: f.name)` 字典序。

**当前状态：** 已在 Round 4 文档化（见 §9，database.md §5 命名规范）。

---

## L4 expires_at 字符串比较时区假设未文档化

`get_permission` 的 `expires_at > ?` 比较依赖 `expires_at` 与 `_now_iso()` 用相同时区偏移。

**当前状态：** 已在 Round 4 文档化（见 §9，database.md §5 时间戳约束）。

---

## L5 details JSON 序列化用 default=str 隐藏 bug

[bot/services/database.py:373-374](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L373-L374) 把不可序列化对象转字符串，可能掩盖插件传错对象的 bug。

**未来方向：** 可接受，或改为严格序列化。

---

## L6 shortcut.replace 无 @ 时生成 [CQ:at,qq=]

[bot/plugins/command_dispatcher.py:82](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py#L82) 无 @ 时 `at_target=""`，生成 `[CQ:at,qq=]`。

**未来方向：** 无 @ 时跳过替换或返回 None。

---

## L7 auto_recall 与 dispatcher 都 block=False

[bot/plugins/auto_recall.py:62](file:///c:/AphrosyneData/CommunityOS/bot/plugins/auto_recall.py#L62) priority=0，[bot/plugins/command_dispatcher.py:61](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py#L61) priority=1，同一条消息若同时命中关键词和命令会双重处理。

**未来方向：** Low，实际场景同时命中概率低。

---

## L8 command_log / moderation_log 缺索引

`action` / `command_name` 无索引，按字段查询是全表扫描。

**当前状态：** 已在 Round 4 修复（见 §9，新增迁移 002）。

---

## L9 _apply 中 target_level 只查全局

[bot/plugins/admin.py:80](file:///c:/AphrosyneData/CommunityOS/bot/plugins/admin.py#L80) 传 `group_id=0`，不查 group-level。

**未来方向：** defense-in-depth 应查 MAX。

---

## L10 friend.py 不写 relationship 表

[bot/plugins/friend.py:32-35](file:///c:/AphrosyneData/CommunityOS/bot/plugins/friend.py#L32-L35) 只 upsert_user，无好友关系记录。database.md 也没有 friends 表。

**未来方向：** Low，与 Round 6 关系不大。

---

## L11 record_membership UPSERT 可合并

[bot/services/database.py:219-233](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L219-L233) UPDATE→INSERT 模式可用 `INSERT ... ON CONFLICT DO UPDATE` 合并为单语句。

**未来方向：** Low，单连接 async 下无并发问题。

---

## L12 测试 time.sleep(0.01) 依赖时间精度

[tests/unit/test_user.py:46](file:///c:/AphrosyneData/CommunityOS/tests/unit/test_user.py#L46) `_now_iso()` 精度到秒，0.01s sleep 不够，该测试可能偶尔失败。

**未来方向：** mock `datetime.now`。

---

## L13 dispatcher cooldown 在 permission check 之前消耗

[bot/plugins/command_dispatcher.py:122-141](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py#L122-L141) 顺序是 cooldown → permission。权限不足时 cooldown 已被消耗。

**未来方向：** 文档化或交换顺序（permission 失败不消耗 cooldown）。

---

## L14 _cooldowns 内存字典无 TTL

[bot/plugins/command_dispatcher.py:50](file:///c:/AphrosyneData/CommunityOS/bot/plugins/command_dispatcher.py#L50) 只在 [bot/services/cleanup.py:29-37](file:///c:/AphrosyneData/CommunityOS/bot/services/cleanup.py#L29-L37) 每 10 分钟清理 30 秒以上的过期项，活跃用户的旧 cooldown_level 永不删除。

**未来方向：** Low，长期运行内存增长缓慢。

---

# 7. Deferred

暂时不处理。这些问题当前不会阻塞功能开发，触发条件出现时再评估。

## X1 migration 原子事务优化

**当前状态：**
[bot/services/database.py:134-145](file:///c:/AphrosyneData/CommunityOS/bot/services/database.py#L134-L145) `executescript` 会自动 commit 自己的语句，迁移 SQL 应用与 `_migrations` 记录不在同一事务。

**触发条件：**
迁移脚本数量 > 5 个，或出现非幂等迁移（如 ALTER TABLE）。

**未来方向：**
把迁移脚本和 `_migrations` 记录放进同一个显式事务，或文档明确"`executescript` 会自动提交，幂等性靠 IF NOT EXISTS 保证"。

---

## X2 timestamp 格式统一

**当前状态：**
`_migrations.applied_at` 用 `datetime('now')`（UTC 无时区），其它表用 `_now_iso()`（本地带时区）。见 M9。

**触发条件：**
需要按迁移时间筛选或跨表 join 时间字段。

**未来方向：**
统一为 ISO 8601 含时区格式。

---

## X3 command query 性能优化

**当前状态：**
每条命令 3 次 SELECT + 1 次 INSERT。见 M6。

**触发条件：**
单日命令调用量 > 10 万次，或 WebUI 高频查询。

**未来方向：**
合并查询、引入查询缓存。

---

## X4 audit 查询索引

**当前状态：**
`moderation_log.action` / `command_log.command_name` 无索引。见 L8。

**触发条件：**
单表记录数 > 10 万行，或 WebUI 提供按 action/command_name 筛选查询。

**未来方向：**
加 `idx_mod_log_action` / `idx_cmd_log_command_name`。

---

## X5 WebUI 前置优化

**当前状态：**
WebUI 未接入，相关优化暂缓。

**触发条件：**
Round 6 WebUI 开发启动。

**未来方向：**
- 统一 Service 层 API（消除 plugin 直接调 database 的越界）。
- 引入查询缓存层。
- HTTP 请求与 QQ 消息共享 event loop 的并发审查。

---

# 8. 关联文档

- [Database Round 1-5 Code Review](file:///c:/AphrosyneData/CommunityOS/docs/) （2026-07-29 会话记录）
- [总体架构](architecture.md)
- [数据库设计](design/database.md)
- [数据库实施路线](design/database-roadmap.md)
- [权限服务](design/permission.md)
- [指令系统](design/command-system.md)
- [测试规范](developer/testing.md)
- [插件开发指南](developer/plugin-development.md)

---

# 9. 已解决

已处理完成的技术债，保留历史可追溯。

## Round 1: Permission Security Hardening（2026-07-29）

| 编号 | 标题 | 解决方式 | 提交 |
|------|------|----------|------|
| H1 | Owner 保护依赖数据库状态 | DB 层 `set_permission` 加 `user_id == OWNER 且 level != 9` 抛 `PermissionError`；命令层保留显式检查 | fix/permission-security-hardening |
| H2 | BotAdmin 同级权限保护 | `admin.py _apply` 加 `target_level >= operator_level`（operator 非 Owner）拒绝逻辑；`handle_perm` clear 子命令同步 | fix/permission-security-hardening |
| M2 | set_permission 缺少 level 范围校验 | `set_permission` 开头校验 `level ∈ [-1, 9]`，超出抛 `ValueError`；常量 `LEVEL_MIN/LEVEL_MAX` 定义在 database.py | fix/permission-security-hardening |
| M3 | clear_user_permissions Owner 防护下沉数据库层 | `clear_user_permissions` 内部 `user_id == OWNER` 抛 `PermissionError` | fix/permission-security-hardening |
| M9 | _migrations.applied_at 时间戳格式不一致 | `applied_at` 列去除 `DEFAULT datetime('now')`，INSERT 时显式传 `_now_iso()` | fix/permission-security-hardening |

文档同步：[permission.md](design/permission.md) v1.1、[database.md](design/database.md) v0.2。
测试新增：[tests/unit/test_permission_security_hardening.py](tests/unit/test_permission_security_hardening.py)（13 个用例，覆盖 M2/H1/M3/M9）。

## Round 2: Dispatcher Reliability（2026-07-29）

| 编号 | 标题 | 解决方式 | 提交 |
|------|------|----------|------|
| H3 | Dispatcher 修改 event.message | shortcut 展开用新 Message 对象替换 event.message，dispatch 结束在 finally 块恢复原始引用，避免污染后续 matcher | fix/dispatcher-reliability |
| H5 | 缺少 Dispatcher 集成测试 | conftest.py 实现 MockBot/MockEvent fixture；新增 tests/integration/ 目录与 8 个集成测试覆盖黑名单拦截/权限拒绝/shortcut/私聊/冷却豁免 | fix/dispatcher-reliability |
| M6 | dispatcher 多次权限查询优化 | 单次 get_level 替代 is_blacklisted + is_owner + check_permission 三次 SELECT，本地判断 blacklist/owner/required | fix/dispatcher-reliability |

文档同步：[testing.md](developer/testing.md) fixture 模板已实现。
测试新增：[tests/integration/test_dispatcher.py](tests/integration/test_dispatcher.py)（8 个用例，覆盖 H3/H5/M6）。

## Round 3: Audit Service Refactor（2026-07-31）

| 编号 | 标题 | 解决方式 | 提交 |
|------|------|----------|------|
| TD1 / TD2 (M7) | audit log 重复代码抽取 | 新增 [bot/services/audit.py](file:///c:/AphrosyneData/CommunityOS/bot/services/audit.py) 统一封装 `log_moderation` / `log_command` 的 try/except 模板；mute / auto_recall / admin / command_dispatcher 4 处本地 helper 全部移除，改用 audit service | fix/audit-service-refactor |

设计要点：
- audit service 作为薄封装层，参数与 `database.log_moderation` / `database.log_command` 完全对齐（含默认值），仅做异常吞咽 + logger 记录。
- 失败不向上抛出（Q4-A / Q1-A），调用方（插件）无需 try/except 包裹 audit 调用。
- 保持分层架构：audit service 通过 `services.database` 模块级 API 写入，不直接持有连接。

测试新增：[tests/unit/test_audit.py](tests/unit/test_audit.py)（7 个用例，覆盖委托透传 / 默认值 / 异常吞咽 / 调用方不阻塞）。

## Round 4: Database Robustness（2026-07-31）

| 编号 | 标题 | 解决方式 | 提交 |
|------|------|----------|------|
| M5 | database.setup() 失败恢复 | `setup()` 用 try/except 包裹 PRAGMA + 迁移，失败分支调 `_safe_close()` 关闭并清空 `_conn`，重试时不会拿到半升级连接 | fix/database-robustness |
| M6 | dispatcher 多次权限查询优化（标签修正） | Round 2 已修复，本 Round 仅修正 §4 残留条目与 §9 Round 2 表格的标签错误（原误标 M7） | — |
| L1 | database logger 落到 bot.log | `logger.py` `_DOMAIN_FILES` 加 `database` 项，`setup_logging()` 新增 `database.log` handler，DB 异常独立落盘 | fix/database-robustness |
| L2 | ADMINS env 解析无 try/except | `config.py` 抽取 `_parse_int_env` / `_parse_int_list_env`，OWNER/ADMINS/BOT_QQ 解析失败抛带上下文（变量名+非法值）的 `ValueError` | fix/database-robustness |
| L3 | Migration 文件名排序依赖零填充 | [database.md](design/database.md) §5 新增"命名规范"小节，强制 3 位数字前缀（`NNN_描述.sql`）并给出正反例 | fix/database-robustness |
| L4 | expires_at 字符串比较时区假设未文档化 | [database.md](design/database.md) §5 新增"时间戳与 expires_at 比较约束"小节，明确 `expires_at` 必须用 `_now_iso()` 同款格式 | fix/database-robustness |
| L8 | command_log / moderation_log 缺索引 | 新增 [bot/migrations/002_add_audit_indexes.sql](file:///c:/AphrosyneData/CommunityOS/bot/migrations/002_add_audit_indexes.sql) 创建 `idx_mod_log_action` / `idx_cmd_log_command_name`，IF NOT EXISTS 保证幂等 | fix/database-robustness |

设计要点：
- M5 使用新增的 `_safe_close()` 而非直接 `close()`，吞咽关闭异常避免掩盖原始失败原因。
- L1 不改 `database.py` 调用方代码，仅扩展 logger 配置；现有 `get_logger("database")` 自动路由到新文件。
- L2 保持 fail-fast 语义（非法配置仍阻止启动），仅把裸 `ValueError` 升级为带上下文提示。
- L8 索引按 action / command_name 维度，已有的 idx_mod_log_user_time / idx_cmd_log_user_time 保持不变，本迁移只补充筛选维度。

未做（评估后排除出 Round 4 范围）：
- L5（default=str 可接受现状）、L11（UPSERT 合并 Low 无并发问题）、L12（测试 sleep 非数据库鲁棒性）、L14（cooldown TTL 非数据库）。

测试新增：
- [tests/unit/test_database.py](tests/unit/test_database.py) 增加 M5 用例：setup 失败后 `_conn` 为 None、重试可成功、`_safe_close` 吞咽关闭异常。
- [tests/unit/test_config_env_parsing.py](tests/unit/test_config_env_parsing.py) 新增 L2 用例：合法/空 ADMINS、非法 ADMINS 报错、OWNER/BOT_QQ 边界。
- [tests/unit/test_migration.py](tests/unit/test_migration.py) 增加 L8 用例：002 迁移后索引存在。

## Round 5: Documentation Synchronization（2026-07-31）

| 编号 | 标题 | 解决方式 | 提交 |
|------|------|----------|------|
| D1 | permission.md 落后于实现 | permission.md 已在 Round 1 升级到 v1.1（9 级权限模型 + defense-in-depth），Round 5 确认同步无遗漏 | fix/documentation-sync |
| D2 | testing.md 承诺的 fixture 与目录未落地 | conftest.py 已在 Round 2 实现 mock_bot / make_group_event / make_private_event（按 testing.md §3 模板），tests/integration/ 目录已创建，Round 5 确认同步 | fix/documentation-sync |
| D3 | roadmap / command-system 命令名称变更未记录 | [database-roadmap.md](design/database-roadmap.md) v0.3 Round 3 段落更新命令名（/admin→/botadmin 等）、函数名（grant_permission→set_permission）；[command-system.md](design/command-system.md) v1.2 §11 新增管理命令表格（含别名 sba/sga/swl/sbl/spm 与权限要求），冷却术语 Admin→BotAdmin 对齐 9 级模型 | fix/documentation-sync |

设计要点：
- D1/D2 属于"文档债在早期 Round 已实际解决但未在 technical-debt.md 标记"的情况，Round 5 做确认性同步。
- D3 是实质性文档更新：database-roadmap.md 修正历史 Round 3 的命令名/函数名，command-system.md 补全管理命令清单。
- 不涉及代码变更，仅文档同步。

---

# 10. 维护规则

- 新条目录入时机：Code Review、设计评审、运维事件、安全审查。
- 处理完成的条目移至 §9 已解决清单，注明解决日期与提交 hash，不直接删除。
- 优先级变化时更新 §2 表格说明。
- High 条目必须在进入下一开发阶段前处理或显式降级到 Medium。
