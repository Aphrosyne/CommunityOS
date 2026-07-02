# 指令冷却等级 + Owner 豁免

> **日期：** 2026-07-02
> **功能：** 按等级分冷却 + Owner 冷却豁免
> **结果：** ✅ 查询/会话/管理三级冷却，Owner 全部跳过

---

## 设计

指令冷却从单一全局值改为三级：

| 等级 | 类型 | 默认 | 适用 |
|------|------|------|------|
| 0 | 查询类 | 3s | help, status |
| 1 | 会话启动类 | 5s | publish, obfuscate, decode |
| 2 | 管理类 | 10s | 后续管理命令 |

`register()` 新增 `cooldown_level` 参数。不同等级冷却独立，互不影响。

冷却存储：`{user_id: {level: last_time}}`。

## Owner 豁免

`permission.py` 新增 `is_owner()`。command_dispatcher 和三个图片插件的冷却检查全部用 `if not is_owner(user_id):` 包裹。

Owner 跳过所有冷却，不写入冷却状态。Admin 和 User 正常冷却。

## 清理

删除 `IMAGE_COOLDOWN` 死配置（旧 `image_submit.py` 残留）。`.env` 行内 `#` 注释改为独立行（python-dotenv 不支持行内注释）。
