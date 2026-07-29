# Changelog

All notable changes to CommunityOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

---

## [Unreleased]

### Added

- Database Round 5 指令日志结构化记录：新增 `DatabaseManager.log_command()` Repository 函数（含模块级委托），`command_dispatcher.py` 在指令执行成功（result=success）和异常（result=error）时写入 `command_log` 表。
- `command_log` 写入支持 `raw_text` Python 端截断至 200 字符（Q5-A），`raw_text=None` 写入 NULL；私聊 `group_id=0`（Q6-B）；shortcut 命中按最终命令名记录（Q8-A）；运行时 DB 写入失败仅记日志不抛出，不影响指令执行。
- 新增 `tests/unit/test_command_log.py`（12 个用例）：覆盖正常写入、error 结果、未注册用户写入、私聊 group_id=0、raw_text 截断（200/恰好 200/None）、默认 result、多记录排序、按命令名/结果/群查询。

### Changed

- `bot/migrations/001_create_tables.sql`：移除 `command_log` 表 `user_id` 的外键约束（Q1-A）。指令日志是行为审计日志，未注册用户也可执行指令，写入不应依赖 `users` 表存在。
- `bot/plugins/command_dispatcher.py`：接入 `log_command`，用 try/except 捕获 handler 异常；`MatcherException`（NoneBot 控制流如 finish/pause/reject）视为正常完成记录 success 并 re-raise，其他异常记录 error。黑名单拦截、冷却期拦截、权限拒绝、未注册命令等不写入 `command_log`（Q2-A/Q3-A/Q4-A）。
- `docs/design/database.md`：§3.2 `command_log` 更新字段说明（私聊 group_id=0、raw_text 截断 200、无 FK 约束、不记录的状态、shortcut 处理、写入失败处理）。

---

### Added (Round 4)

- Database Round 4 审核日志结构化记录：新增 `DatabaseManager.log_moderation()` Repository 函数（含模块级委托），`mute.py`（禁言/解禁/自禁/拒绝禁言）、`auto_recall.py`（违禁词自动撤回成功与失败）、`admin.py`（权限设置成功与拒绝）接入写入 `moderation_log` 表。
- `moderation_log` 写入支持 `details` 字段 JSON 序列化（`json.dumps(ensure_ascii=False, default=str)`），`details=None` 写入 NULL；运行时 DB 写入失败仅记日志不抛出，不影响业务流程。
- 新增 `tests/unit/test_moderation_log.py`（11 个用例）：覆盖正常写入、系统操作（operator_id=0）、全局权限记录、details=NULL、JSON 序列化往返、不存在 user_id/operator_id 仍能写入、多记录排序、全 action 值域、按用户/群/action 查询。

### Changed (Round 4)

- `bot/migrations/001_create_tables.sql`：移除 `moderation_log` 表 `user_id`、`operator_id` 的外键约束（Q1-A）。审计日志优先级高于数据完整性约束，保证被操作用户不存在或系统操作（operator_id=0）时仍能写入。
- `docs/design/database.md`：§3.2 `moderation_log` 更新 action 值域（mute/unmute/mute_denied/auto_recall/permission_set/permission_denied），补充无 FK 约束、JSON details、不记录常规权限拒绝的设计说明；§5 修正迁移文件名；§6 接入计划对齐 database-roadmap.md（Round 3=权限系统，Round 4=审核日志）。

---

## [1.1.1] - 2026-07-08

### Fixed

- `setup.bat` 遗漏 `runtime.json` 复制步骤：新安装时不会从 `runtime.example.json` 创建 `runtime.json`，导致运行时配置服务回退到示例值。新增 runtime.json 复制逻辑，并在完成提示中增加编辑 runtime.json 的说明。

---

## [1.1.0] - 2026-07-08

### Added

- 配置热更新：新增 `reload` / `重载` 指令（Owner 专用，hidden 不显示在 help），运行期重新加载 `runtime.json`、`keywords.json`、`shortcuts.json` 三个配置文件，无需重启。
- 运行时配置服务 `services/runtime_config.py`：管理可在运行期变更的配置项，提供 `get(key)` 函数访问和 `reload()` 重载。
- 配置文件 `bot/config/runtime.json`（gitignored）+ `runtime.example.json` 示例。

