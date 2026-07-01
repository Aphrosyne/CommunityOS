# 解混淆插件 + 自动识别 + 群聊引用解图

> **日期：** 2026-07-01
> **功能：** decode.py 解混淆插件（三种触发方式）
> **结果：** ✅ 三种路径均可用

---

## 三种触发方式

| 方式 | 场景 | 回复位置 |
|------|------|---------|
| 会话模式 | 私聊「解图」→ 发图 →「完成」 | 私聊 |
| 自动识别 | 私聊转发 publish 消息（含 `IMAGE_DECODE_URL` + 图片） | 私聊 |
| 群聊引用 | 群聊引用含图消息 + `@bot 解图` | 私信 |

三者共用动态冷却公式和 `_cd_expires` 冷却池。

---

## 架构

新增 `image_obfuscator.py` 的 `deobfuscate()` 函数（DEC 模式，`np.roll(old_idx, offset)` 正向偏移）。

插件内提取三个公共函数：

- `_download_images(img_segs)` — 从 MessageSegment 下载图片、GIF 过滤
- `_deobfuscate_batch(images, user_id, prefix)` — 批量解混淆、写临时文件
- `_cleanup_tmp(paths)` — 清理临时文件

避免三处重复的下载→过滤→解混淆代码。

---

## 踩坑

### sed 替换不彻底

从 `obfuscate.py` 复制后，sed 把 `deobfuscate` 换成了 `decode`，导致函数名错误。手动修正了函数名、别名和触发词。

### NoneBot2 回复杂记

查阅源码确认 `event.reply` 由适配器的 `_check_reply()` 自动填充，包含被引用消息的完整 `Message` 对象。`get_msg` API 调用已在适配器内部处理，插件只需检查 `event.reply is not None`。
