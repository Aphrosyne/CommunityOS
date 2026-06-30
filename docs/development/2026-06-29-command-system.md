# 指令系统实现记录

> **日期：** 2026-06-29
> **功能：** 指令系统基础框架 + /help + /status
> **结果：** ✅ 私聊和群聊 @bot 均可正常触发

---

## 设计要点

### 群聊 @bot /cmd 格式

**问题：** 群聊消息 `@bot /help` 和 `@bot/help` 两种写法，`get_plaintext()` 返回不同。

- `@bot /help`（有空格）→ plaintext = ` /help` → strip → `/help` ✅
- `@bot/help`（无空格）→ plaintext = `/help` → strip → `/help` ✅

两种都能正确识别，无需特殊处理。

### 为什么不用 NoneBot2 的 on_command

NoneBot2 自带 `on_command()`，但不能直接满足需求：

- `on_command("help")` 只监听 `/help`，不能做动态分发。
- 我们的 `register()` 模式让插件自主注册，dispatcher 统一分发。

因此选择 `on_message(rule=to_me())` + 手动解析指令前缀。

### Plugin → Service 分层

`/status` 是最早体现分层的指令：

```
用户 → 指令系统 → status plugin → runtime service → 返回
```

- `plugins/status.py` 决定展示哪些字段、如何排版。
- `services/runtime.py` 只负责 `get_uptime()`，不关心谁调用。

后续所有指令都遵循此模式。

### 冷却放在 dispatcher 而非插件

冷却属于基础设施层，不应由每个插件各自实现。dispatcher 统一拦截，插件只处理已通过冷却的请求。

### 版本号同步提醒

每次 SemVer 升级需同步更新三处：

1. `CHANGELOG.md`
2. `bot/.env` — `BOT_VERSION=x.x.x`
3. `bot/.env.example` — `BOT_VERSION=x.x.x`

未来考虑合并为单一 VERSION 文件。
