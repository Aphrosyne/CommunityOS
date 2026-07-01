# Changelog

All notable changes to CommunityOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

---

## [Unreleased]

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
