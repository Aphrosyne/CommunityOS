# SessionService + ThrottleService + Publish 插件

> **日期：** 2026-06-30
> **功能：** SessionService、ThrottleService、Publish 批量发布插件
> **结果：** ✅ 私聊多步交互批量投稿可用

---

## 设计要点

### 三种机制的职责分离

| 机制 | 职责 | 限制对象 |
|------|------|----------|
| Cooldown | 限制用户多久能再次执行功能 | 用户行为 |
| Session | 管理多步交互流程 | 用户状态 |
| Throttle | 限制机器人回复频率 | 机器人回复 |

三者互不隶属，各自独立。以后新增插件直接复用。

### SessionService — 通用多步交互

`services/session.py` 提供 `create/get_active/complete/cancel`。

关键设计：
- 绝对超时（`expires_at`），发消息不重置计时器。
- 后台定时扫描（`get_expired()`）通知超时用户。
- 内存存储，后续可扩展持久化。

### ThrottleService — 回复节流

`services/throttle.py` 提供 `should_reply(user_id, reply_type)`。

关键设计：
- 每个 `(user_id, reply_type)` 独立计时。
- 默认 5 秒沉默窗口。
- 不同类型互不影响——冷却提示被掐了，计数提示照常。

### Publish 自定义匹配规则

`_publish_rule` 同时处理两种场景：
- 用户有活跃 session → 匹配所有消息（收集图片/完成/取消）
- 用户无 session 且私聊 ─ → 只匹配「发布」/「publish」

避免群聊消息误触发 session。

### 动态冷却公式

```
cooldown = min(base + per_image × count, max)
默认：min(30 + 10×N, 90)
```

图越多冷却越长，但不超过 90 秒上限。

---

## 踩坑

### 取消后落到底部提示语

`cancel()` 后没 `return`，代码继续执行到最后的通用提示「发送图片进行投稿……」导致双回复。

**解决：** `cancel()` 后加 `return`。

### session matcher 拦截初始命令

`on_message(priority=0, block=True)` 拦住「发布」，但 session 未创建 → 消息被吞。

**解决：** 改用自定义 `_publish_rule`，未激活时放行「发布」给后续 handler。

### image_submit.py 被 publish 替代

单图投稿插件 `image_submit.py` 已删除，由 `publish.py` 继承其混淆/冷却/转发逻辑。
