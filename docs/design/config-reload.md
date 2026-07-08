# Config Reload 配置热更新

> **状态：** 正式
> **版本：** v1.0
> **最后更新：** 2026-07-08

---

## 1. 目的

Config Reload 为 CommunityOS 提供运行期配置热更新能力。

在引入此服务前，所有配置项（`.env`、`keywords.json`、`shortcuts.json`）只能通过重启 bot 进程才能生效。对于需要频繁调整的运营类配置（回复语、解图网址、好友验证答案等），重启成本过高，且会中断正在进行的图片发布等会话。

本服务允许 Owner 在运行期通过 `reload` / `重载` 指令重新加载配置文件，无需重启。

---

## 2. 设计原则

### 分层配置

配置项按变更频率和加载机制分为两层：

* **启动配置**（`.env`）：框架初始化、权限身份、冷却参数等，启动时读取，运行期不变。
* **运行配置**（`runtime.json`）：回复语、网址、答案等运营类字符串，运行期可热更新。

### 函数访问

运行配置必须通过 `runtime_config.get(key)` 函数访问，不能使用 `from runtime_config import XXX` 的导入式访问。

原因：Python 的 `from module import X` 是创建本地引用，即使模块内部重新加载，已导入的引用仍是旧值。函数访问每次读取模块级字典的最新值，热更新立即生效。

### 配置文件独立性

热更新配置文件 `runtime.json` 独立于 `.env`，不与启动配置混用。原因：

* `.env` 由 `python-dotenv` 在启动时加载到 `os.environ`，运行期重新读取需要手动管理 `os.environ` 覆盖逻辑，复杂且易错；
* JSON 格式天然支持数组、嵌套对象，比 `.env` 的 `|` 分隔字符串更清晰；
* 热更新范围明确——只有 `runtime.json` 中的项才会被 reload 指令影响，避免误改启动配置。

### 失败不阻断

任何单个配置文件重载失败不应阻断其他文件的重载。reload 指令逐个加载，汇总结果返回给用户。

---

## 3. 配置文件

### runtime.json

**位置：** `bot/config/runtime.json`（gitignored）
**示例：** `bot/config/runtime.example.json`（提交到 git）

**结构：**

```json
{
  "GREETING_REPLY": "你好呀 这里是机器人名字",
  "IMAGE_DECODE_URL": "https://example.com/decode",
  "FRIEND_VERIFY_ANSWER": "",
  "SELF_MUTE_REPLIES": ["回复1", "回复2"],
  "URL_AUTOCOMPLETE_PREFIX": "https://example.com/",
  "reload_marker": "初始版本"
}
```

**字段说明：**

| 字段 | 类型 | 用途 |
|------|------|------|
| `GREETING_REPLY` | string | greet 插件被 @ 时的回复语 |
| `IMAGE_DECODE_URL` | string | publish 插件发布后附带的解图网址 |
| `FRIEND_VERIFY_ANSWER` | string | friend 插件好友申请验证答案，空则不自动同意 |
| `SELF_MUTE_REPLIES` | string[] | mute 插件自禁成功后随机选取的回复语列表 |
| `URL_AUTOCOMPLETE_PREFIX` | string | auto_complete 插件网址补全前缀 |
| `reload_marker` | string | 人工确认字段，reload 指令回复此值供 Owner 核对 |

**`reload_marker` 用法：**

Owner 修改 `runtime.json` 后，同时修改 `reload_marker` 为一个易识别的值（如时间戳或序号），发送 `reload` 指令后对比回复中的 marker 值，确认热更新已生效。

### keywords.json / shortcuts.json

保持原有结构和加载逻辑，仅新增公开的 `reload_*()` 函数供 reload 指令调用。

---

## 4. 架构

### 服务层

#### `services/runtime_config.py`

```python
_config: dict  # 模块级配置字典，reload 时整体替换

def reload() -> tuple[bool, str, str]
    # 返回 (success, marker, error_msg)

def get(key: str, default=None) -> Any
    # 函数访问配置值
```

模块加载时自动读取 `runtime.json`，文件不存在则回退到 `runtime.example.json`。

#### `services/message_rule.py`

新增公开函数：

```python
def reload_keywords() -> tuple[bool, str]
    # 返回 (success, error_msg)
```

#### `services/shortcut.py`

`reload()` 返回值从 `None` 改为 `tuple[bool, str]`，统一与其他 reload 函数的返回格式。

### 插件层

#### `plugins/reload.py`

```python
async def handle_reload(bot, event):
    # 1. runtime_config.reload()
    # 2. message_rule.reload_keywords()
    # 3. shortcut.reload()
    # 汇总结果回复
```