### Changed

- 5 项配置从 `.env` 迁移至 `runtime.json`（JSON 格式，`SELF_MUTE_REPLIES` 从 `|` 分隔字符串改为 JSON 数组）：
  - `GREETING_REPLY`（greet 插件）
  - `IMAGE_DECODE_URL`（publish 插件）
  - `FRIEND_VERIFY_ANSWER`（friend 插件）
  - `SELF_MUTE_REPLIES`（mute 插件）
  - `URL_AUTOCOMPLETE_PREFIX`（auto_complete 插件）
- 上述 5 个插件改为通过 `runtime_config.get()` 函数访问配置值，确保热更新立即生效（避免 `from config import X` 的导入引用陈旧问题）。
- `services/shortcut.py` 的 `reload()` 返回值从 `None` 改为 `tuple[bool, str]`，统一与其他 reload 函数的返回格式。
- `services/message_rule.py` 新增公开函数 `reload_keywords()`，返回 `tuple[bool, str]`。

### Removed

- `.env` 和 `.env.example` 移除上述 5 项配置项（保留注释说明已迁移）。
- `services/config.py` 移除上述 5 项配置的读取代码。

---

## [1.0.4] - 2026-07-08

### Fixed

- 指令误触发：`帮助 xxx`、`状态 xxx` 等"指令+空格+聊天内容"被错误触发为指令。新增 `accepts_args` 参数规则（`False` 纯指令 / `True` 任意参数 / `Sequence[str]` 参数白名单），`help` 限制为只接受 `图片` 参数。
- 群聊专属命令在私聊中消耗冷却：`禁言`、`自禁` 在私聊发送会进入 handler 后静默 return 但冷却已被写入。新增 `group_only` 参数，dispatcher 在冷却写入前校验场景，私聊直接忽略。

### Changed

- `register()` 新增 `accepts_args` 和 `group_only` 两个参数，统一控制命令的参数规则和适用场景。
- `help.py` 文档字符串清理未实现的参数说明（`help publish / 帮助 混淆`）。
- 移除 `command_dispatcher.py` 中未使用的 `to_me` 导入。

---

## [1.0.3] - 2026-07-04

### Fixed

- `.env.example` 中 `GREETING_REPLY` 移除具体昵称，改用通用占位符。

---

## [1.0.2] - 2026-07-04

### Fixed

- 计数类消息（已接收 N 张）从节流中移除，改用防抖播报：1.5s 内无新图只报一次最终数。

---

## [1.0.1] - 2026-07-04

### Fixed

- 群聊引用消息自动填入 @发送者后「解图」无法触发（移除 `to_me()` 要求，有回复即匹配）。
- 部署文档 NapCat 配置拆分为 URL 和 Token 两个字段。

---

## [1.0.0] - 2026-07-04

### Added

- 部署指南（`deployment.md`）、一键安装（`setup.bat`）、一键启动（`start.bat`）。
- 总体架构文档 v1.0（中英双语）、README 更新。
- `.env.example` 补全 `ONEBOT_ACCESS_TOKEN`。

### Changed

- 版本号升至 1.0.0 正式版。

---

## [0.21.0] - 2026-07-04

### Fixed

- `eval()` 代码注入漏洞：SUPERUSERS 改用 `json.loads()`。
- 发布失败后 session 未清理：`complete(session)` 前置。
- FileCache 同步 I/O 阻塞事件循环：改为 `asyncio.to_thread`。
- obfuscate/deobfuscate CPU 密集阻塞事件循环：改为 `asyncio.to_thread`。
- shortcut 翻译后 event.message 未清空导致 handler 收到污染输入。
- shortcut 纯 @ 码时 IndexError 崩溃。
- keywords.json 解析失败静默失效无日志。
- auto_recall 无频率限制：加 5 秒冷却。
- 存储服务 storage.py + aiofiles 死代码删除。

### Added

- 定期内存清理（`services/cleanup.py`）：每 10 分钟回收过期 cooldown/throttle/session 条目。
- `DEBUG_NONEBOT` 开关：控制 NoneBot2 框架日志。

