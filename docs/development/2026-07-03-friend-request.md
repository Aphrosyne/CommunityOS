# 好友申请自动处理

> **日期：** 2026-07-03
> **功能：** 验证答案匹配自动同意好友申请
> **结果：** ✅ 正确匹配并同意，日志写入 relationship.log

---

## 设计

`plugins/friend.py` 监听 OneBot v11 `request.friend` 事件。提取验证文本最后一行，去掉「回答:」/「答案:」前缀，与 `.env` 中 `FRIEND_VERIFY_ANSWER` 完全匹配。

匹配 → 同意申请。不匹配 → 忽略（不拒绝，留给人审）。

新增 `relationship.log`（Logger Service 的 `relationship` 域）。

## 踩坑

### QQ 验证文本格式

QQ 好友申请的 `comment` 是 `问题\n回答:答案` 多行格式，`split("\n")[-1]` 取最后一行后还需去掉 `回答:` 前缀。`strip()` 只去头尾空白，不去中间换行和前缀。
