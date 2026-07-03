# 禁言指令插件

> **日期：** 2026-07-03
> **功能：** 群聊 @bot 禁言/解除禁言 @用户 [时长]
> **结果：** ✅ 禁言和解除禁言可用，全部写入 moderation.log

---

## 设计

`plugins/mute.py`，通过 Command System 注册（`hidden=True`）。

- 权限：Admin+（`permission=1`），冷却等级 2（10s）
- 指令名 `mute`，别名 `禁言`、`解除禁言`
- 内部通过 `startswith("禁言")` / `startswith("解除禁言")` 区分
- 时长解析：s/m/h/d + 秒/分钟/小时/天，中英文混用，正则匹配
- 检查：Owner 保护、机器人管理员权限、时长上限 30 天
- 全部操作结果写入 `moderation.log`

## 踩坑

### 第一版绕过 Command System

最初用 `on_message(rule=to_me())` 自行处理，权限和冷却都在插件内重复实现。后改为通过 `register()` 统一走指令系统，仅 `hidden=True` 隐藏帮助条目。

### 别名注册遗漏

`register("mute", ...)` 只注册了主名称，未加 `aliases=["禁言", "解除禁言"]`，群聊中发送「禁言」无法匹配。补充别名后恢复正常。
