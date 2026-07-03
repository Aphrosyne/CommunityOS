# Message Rule Service + 管理群免 @bot

> **日期：** 2026-07-03
> **功能：** 消息规则服务 + 管理群低权限命令免 @bot
> **结果：** ✅ 管理群 help/发布/禁言 等无需 @bot

---

## 设计

`services/message_rule.py`：独立消息规则服务，第一版仅提供 `check_command()`——判断消息是否应路由到 Command System。

`command_dispatcher.py` 的自定义 `_rule()` 调用该服务，不再硬编码规则。

管理群（`MANAGED_GROUPS`）内，permission < 2 的命令无需显式 @bot。permission >= 2 的命令仍需 @bot。

## 踩坑

### 注入 @bot segment 方案失败

最初尝试在 `event.message` 中注入 `MessageSegment.at()` 来模拟 @bot，但 `to_me()` 规则不识别后注入的 segment。改为直接在 dispatcher `_rule()` 中判断。

### `event.to_me = True` hack

同样不可靠。最终方案：dispatcher 自定义 rule 调用 `check_command()`，在管理群内主动放行低权限命令。

### 最终架构

不注入、不 hack——dispatcher 的 `_rule()` 调用 `services/message_rule.py` 的 `check_command()`，逻辑集中，易扩展。
