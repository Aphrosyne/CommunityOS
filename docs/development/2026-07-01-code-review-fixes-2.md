# Code Review 修复 — 解混淆插件

> **日期：** 2026-07-01
> **来源：** /code-review medium
> **结果：** ✅ 3 条修复，decode/obfuscate/publish 同步

---

## 修复

### 1. handle_group_decode 未加锁

群聊引用解图 handler 访问 `_cd_expires` 未取用户锁，与 session 路径并发可绕过冷却。

**修复：** 拆分为 `handle_group_decode`（取锁）+ `_handle_group_decode_locked`（业务逻辑），与 session handler 模式一致。

### 2. write_bytes 异常未捕获

`_deobfuscate_batch` 中 `tmp.write_bytes(result)` 失败时，前几张已写入的临时文件路径未返回给调用方，无法清理。

**修复：** `write_bytes` 加 try/except，失败时记录日志并跳过。同步到 obfuscate.py 和 publish.py。

### 3. _cleanup_tmp 异常掩盖

`p.unlink()` 在 `finally` 块中抛出 `PermissionError` 会替代 `try` 块的原始异常。

**修复：** `_cleanup_tmp` 内 `p.unlink()` 加 try/except。同步到 obfuscate.py 和 publish.py。
