# Message Rule Service 消息规则服务

> **状态：** 正式
> **版本：** v1.0
> **最后更新：** 2026-07-04

---

## 1. 目标

Message Rule Service 是 CommunityOS 的公共群消息规则匹配服务。

它监听群消息，根据已注册规则判断消息是否命中，并将结果分发给对应处理模块。当前已用于两类功能：

* 无 @ 的低风险精确指令触发；
* 自动审核规则命中后的消息撤回。

服务本身负责匹配、优先级和分发。命令执行仍由 Command System 负责；自动撤回动作由 Auto Recall / Auto Moderation 模块负责。

## 2. 模块边界

建议目录结构：

```text
services/
└── message_rule.py

plugins/
└── auto_recall.py
```

如实际文件名不同，以当前实现为准。

### Message Rule Service 负责

* 接收群消息事件；
* 忽略不应处理的消息；
* 标准化可匹配文本；
* 按优先级匹配规则；
* 将命中结果交给对应 Handler；
* 控制命中后是否继续向下处理；
* 捕获规则或 Handler 异常，避免影响消息事件主流程。

### Command System 负责

* 命令注册与别名管理；
* 命令权限检查；
* 指令冷却；
* 参数解析；
* 调用对应插件；
* 写入 `command.log`。

### Auto Recall Plugin 负责

* 注册自动审核规则；
* 定义命中后的撤回策略；
* 调用平台撤回消息动作；
* 处理白名单、豁免与频率限制；
* 写入 `moderation.log`；
* 处理平台动作失败。

## 3. 当前范围

当前支持：

* 群消息全局监听；
* `@bot` 显式指令；
* 群消息全局监听（仅 `MANAGED_GROUPS` 中的群）；
* 私聊命令和 `@bot` 显式指令照旧；
* 管理群内低权限命令（permission < 2）免 @bot 触发；
* 固定短语审核匹配（`contains_phrase`）；
* 审核命中后自动撤回原消息并写入 `moderation.log`；
* 违禁词分群配置（`keywords.json`，支持 `*` 全局 + 群号专属）；
* 关键词查询指令（`违禁词`，Admin+，hidden）；
* Owner 豁免自动撤回。

当前不支持：

* 自然语言理解；
* 模糊命令匹配；
* 从普通句子中推断用户意图；
* 正则表达式规则；
* 图片内容识别；
* 自动禁言；
* 自动踢人；
* 自动公开回复；
* 私聊消息审核；
* 任意关键词直接调用任意指令。

## 4. 核心原则

### 4.1 匹配与执行分离

Message Rule Service 只判断消息是否命中规则，不直接执行图片处理、撤回、禁言或其他群管理动作。

```text
群消息
  ↓
Message Rule Service
  ├─ 命令规则命中 → Command System
  └─ 审核规则命中 → Auto Recall Plugin
```

### 4.2 无 @ 指令必须全文精确匹配

无 @ 指令仅在消息标准化后与已注册别名完全一致时触发。

```text
混淆              → 触发
发布              → 触发
解图              → 触发
帮助              → 触发

帮我混淆一下      → 不触发
这个图怎么解图    → 不触发
发布一下          → 不触发
```

服务不应从自然语言聊天中猜测用户是否在下命令。

### 4.3 按权限等级决定是否需 @bot

管理群内，permission < 2 的命令无需 @bot 即可触发（当前包括 help、status、publish、obfuscate、decode、mute、self_mute）。permission >= 2 的命令仍需显式 @bot。

```text
禁言 @用户 1m        → 管理群内可无 @bot 触发
解除 @用户           → 同上（permission=1）
@机器人 短禁 @用户 1m → 非管理群或高权限命令仍需 @bot
```

无 @ 规则的具体范围由 Command System 注册的权限等级决定。

### 4.4 自动审核不调用命令系统

审核规则命中后，Auto Recall Plugin 直接执行预设的审核动作。

