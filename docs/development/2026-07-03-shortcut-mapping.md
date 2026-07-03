# 指令快捷映射

> **日期：** 2026-07-03
> **功能：** 全句 → 完整指令映射
> **结果：** ✅ 支持 `{at}` 占位和 `[CQ:at,qq=xxx]` 硬编码

---

## 设计

`services/shortcut.py` 加载 `bot/config/shortcuts.json`（gitignored），提供 `match(text)` 全句匹配。

`command_dispatcher.py` 在普通命令匹配之前先查快捷映射。命中时将翻译后的文本注入 `event.message`，然后正常走指令分发。

支持两种格式：
- `{at}` — 自动替换为消息中第一个 @ 目标的 QQ
- `[CQ:at,qq=xxx]` — 硬编码目标

## 踩坑

### Segment 插入顺序

`event.message.insert(0, seg)` 逐个压入导致顺序反转。改为 `reversed(parts)` 逆序插入保持原文顺序。

### 翻译文本无法被 handler 识别

最初只替换了 `cmd_name`，handler 仍从 `event.get_plaintext()` 读取原始 shortcut 文本。后改为将翻译文本作为 MessageSegment 注入 `event.message`，handler 正常解析。
