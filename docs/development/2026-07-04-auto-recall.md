# 违禁词自动撤回

> **日期：** 2026-07-04
> **功能：** 管理群内命中违禁词自动撤回
> **结果：** ✅ 撤回成功，写入 moderation.log

---

## 设计

`services/message_rule.py` 新增 `check_keywords()` + `list_keywords()`。

`plugins/auto_recall.py`：
- 监听管理群消息，`contains_phrase` 匹配
- 命中 → `bot.delete_msg()` 撤回
- 写入 `moderation.log`
- Owner 豁免
- 查询指令「违禁词」，Admin+，列出当前群关键词

`bot/config/keywords.json`（gitignored）：分群配置，支持 `"*"` 全局 + 群号专属。

## 踩坑

### 关键词配置采用 JSON

与 shortcuts.json 采用相同的分群结构（`"*"` + 群号），两个配置共用 `message_rule.py` 中的路径解析逻辑。