自动审核不应把命中消息转换为普通指令，也不应允许配置为“任意关键词 → 任意命令”。

## 5. 消息标准化

规则匹配前，服务对可匹配文本进行有限标准化。

建议标准化范围：

```text
- 去除首尾空白；
- 合并连续空白；
- 保留普通文字顺序；
- 不修改原始消息内容；
- 不改变图片、回复、转发等非文本消息段；
- 原始消息仅由需要它的业务模块使用。
```

标准化文本只用于规则匹配。

未命中消息不记录原始内容，避免将全群聊天变成日志数据。

## 6. 规则模型

每条规则至少包含：

```text
rule_id
match_type
pattern
priority
stop_on_match
handler
```

字段说明：

* `rule_id`：规则唯一标识；
* `match_type`：匹配类型；
* `pattern`：匹配内容；
* `priority`：规则优先级；
* `stop_on_match`：命中后是否停止继续匹配；
* `handler`：接收命中结果的模块或回调。

概念示例：

```python
MessageRule(
    rule_id="command_obfuscate",
    match_type="exact_text",
    pattern="混淆",
    priority=200,
    stop_on_match=True,
    handler=command_dispatcher,
)
```

```python
MessageRule(
    rule_id="moderation_blocked_phrase_001",
    match_type="contains_phrase",
    pattern="示例违规短语",
    priority=100,
    stop_on_match=True,
    handler=auto_recall_handler,
)
```

## 7. 匹配类型

### 7.1 `exact_text`

消息标准化后的全文必须与规则内容完全一致。

适用于：

* 无 @ 低风险指令；
* 帮助入口；
* 明确且无歧义的短语型功能。

```text
pattern: 混淆
message: 混淆
result: matched
```

```text
pattern: 混淆
message: 帮我混淆
result: not_matched
```

### 7.2 `contains_phrase`

消息文本包含固定短语时命中。

适用于：

* 自动审核；
* 明确违规短语；
* 仅记录或通知类规则；
* 自动撤回规则。

`contains_phrase` 应仅用于低歧义、已明确写入群规或管理规则的内容。它不应用于玩笑、讨论语境、常见引用或容易误判的日常表达。

## 8. 消息处理优先级

群消息处理顺序：

```text
1. @bot 显式指令
2. 无 @ 精确低风险指令
3. 自动审核规则
4. 普通消息
```

说明：

* 显式指令优先级最高；
* 无 @ 指令只允许精确别名；
* 自动审核规则在命令路由后执行；
* 未命中规则的消息静默忽略。

当规则 `stop_on_match=true` 时，命中后停止继续向下匹配。

一条消息不得因同一审核规则被重复撤回或重复处罚。

## 9. 无 @ 指令范围

允许无 @ 精确触发的指令应限制为低风险功能。

示例：

```text
混淆
发布
解图
帮助
```

permission >= 2 的命令仍需 @bot（当前无具体命令，为未来预留）。

实际开放别名以 Command System 的注册配置为准。

## 10. 自动撤回规则

自动撤回规则由 Auto Recall Plugin 注册或加载。

每条规则建议包含：

```text
rule_id
group_scope
match_type
pattern
action
enabled
priority
stop_on_match
```

当前 `action` 固定为：

```text
recall
```

概念配置：

```yaml
rules:
  - rule_id: blocked_phrase_001
    group_scope:
      - 123456
    match_type: contains_phrase
    pattern: "示例违规短语"
    action: recall
    enabled: true
    priority: 100
    stop_on_match: true
```

规则应支持按群启用或禁用。未配置规则的群不执行自动撤回。

## 11. 自动撤回保护规则

自动撤回必须包含基础保护边界：

* 忽略非管理群消息；
* 忽略私聊消息；
* Owner 默认不自动撤回（已实现）；
* 一条消息只执行一次撤回；
* 平台撤回失败时不无限重试；
* 自动撤回后默认不公开回复，避免扩大消息传播或造成刷屏。

