# 图片投稿 + 混淆实现记录

> **日期：** 2026-06-29
> **功能：** 私聊投稿 → Gilbert 混淆 → 转发群
> **结果：** ✅ 可用，200 万像素图片约 1 秒完成

---

## 踩坑记录

### 1. NapCat 图片路径问题

**现象：** `file:///` 协议路径 NapCat 无法识别，报 `ENOENT` 且路径被拼接到 NapCat 安装目录。

```
ENOENT: no such file or directory, open 'C:\MyProgrames\QQNT\...\data\images\xxx.png'
```

**解决：** 使用绝对路径 `C:\AphrosyneData\...\xxx.png`（`Path.resolve()`），不加 `file:///` 前缀。NapCat 直接接受 Windows 绝对路径。

**替代方案（未采用）：** base64 内嵌图片数据——无需文件路径，但对大图有体积膨胀问题。

---

### 2. 相对路径 vs 绝对路径

`IMAGE_DIR` 定义在 `services/config.py` 中，基于 `DATA_DIR`（相对路径 `data`）。

`Path` 对象不自动 resolve，`IMAGE_DIR / "xxx.jpg"` 返回相对路径，NapCat 无法识别。

**解决：** 发送前调用 `tmp_path.resolve()` 转为绝对路径，其余操作（写入/删除）使用相对路径即可。

---

### 3. Python 原生循环性能问题

**现象：** 1260×1612 图片混淆耗时约 10 秒，远慢于 JS 原版（毫秒级）。

**原因：** 原始实现使用 Python list + for 循环处理 200 万像素：
- Gilbert 曲线坐标生成：200 万次递归 + `list.append`
- 像素置换：200 万次循环，RGBA 四通道逐个拷贝

**解决：** 重写为 numpy 向量化：

```python
# 之前：200 万次循环
for i in range(total):
    result[new_p + 0] = pixels[old_p + 0]
    ...

# 之后：numpy 单次操作
result[new_idx] = flat[old_idx]
```

同时将 `list.append` 改为预分配 numpy 数组。性能降至约 1 秒。

**依赖新增：** `numpy>=1.26.0`

---

### 4. 插件加载路径

`nonebot.load_plugins("plugins")` 无法正确识别插件目录。

**解决：** 当前使用 `nonebot.load_plugin("plugins.xxx")` 逐个加载。后续插件多了再统一处理。

---

### 5. `sys.path` 与模块导入

插件中 `from services.config import ...` 报 `ModuleNotFoundError`。

**原因：** `bot/` 不在 Python 搜索路径中。

**解决：** `main.py` 中 `sys.path.insert(0, str(PROJECT_ROOT))`，同时创建 `bot/__init__.py` 使其成为 Python 包。

