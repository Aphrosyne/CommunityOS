# 配置热更新

> **日期：** 2026-07-08
> **功能：** reload 指令 + runtime.json 运行时配置
> **结果：** ✅ 三类配置文件运行期重载，无需重启

---

## 背景

原有设计中所有配置项集中在 `.env`，修改后必须重启 bot 才能生效。对于回复语、解图网址、好友验证答案等需要频繁调整的运营类配置，重启成本过高——会中断正在进行的图片发布 session、断开 OneBot WebSocket 连接。

本次新增 `reload` 指令，把需要频繁调整的配置项从 `.env` 迁移到独立的 `runtime.json`，运行期可重载。

## 设计

### 分层配置

把配置拆成两层：
- `.env`：启动配置，框架/权限/冷却等，启动时读取不变
- `runtime.json`：运行配置，回复语/网址/答案等，运行期可热更新

### 函数访问 vs 导入式访问

关键决策：运行配置必须用 `runtime_config.get(key)` 函数访问，不能用 `from runtime_config import XXX`。

Python 的 `from module import X` 是创建本地引用，模块内部 reload 后，已导入的引用仍是旧值。函数访问每次读模块级字典最新值，热更新立即生效。

这是本次设计的核心约束，决定了所有使用运行配置的插件必须改造为函数访问。

### 迁移的 5 项配置

| 配置项 | 使用插件 | 原 .env 格式 | 新 JSON 格式 |
|--------|---------|-------------|-------------|
| `GREETING_REPLY` | greet | string | string |
| `IMAGE_DECODE_URL` | publish | string | string |
| `FRIEND_VERIFY_ANSWER` | friend | string | string |
| `SELF_MUTE_REPLIES` | mute | `\|` 分隔 | string[] |
| `URL_AUTOCOMPLETE_PREFIX` | auto_complete | string | string |

`SELF_MUTE_REPLIES` 从 `|` 分隔字符串改为 JSON 数组，更清晰。

### reload 指令

- `reload` / `重载`，permission=2（Owner），hidden=True，accepts_args=False
- 依次调用 `runtime_config.reload()`、`message_rule.reload_keywords()`、`shortcut.reload()`
- 汇总结果回复，每项显示 ✓/✗ 和错误原因
- runtime.json 重载成功时附带 `reload_marker` 字段值，供 Owner 人工确认

### reload_marker

`runtime.json` 中的 `reload_marker` 字段是人工确认机制。Owner 修改配置时同时改这个值（如时间戳、序号），reload 后回复中会显示这个值，对比即可确认热更新确实生效。

## 踩坑

### reload 返回值统一

`services/shortcut.py` 原有 `reload()` 返回 `None`，新增的 `runtime_config.reload()` 和 `message_rule.reload_keywords()` 返回 `tuple[bool, str]`。

为统一调用方处理逻辑，把 `shortcut.reload()` 也改为返回 `tuple[bool, str]`。这是一个 breaking change，但 `shortcut.reload()` 此前无外部调用方，不影响现有功能。

### runtime.json 解析失败的保留策略

`keywords.json` / `shortcuts.json` 解析失败时原有行为是清空为空字典。`runtime.json` 如果也这样处理，运营配置会突然失效（如 `GREETING_REPLY` 变空导致 greet 插件回复空消息）。

因此 `runtime_config.reload()` 在解析失败时**保留旧配置不变**，只返回失败信息。这是与 keywords/shortcuts 的设计差异——运营配置失效影响用户体验，违禁词失效影响审核但可接受临时空值。

### runtime.json gitignore

`runtime.json` 含实际运营数据（如好友验证答案），必须 gitignore。同时提供 `runtime.example.json` 提交到 git，作为模板。

这与 `shortcuts.json` / `keywords.json` 的处理方式一致。
