# Mute Plugin 群禁言指令

> **状态：** 正式
> **版本：** v1.0
> **最后更新：** 2026-07-03

---

## 1. 目标

Mute Plugin 为 CommunityOS 提供基础的手动群禁言能力。

管理员可在群聊中通过 @ 机器人、@ 目标成员和指定时长，对群成员执行禁言；也可通过 @ 目标成员解除禁言。

所有操作尝试、权限拒绝、参数错误和平台调用结果均写入 `moderation.log`，形成可追踪的管理审计记录。

本插件只负责禁言与解除禁言，不承担踢人、撤回消息、群公告、自动审核或其他群管理功能。

## 2. 模块位置

插件位于：

```text
plugins/
└── mute.py
```

Mute Plugin 是独立业务插件。

当前版本不引入通用 `Group Action Service`。插件自行完成指令解析、权限检查、目标保护、平台调用和审计记录。

未来当踢人、撤回消息、群公告等多个群管理插件出现相同的机器人权限检查、目标保护、平台异常处理和审计逻辑时，再考虑抽取：

```text
services/
└── group_actions.py
```

## 3. 当前范围

当前支持：

* 管理员在群聊中禁言一名成员（管理群内免 @bot）；
* 管理员在群聊中解除一名成员禁言；
* 任意用户自禁（`自禁` 指令，可指定时长，1-5 分钟随机，上限 15 分钟）；
* 随机禁言时长（`-r min-max` 参数）；
* 通过 @ 消息段识别目标成员；
* 解析禁言时长（支持中英文混合）；
* 检查操作者权限；
* 检查机器人是否具有群管理权限；
* 检查目标保护规则；
* 写入管理审计日志；
* 成功静默，失败不提示。

当前不支持：

* 永久禁言；
* 批量禁言；
* 自动禁言；
* 关键词审核；
* 图片审核；
* 违规积分；
* 禁言申诉；
* 踢出成员；
* 撤回消息；
* 群公告管理；
* 管理员身份变更；
* 管理面板。

## 4. 指令

管理群内免 @bot 触发，非管理群需 @bot。

```text
禁言 @用户 <时长>
解除 @用户
自禁                     # 任意用户可用，1-5 分钟随机
自禁 3m                  # 指定时长，上限 15 分钟
```

示例：

```text
禁言 @用户 1m
禁言 @用户 10m
禁言 @用户 1h
禁言 @用户 -r 5-15       # 随机 5-15 分钟
禁言 @用户 -r            # 随机 1-10 分钟（默认）
解除 @用户
自禁
```

目标成员通过消息中的 @ 消息段提取。

禁言时长支持中英文混合及随机范围：

```text
30s 1m 10m 1h 1d           # 秒/分/时/天
30秒 1分钟 1小时 1天        # 中文
1m30s 1分30秒              # 组合
-r 5-15                    # 随机 5-15 分钟
-r                         # 随机 1-10 分钟
```

时长必须为正整数，最大 30 天。无时长参数默认 1 分钟。

未 @ 目标成员、@ 多名成员、未提供时长、时长格式错误或时长超出平台允许范围时，插件不执行平台动作，并返回简短提示。

## 5. 权限模型

Mute Plugin 使用 Permission Service 判断操作者权限。

当前规则：

* User 无权执行禁言或解除禁言；
* Admin 可以执行禁言和解除禁言；
* Owner 可以执行禁言和解除禁言；
* Owner 的指令冷却豁免不影响目标保护规则和平台权限检查。

机器人自身必须具有群管理员权限。

机器人不是群管理员、平台未授予禁言权限或平台拒绝动作时，插件不得将操作结果视为成功。

## 6. 目标保护

当前目标保护规则：

* 必须且只能 @ 一名目标成员；
* 不允许禁言或解除禁言机器人自身；
* 不允许禁言或解除禁言 Owner；
* 目标成员必须存在于当前群；
* @ 消息段无法解析目标用户 ID 时拒绝执行；
* 目标保护检查失败时不调用平台动作。

当前版本允许 Admin 操作其他 Admin。

如果后续需要更严格的管理层级，可增加规则：

```text
Owner > Admin > User
```

并限制 Admin 不可操作 Owner 或其他 Admin。

## 7. 禁言时长

Mute Plugin 将用户输入时长转换为秒后传递给平台动作。

内部全部转为秒后调用 `set_group_ban`。最大禁言 30 天（2592000 秒）。

当前版本不支持永久禁言。

解除禁言不需要时长参数。

## 8. 处理流程

### 禁言