### Changed

- 抑制 httpx/httpcore 的 HTTP 请求日志输出。
- 抑制 nonebot 标准 logging 的 INFO 日志。
- loguru 格式从 Python logging 格式改为原生格式。


### Added

- 网址自动补全指令（`尾号 <数字ID>`）：拼接前缀返回完整 N 网链接。

---

## [0.20.0] - 2026-07-04

### Added

- 违禁词自动撤回（`plugins/auto_recall.py`）：管理群内命中关键词自动删除。
- 违禁词分群配置（`keywords.json`，支持 `*` 全局 + 群号专属）。
- `违禁词` 查询指令：Admin 列出当前群关键词。
- Message Rule Service 设计文档（`message-rule-service.md` v1.0）。

---

## [0.19.1] - 2026-07-03

### Added

- 自禁成功回复随机语句（`SELF_MUTE_REPLIES`，`.env` 配置，管道符分隔），@用户后发送。

---

## [0.19.0] - 2026-07-03

### Added

- 快捷映射分群配置（`shortcuts.json` 支持 `"*"` + 群号）。
- `映射` 指令：Admin 查询当前群快捷映射，QQ 号显示为群昵称。
- 自禁指令（`自禁`）：任意用户可用，支持指定时长，上限 15 分钟。
- 随机禁言时长（`-r` 参数）。
- 禁言默认时长 1 分钟，别名「解除」。

### Changed

- 帮助命令列表只显示别名。
- 权限拒绝静默（不回复用户）。
- `shortcuts` / `映射` 隐藏于帮助（Admin 专用）。

---

## [0.18.1] - 2026-07-03

### Changed

- 权限拒绝不再回复用户提示，静默拒绝。

---

## [0.18.0] - 2026-07-03

### Added

- Message Rule Service（`services/message_rule.py`）：统一消息规则匹配与路由。
- 管理群内低权限命令（<2）无需 @bot 即可触发。
- 禁言默认时长 1 分钟，别名「解除」替代「解除禁言」。

---

## [0.17.1] - 2026-07-03

### Changed

- 解图指令和帮助提示增加手机用户勾选原图提醒。

---

## [0.17.0] - 2026-07-03

### Changed

- 图片帮助统一至 `help.py`，三个插件不再各自维护 `help_text`。
- 帮助参数 `帮助 图片处理` → `帮助 图片`。
- 图片三件套增加风控/发送失败用户提示。

---

## [0.16.2] - 2026-07-03

### Changed

- 快捷映射示例增加硬编码 QQ 号格式说明。

---

## [0.16.1] - 2026-07-03

### Added

- 指令快捷映射：`bot/config/shortcuts.json`，全句 → 完整指令，支持 `{at}` 和 `[CQ:at]`。

---

## [0.16.0] - 2026-07-03

### Added

- 禁言指令（`plugins/mute.py`）：`@bot 禁言 @用户 时长` / `@bot 解除禁言 @用户`。
- 时长支持中英文混合：1m/10m/1h/1d/1分钟/1小时/1m30s。
- `register()` 新增 `hidden` 参数，禁言等管理指令不出现在 help 中。

---

## [0.15.1] - 2026-07-03

### Added

- `moderation.log`：管理员操作审计日志，当前记录权限拒绝事件。

---

## [0.15.0] - 2026-07-03

### Added

- 群成员变更日志（`plugins/member.py`）：入群/退群/被踢写入 `member.log`。
- `IMAGE_SUBMIT_GROUPS` 升级为 `MANAGED_GROUPS`，供所有插件共用。

---

## [0.14.0] - 2026-07-03

### Added

- 好友申请自动处理（`plugins/friend.py`）：验证答案匹配自动同意。
- `relationship.log`：记录好友申请及处理结果。

---

## [0.13.2] - 2026-07-02

### Changed

- 发布消息新增 `[解图]` 标记，自动识别不再依赖网址。
- 图片发送超时不再重试（`result:0` 即成功，重试会重复发送）。

### Fixed

- 大图发布后网址改提示语导致自动解图无法触发。
- 群聊引用解图失败时提示添加好友。