**注册参数：**

| 参数 | 值 | 说明 |
|------|-----|------|
| `name` | `reload` | 主命令名 |
| `aliases` | `["重载"]` | 中文别名 |
| `permission` | `2` | Owner 专用 |
| `cooldown_level` | `2` | 管理类冷却 |
| `hidden` | `True` | 不显示在 help |
| `accepts_args` | `False` | 纯指令，无参数 |

#### 其他插件改造

5 个插件从 `from services.config import XXX` 改为 `runtime_config.get("XXX")`：

| 插件 | 配置项 |
|------|--------|
| `plugins/greet.py` | `GREETING_REPLY` |
| `plugins/publish.py` | `IMAGE_DECODE_URL` |
| `plugins/friend.py` | `FRIEND_VERIFY_ANSWER` |
| `plugins/mute.py` | `SELF_MUTE_REPLIES` |
| `plugins/auto_complete.py` | `URL_AUTOCOMPLETE_PREFIX` |

---

## 5. 指令回复格式

成功：

```
配置重载完成：
✓ runtime.json（marker: 你手动改的值）
✓ keywords.json
✓ shortcuts.json
```

部分失败：

```
配置重载完成：
✓ runtime.json（marker: v2）
✗ keywords.json（JSONDecodeError: ...）
✓ shortcuts.json
```

---

## 6. 配置项迁移规则

### 适合迁移到 runtime.json 的配置项

* 字符串或字符串列表类型
* 运营类内容（回复语、网址、答案），需频繁调整
* 各插件通过 `from services.config import` 导入

### 不适合迁移的配置项

* **框架级**：`DRIVER`、`LOG_LEVEL`、`ONEBOT_*` —— NoneBot2 初始化前必须读取
* **身份/权限**：`OWNER`、`ADMINS`、`BOT_QQ` —— 权限系统暂不热更新
* **数值调优**：`PUBLISH_COOLDOWN_*`、`IMAGE_*` —— 改动需重测边界，少改
* **结构复杂**：`MANAGED_GROUPS` —— 涉及多文件，迁移收益小

---

## 7. 错误处理

### 文件不存在

`runtime.json` 不存在时，模块加载回退到 `runtime.example.json`，reload 指令返回失败并提示文件不存在。

`keywords.json` / `shortcuts.json` 不存在时，对应 reload 函数返回失败，但不影响其他文件重载。

### JSON 解析失败

解析失败时：
* `runtime_config`：保留旧配置字典不变，返回失败和错误信息
* `reload_keywords`：清空 `_keywords` 为空字典，返回失败和错误信息
* `shortcut.reload`：清空 `_map` 为空字典，返回失败和错误信息

**注意**：`keywords.json` / `shortcuts.json` 解析失败会清空配置（原有行为），`runtime.json` 解析失败保留旧值（避免运营配置突然失效）。这是设计上的差异——运营配置失效影响用户体验，违禁词失效影响审核但可接受临时空值。

### 并发安全

reload 时整体替换模块级字典引用（`global _config; _config = new_dict`），Python 的 GIL 保证字典引用赋值是原子操作。正在读取旧字典的协程会继续使用旧值直到下次调用 `get()`，不存在半更新状态。

---

## 8. 与其他服务的关系

### Logger Service

`runtime_config.py` 使用 `get_logger(__name__)`，重载事件写入 `bot.log`：

```
运行时配置已重载，marker=v2
```

### Command Service

reload 指令通过 `services/command.py` 的 `register()` 注册，由 `command_dispatcher` 统一分发，遵循 `permission`、`cooldown_level`、`hidden`、`accepts_args` 等规则。

### Config Service（services/config.py）

启动配置仍由 `services/config.py` 从 `.env` 读取，与运行配置互不干扰。已迁移的 5 项配置从 `config.py` 中删除，避免双源冲突。

---

## 9. 当前版本不包含

* 权限系统热更新（`OWNER` / `ADMINS`）
* 数值类参数热更新（`PUBLISH_*` / `IMAGE_*` / `COMMAND_COOLDOWN_*`）
* `MANAGED_GROUPS` 迁移
* 配置文件变更监听（如 watchdog 自动 reload）
* 多实例配置同步
* 配置版本回滚

这些能力不属于当前阶段需求。

---

## 10. 总结

Config Reload 通过分层配置和函数访问模式，在不改动框架启动流程的前提下，为运营类配置提供了运行期热更新能力。

Owner 修改 `runtime.json` / `keywords.json` / `shortcuts.json` 后，发送 `reload` 指令即可立即生效，无需重启 bot。`reload_marker` 字段提供人工确认机制，确保热更新确实发生。
