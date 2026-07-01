# Logger Service 重构 — 按领域分日志

> **日期：** 2026-07-01
> **功能：** 日志系统重构，按业务域分文件
> **结果：** ✅ bot.log / command.log / image.log 各自独立

---

## 改动

重写 `services/logger.py`，从单文件 `bot.log` 改为按领域分文件：

```
logs/
├── bot.log      # 系统 + 其他（默认）
├── command.log  # 指令执行
└── image.log    # 图片业务
```

核心机制：
- `get_logger(name)` — 根据 name 路由到对应日志文件
- `_DOMAIN_FILES` dict 维护域名→文件映射
- file handler 加 filter 防止跨域写入
- 控制台输出所有日志，文件 handler 为 INFO 级别

图片三插件 + image_obfuscator 改用 `get_logger("image")`。
command_dispatcher 改用 `get_logger("command")`。

## 踩坑

### bot.log filter 未排除 command 域

初版 bot.log filter 只排除了 `image`，新增 `command` 域后未同步更新，导致 command 日志同时写入 bot.log。

**解决：** bot.log filter 改为 `record.name not in _DOMAIN_FILES`，自动排除所有有独立文件的域。

### 插件日志信息不足

混淆服务只有两行「开始混淆」「混淆完成」，缺少用户、模式、数量等业务上下文。

**解决：** 三个图片插件各补 5-7 条 `logger.info`，格式统一为 `[功能] 用户 X 操作 详情`。