---

## [0.13.1] - 2026-07-02

### Fixed

- 群聊引用解图私信发送失败时缺少用户提示。

---

## [0.13.0] - 2026-07-02

### Added

- Cache Service（`services/cache.py`）：通用文件缓存，按总字节数限制，最旧文件淘汰。
- 图片解混淆缓存：`MD5(混淆图) → 原图`，磁盘持久化，重启不丢。
- 缓存文档（`cache.md` v1.0）。

---

## [0.12.1] - 2026-07-02

### Changed

- 图片预检：下载前通过 Range 请求获取尺寸，超限直接拒绝，省带宽。

---

## [0.12.0] - 2026-07-02

### Added

- 图片大小/像素限制：>20MB 或 >20MP 拒绝；>8MP 仅可通过机器人解图。
- `image_obfuscator.check_image_limits()` 统一校验函数。

---

## [0.11.0] - 2026-07-02

### Added

- 发布多群选择：自动查询用户所在启用群，单群自动选，多群用户自选（支持多选）。
- 指令冷却分群独立：不同群之间冷却互不影响。

### Changed

- `IMAGE_SUBMIT_GROUP`（单群号）→ `IMAGE_SUBMIT_GROUPS`（逗号分隔群号列表）。
- `image-pipeline.md` v1.1：更新发布流程、配置项、基础设施。

---

## [0.10.0] - 2026-07-02

### Added

- Permission Service v1.0：三级权限（User/Admin/Owner），统一检查接口。
- 命令权限控制：`register()` 支持 `permission` 参数，dispatcher 分发前检查。
- 指令冷却等级：查询类 3s / 会话启动类 5s / 管理类 10s，由 `.env` 配置。
- Owner 冷却豁免：Owner 跳过全部冷却（指令 + 业务），Admin/User 正常冷却。

### Changed

- 指令冷却从单一全局值改为三级配置（L0/L1/L2）。
- `command-system.md` v1.0 正式版。
- `permission.md` v1.0 正式版。

### Removed

- `IMAGE_COOLDOWN` 死配置（旧 image_submit.py 残留）。

---

## [0.9.0] - 2026-07-01

### Added

- Logger Service 重构：按业务域分日志文件（`bot.log` / `command.log` / `image.log`）。
- 图片三插件补业务日志：进入模式、收图、完成、取消、超时。
- 日志设计文档（`logger.md` v1.0）。

### Changed

- `command_dispatcher` 改为写入 `command.log`，独立于 `bot.log`。
- 图片插件日志统一写入 `image.log`。

---

## [0.8.3] - 2026-07-01

### Fixed

- decode.py 缺少 `from pathlib import Path` 导入。

---

## [0.8.2] - 2026-07-01

### Added

- 帮助系统「帮助 图片处理」参数化详细说明。
- 图片处理流水线文档更新至 v1.0 正式版。

### Changed

- `register()` 支持 `help_text` 参数，插件可附带详细使用说明。

---

## [0.8.1] - 2026-07-01

### Fixed

- 群聊引用解图未加锁，并发可绕过冷却。
- `write_bytes` 异常未捕获导致临时文件泄漏（decode/obfuscate/publish 同步修复）。
- `p.unlink()` 在 finally 中抛异常可掩盖原始错误。

---

## [0.8.0] - 2026-07-01

### Added

- 解混淆插件（`plugins/decode.py`）：三种触发方式 —— 私聊会话「解图」、私聊转发 publish 自动识别、群聊引用+@bot 解图私信返回。
- `image_obfuscator.deobfuscate()`：DEC 模式解混淆函数。
- 公共下载/解混淆函数（`_download_images`、`_deobfuscate_batch`），消除三处分身代码。

---

## [0.7.0] - 2026-06-30

### Added

- 混淆插件（`plugins/obfuscate.py`）：私聊「混淆」指令，发图 → 混淆 → 私聊回复混淆图。
- `asyncio.Lock` 串行化同一用户 session 操作，解决并发收图与完成竞态。

### Fixed

- 发布/混淆 session 图片收集并发竞态（`pop` → `get+clear`，`setdefault` 安全重建）。

