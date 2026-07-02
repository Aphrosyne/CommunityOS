# Cache Service — 文件缓存 + 解混淆缓存

> **日期：** 2026-07-02
> **功能：** 通用 FileCache + 图片解混淆结果缓存
> **结果：** ✅ 磁盘缓存，重启不丢，LRU 淘汰

---

## 设计

`services/cache.py`：通用 `FileCache` 类，基于文件系统的缓存，按总字节数限制，最旧文件优先淘汰。

`image_obfuscator.py` 持有实例并暴露 `cache_get` / `cache_set`——全部用 MD5(混淆图) 作键，值存 `.jpg` 原图。

写入点：
- `publish.py` / `obfuscate.py`：混淆完成后写入
- `decode.py`：解混淆成功后写入

读取点：
- `decode.py` 的 `_deobfuscate_batch`：解混淆前先查缓存，命中跳过 `deobfuscate()`

## 踩坑

### 目录错位

`.env` 中 `DATA_DIR=data` 是相对路径，从项目根目录启动时在根目录创建了 `data/cache/images/`。删除 `DATA_DIR` 配置项后统一使用代码默认 `bot/data/`。

### 最初用内存 LRU

第一版是纯内存缓存——重启丢失，且占 RAM。改为文件缓存后重启不丢。

### 缓存日志归属

最初 `FileCache` 内部写 `bot.log`。改为调用方 `cache_get`/`cache_set` 写 `image.log`，`FileCache` 自身异常仅 debug。普通未命中不记日志，避免噪音。