```text
管理员在群聊中 @机器人 禁言 @目标成员 <时长>
    ↓
Command System 识别禁言指令
    ↓
Permission Service 检查操作者是否为 Admin 或 Owner
    ↓
从消息 @ 段中提取目标成员
    ↓
检查目标保护规则
    ↓
解析并校验禁言时长
    ↓
检查机器人群管理权限
    ↓
调用平台禁言动作
    ↓
写入 moderation.log
    ↓
回复操作结果
```

### 解除禁言

```text
管理员在群聊中 @机器人 解除禁言 @目标成员
    ↓
Command System 识别解除禁言指令
    ↓
Permission Service 检查操作者是否为 Admin 或 Owner
    ↓
从消息 @ 段中提取目标成员
    ↓
检查目标保护规则
    ↓
检查机器人群管理权限
    ↓
调用平台解除禁言动作
    ↓
写入 moderation.log
    ↓
回复操作结果
```

## 9. 平台动作

Mute Plugin 通过 OneBot 群管理动作执行禁言。

概念接口：

```text
set_group_ban(group_id, user_id, duration)
```

参数说明：

* `group_id`：当前群号；
* `user_id`：目标成员 ID；
* `duration`：禁言秒数。

解除禁言通常通过将 `duration` 设置为 `0` 实现，或使用当前适配器提供的等价动作。

实际动作名称、权限限制、时长上限和返回格式以当前 QQ / OneBot 实现为准。

## 10. 审计日志

所有禁言和解除禁言尝试写入：

```text
logs/
└── moderation.log
```

每条记录至少包含：

```text
action
operator_id
group_id
target_id
result
reason
timestamp
```

禁言成功时额外记录：

```text
duration
```

概念示例：

```text
action=mute operator_id=10001 group_id=123456 target_id=20001 duration=600 result=success
action=unmute operator_id=10001 group_id=123456 target_id=20001 result=success
action=mute operator_id=10001 group_id=123456 target_id=20001 result=denied reason=permission_denied
action=mute operator_id=10001 group_id=123456 target_id=20001 result=denied reason=target_is_owner
action=mute operator_id=10001 group_id=123456 target_id=20001 result=failed reason=bot_not_admin
```

日志不记录群聊消息内容或 @ 消息段原始内容。

## 11. 错误处理

处理原则：

* 未 @ 目标成员或 @ 多名成员：不调用平台动作，记录拒绝原因；
* 禁言时长缺失、格式错误、非正数或超过上限：不调用平台动作，记录拒绝原因；
* 操作者权限不足：不调用平台动作，记录权限拒绝；
* 目标保护规则命中：不调用平台动作，记录拒绝原因；
* 机器人群权限不足：不调用平台动作，记录失败原因；
* 平台动作异常：捕获异常，记录失败，不影响机器人主进程；
* 审计日志写入失败：写入系统日志，但不重复执行平台动作；
* 操作结果回复失败：不回滚已经完成的禁言或解除禁言动作。

## 12. 与其他模块的关系

### Command System

Command System 负责识别禁言和解除禁言指令，并将请求分发给 Mute Plugin。

### Permission Service

Permission Service 负责判断操作者是否具有 Admin 或 Owner 权限。

Mute Plugin 不自行维护管理员名单。

### Logger Service

Logger Service 负责创建和管理 `moderation.log`。

Mute Plugin 通过统一日志接口写入审计事件。

### Member Event Plugin

Member Event Plugin 记录成员加入、主动退出和被移出群聊。

Mute Plugin 记录管理员执行禁言和解除禁言的操作。

两类日志职责不同。

## 13. 帮助显示

禁言指令通过 `register(hidden=True)` 注册到 Command System，不出现在帮助列表。

## 14. 当前版本不包含

当前版本不包含：

* 踢人；
* 撤回消息；
* 自动审核；
* 自动禁言；
* 禁言原因；
* 禁言记录查询；
* 违规次数；
* 批量操作；
* 永久禁言；
* 群级禁言规则；
* 通用群管理动作服务。

## 15. 后续扩展

未来可增加：

* 禁言原因参数；
* 管理员操作查询；
* 违规记录；
* 自动审核触发禁言；
* 更严格的管理员层级保护；
* 群级最大禁言时长；
* 与踢人、撤回等插件共享 `services/group_actions.py`；
* 禁言状态查询。

## 16. 总结

Mute Plugin 是 CommunityOS 的独立群管理插件。

它通过“管理员 @机器人 + 禁言或解除禁言 + @目标成员”的方式执行手动禁言管理，并将所有结果写入 `moderation.log`。

当前版本保持最小职责：只处理禁言与解除禁言，不承担其他群管理或自动审核功能。