---

## [0.6.1] - 2026-06-30

### Fixed

- 发布「完成」并发竞态：处理前取出图片列表防止重复发布。
- publish_rule 群聊泄露：session 激活时私聊限定，群聊消息不再被拦截。
- 超时通知丢失：bot 未连接时保留会话数据，下次扫描再通知。
- 群消息发送失败不再报「✓ 已发布」成功提示。
- 所有图片混淆失败时提示错误，不发空消息。

---

## [0.6.0] - 2026-06-30

### Added

- SessionService（`services/session.py`）：通用多步交互会话管理，支持创建/完成/取消/超时扫描。
- ThrottleService（`services/throttle.py`）：回复节流，按 `(user_id, reply_type)` 控制机器人回复频率。
- Publish 批量发布插件（`plugins/publish.py`）：私聊「发布」进入多步交互模式，收集图片后批量混淆发布。
- 动态发布冷却：`cooldown = min(base + per_image × count, max)`。
- 单次发布图片上限（默认 10 张）。
- 超时扫描后台任务，超时自动通知用户。

### Changed

- image_submit.py 已被 publish.py 替代并移除。
- 发布时间窗口从 5 分钟改为 3 分钟。

### Fixed

- 取消发布后重复回复提示语的 bug。

---

## [0.5.0] - 2026-06-30

### Added

- 命令别名系统：`register()` 支持 `aliases` 参数，同一命令可被多个名称触发。
- `help` 别名「帮助」，`status` 别名「状态」。

### Changed

- **移除指令前缀**：不再使用 `/`，改为消息首词匹配已注册命令。
- `/help` → `help`，`/status` → `status`。
- 未注册命令静默忽略，不再回复「未知命令」提示。
- 指令系统设计文档更新至 v0.3。

---

## [0.4.1] - 2026-06-30

### Fixed

- 图片投稿冷却标记时机错误：三张图并发提交可绕过冷却，改为处理开始时即标记。
- GIF 图片不应进入混淆流程：新增格式检测，GIF 投稿提示不支持。

---

## [0.4.0] - 2026-06-30

### Added

- 指令系统基础框架：命令注册中心（`services/command.py`）、分发器（`plugins/command_dispatcher.py`）。
- `/help` 命令：列出所有已注册命令。
- `/status` 命令：显示运行时间和版本号（Plugin → Service 分层模式的范例）。
- 运行时服务（`services/runtime.py`）：记录启动时间，提供 `get_uptime()`。
- 指令系统设计文档（`command-system.md` v0.2）。
- 开发记录：`2026-06-30-command-system.md`。

### Changed

- 指令触发规则：私聊直接 `/cmd`，群聊必须 `@bot /cmd`。
- 指令统一 30 秒全局冷却。

---

## [0.3.1] - 2026-06-29

### Fixed

- 混淆算法输出为 DEC 而非 ENC，导致网站需点「混淆」而非「解混淆」才能还原。

---

## [0.3.0] - 2026-06-29

### Added

- 图片投稿插件：私聊投稿 → Gilbert 曲线混淆 → 转发到群。
- Gilbert 曲线混淆服务（image_obfuscator.py），numpy 加速。
- 公共服务层：文件存储（storage.py）、定时调度（scheduler.py）。
- 图片处理流水线文档（image-pipeline.md v0.2）。
- 开发记录：2026-06-29-image-pipeline.md。

---

## [0.2.0] - 2026-06-28

### Added

- Bot 框架搭建：NoneBot2 + FastAPI + OneBot V11 适配器。
- 核心/公共服务/插件/平台适配 四层架构。
- greet 插件：被 @ 时自动回复，回复内容由 `.env` 配置。
- 公共服务层：日志（logger.py）、配置（config.py）。
- 开发记录：2026-06-28-bootstrap.md。

---

## [0.1.0] - 2026-06-28

### Added

- 项目初始化，MIT 许可证。
- 核心理念文档（philosophy.md），中英双语。
- 总体架构文档（architecture.md v0.2），中英双语。
- 社区治理框架（governance.md v0.1）。
- 基础项目结构（docs/ bot/ tests/ scripts/）。