当前未实现但计划增加：

* Admin 是否豁免以实际配置为准；
* 白名单用户不自动撤回；
* 同一用户短时间内连续命中时遵守频率限制。

如平台无法撤回历史消息或消息已被撤回，记录结果后结束，不执行额外动作。

## 12. 自动撤回流程

```text
收到群消息事件
    ↓
Message Rule Service 检查消息是否可处理
    ↓
处理 @bot 显式指令
    ↓
处理无 @ 精确低风险指令
    ↓
匹配自动审核规则
    ↓
Auto Recall Plugin 检查豁免、白名单与频率限制
    ↓
调用平台撤回消息动作
    ↓
写入 moderation.log
    ↓
结束
```

## 13. 平台动作

Auto Recall Plugin 通过当前 QQ / OneBot 适配器提供的撤回消息动作执行自动撤回。

概念接口：

```text
delete_msg(message_id)
```

实际接口名称、参数、可撤回时间范围和权限限制以当前适配器实现为准。

平台动作失败时，不应假设消息已成功撤回。

## 14. 审计日志

自动撤回相关事件写入：

```text
logs/
└── moderation.log
```

当前日志格式（v1.0 简化版）：

```text
action=auto_recall operator=system group=<group_id> target=<user_id> result=<success|failed> keywords=<命中词1,命中词2>
```

日志不记录完整原始群消息内容。

如确有排查需要，可记录规则 ID、匹配类型和受控的匹配摘要，但不应长期保存完整聊天文本。

无 @ 指令命中与执行结果继续由 Command System 写入 `command.log`。

服务内部异常、规则注册失败或 Handler 异常写入 `bot.log`。

## 15. 错误处理

* 规则格式无效：拒绝加载或注册，并写入 `bot.log`；
* `rule_id` 重复：按当前实现拒绝或覆盖，并写入 `bot.log`；
* Handler 不存在：不执行分发，写入 `bot.log`；
* Handler 抛出异常：捕获异常，写入 `bot.log`，不影响其他消息处理；
* 消息文本为空：不进行文本规则匹配；
* 撤回动作失败：写入 `moderation.log`，不无限重试；
* 审计日志写入失败：写入系统日志，但不重复执行撤回动作；
* 自动撤回后的提示发送失败：不回滚已完成的撤回动作。

## 16. 安全边界

Message Rule Service 是全局群消息入口，必须保持保守。

当前安全边界：

* 不做自然语言理解；
* 不做模糊命令匹配；
* 不允许无 @ 触发管理指令；
* 不允许审核规则任意调用命令；
* 不直接记录所有群聊内容；
* 不对未命中消息回复；
* 不允许自动撤回规则无限重试；
* 高影响自动处罚必须由独立模块实现；
* 自动禁言、踢人等动作不属于当前版本。

## 17. TODO

当前版本暂未实现：

* 白名单用户豁免；
* 审核频率限制与冷却；
* `log_only` 审核动作；
* `notify_admin` 审核动作；
* 管理员确认后撤回；
* 规则命中统计；
* 正则表达式匹配；
* 自动禁言规则；
* 规则热加载；
* 规则命中申诉或人工复核流程。


新增高影响动作前，应先明确误判处理、豁免规则、权限边界和审计要求。

## 18. 后续规划

未来可在不改变职责边界的前提下增加：

* 规则热加载；
* 按群启用/禁用自动撤回；
* 审核规则调试模式；
* 规则命中统计；
* 每日动作上限。

## 19. 总结

Message Rule Service 是 CommunityOS 的公共群消息规则匹配入口。

当前版本支持无 @ 的低风险精确指令，以及固定短语命中后的自动撤回。服务只负责匹配和分发，不直接执行命令或群管理动作。

通过严格的精确匹配、规则优先级、自动撤回保护和独立审计日志，系统可以在不干扰普通聊天的前提下提供基础自动审核能力。
