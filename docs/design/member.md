# Member Event Logging 群成员事件日志

> **状态：** 草案
> **版本：** v0.1
> **最后更新：** 2026-07-03

---

## 1. 目标

Member Event Logging 用于记录 CommunityOS 所在群聊中的成员变更事件，为后续群管理、问题追踪和社区运营提供基础审计信息。

当前版本只记录成员加入和离开群聊，不处理管理员身份变化、欢迎消息、入群审核或自动管理动作。

## 2. 范围

当前记录的事件：

* 成员主动加入群聊；
* 成员主动退出群聊；
* 成员被移出群聊。

当前不记录：

* 管理员身份变化；
* 禁言与解除禁言；
* 群名、群公告或群设置变化；
* 成员昵称变化；
* 欢迎消息发送记录；
* 好友申请事件；
* 入群申请审核过程。

好友关系事件继续写入 `relationship.log`，不写入 `member.log`。

## 3. 模块边界

建议实现为独立插件：

```text
plugins/
└── member.py
```

插件只负责：

* 监听群成员变更事件；
* 识别事件类型；
* 提取事件必要字段；
* 仅处理 `MANAGED_GROUPS` 中的群；
* 调用 Logger Service 写入 `member.log`；
* 在平台事件字段缺失或处理异常时写入系统日志。

插件不负责：

* 发送欢迎消息；
* 同意或拒绝入群申请；
* 执行禁言、踢人或其他管理动作；
* 维护成员数据库；
* 判断成员是否违规；
* 管理日志文件。

## 4. 事件模型

每条成员事件至少包含：

```text
event_type
group_id
user_id
timestamp
```

当平台事件提供时，可额外记录：

```text
operator_id
```

字段说明：

* `event_type`：成员事件类型；
* `group_id`：事件发生的群号；
* `user_id`：发生变更的成员；
* `timestamp`：事件发生时间；
* `operator_id`：执行移出操作的管理员或机器人；成员主动退出时为空。

初始事件类型：

```text
member_join
member_leave
member_kick
```

## 5. 处理流程

```text
收到群成员变更事件
    ↓
判断事件类型
    ↓
提取 group_id、user_id、operator_id
    ↓
写入 member.log
    ↓
结束
```

日志写入失败或字段缺失时，不应影响机器人主进程或其他插件。

## 6. 日志

成员事件写入独立日志文件：

```text
logs/
└── member.log
```

概念示例：

```text
event=member_join group_id=123456 user_id=10001
event=member_leave group_id=123456 user_id=10001
event=member_kick group_id=123456 user_id=10001 operator_id=20001
```

日志中不记录：

* 群聊消息内容；
* 用户头像；
* 用户昵称；
* 成员列表快照；
* 不必要的个人资料；
* 入群验证文本。

`member.log` 只作为事件审计记录，不作为成员档案或成员数据库。

## 7. 与其他模块的关系

### Logger Service

`member.log` 由 Logger Service 统一创建和管理。

Member Event Plugin 通过 Logger Service 写入事件，不直接操作日志文件。

### Permission Service

成员事件监听不需要权限判断。

未来若加入成员管理指令，例如查询成员事件或执行踢人操作，权限检查由 Permission Service 负责。

### Relationship Log

好友申请、好友同意和好友关系变化写入 `relationship.log`。

群成员加入、退出和被移出写入 `member.log`。

两类日志不混合。

### Group Configuration

当前版本通过 `.env` 中 `MANAGED_GROUPS` 控制记录范围。仅在受管理的群中发生的事件才写入 `member.log`。

未来如果某个群不需要记录成员事件，可在群配置系统中增加 `member_event_logging_enabled` 开关。

## 8. 错误处理

* 无法识别事件类型：写入 `bot.log`，不写入 `member.log`；
* 缺少 `group_id` 或 `user_id`：写入 `bot.log`，不写入不完整成员事件；
* 缺少 `operator_id`：成员加入或主动退出正常记录；被移出事件记录时省略该字段；
* `member.log` 写入失败：写入 `bot.log`，不重复处理平台事件；
* 插件异常：捕获异常并记录，不影响其他事件处理。

## 9. 当前版本不包含

当前版本不包含：

* 管理员身份变化记录；
* 成员数据库；
* 成员统计；
* 入群欢迎；
* 自动审核；
* 自动禁言；
* 自动踢人；
* 成员积分或等级；
* 成员活跃度追踪；
* 查询成员历史的管理指令。

## 10. 后续扩展

未来可在不改变当前事件模型的前提下增加：

* `admin_promote`；
* `admin_demote`；
* `member_mute`；
* `member_unmute`；
* 成员事件查询指令；
* 按群统计成员加入与离开数量；
* 成员事件保留期限与归档策略。

## 11. 总结

Member Event Logging 是 CommunityOS 的群成员审计基础。

第一版仅记录成员加入、主动退出和被移出群聊三类事件，并统一写入 `member.log`。

它不承担欢迎、审核或自动管理职责，保持事件记录与业务动作分离。
