# Logger Service 日志服务

> **状态：** 正式
> **版本：** v1.0
> **最后更新：** 2026-07-01

---

# 目的

本文档定义 CommunityOS 统一日志服务的整体设计。

Logger Service 是 CommunityOS 的公共基础服务之一，负责为各个模块提供一致的日志记录能力。

---

# 设计目标

日志服务的设计目标包括：

* 提供统一的日志接口，避免各插件重复创建日志器。
* 按业务领域组织日志，而非按插件划分日志。
* 解耦业务逻辑与日志实现，使插件无需关心日志文件、格式及存储方式。
* 为未来日志轮转、日志压缩、远程日志等功能预留扩展能力。

Logger Service 关注的是**日志记录能力**，而不是具体业务。

---

# 设计原则

## 统一入口

所有模块均通过 Logger Service 获取 Logger。

Plugin、Service 不直接创建 Logger，也不直接管理日志文件。

```python
from services.logger import get_logger
logger = get_logger("image")   # → image.log
logger = get_logger("command") # → command.log
logger = get_logger(__name__)  # → bot.log（默认）
```

---

## 领域划分

日志按照业务领域（Domain）划分，而不是按照插件划分。

当前支持的领域：

| 域 | 文件 | 用途 |
|----|------|------|
| `bot` | `bot.log` | 系统运行、启动、配置、异常、其他 |
| `command` | `command.log` | 指令执行 |
| `image` | `image.log` | 图片业务（发布 / 混淆 / 解混淆） |

新增领域只需在 `_DOMAIN_FILES` 中加一行，无需修改已有模块。

---

## 职责分离

Logger Service 仅负责日志记录能力。

* 业务模块决定：什么时候记录、记录什么内容。
* Logger Service 决定：写入哪里、什么格式、如何输出。

二者保持解耦。

## 可扩展

日志系统应支持未来增加新的业务领域，而无需修改已有模块。

新增日志类型时，仅需在 `_DOMAIN_FILES` 中新增对应条目并调用 `_add_file_handler`。

---

# 日志分类

## bot.log

记录机器人系统运行状态。

包括但不限于：

* 启动
* 配置加载
* 插件加载
* 公共服务初始化
* Session 创建/完成/取消
* 系统异常

---

## command.log

记录指令执行情况。

由 `command_dispatcher.py` 写入，记录：

* 用户 QQ
* 执行的命令名

当前已实现基础记录。执行结果和耗时暂未记录，后续版本逐步加入。

---

## image.log

记录图片业务操作。

由 `publish.py`、`obfuscate.py`、`decode.py`、`image_obfuscator.py` 写入，记录：

* 进入模式
* 收到图片及数量
* 处理结果
* 完成发布/混淆/解混淆
* 取消
* 超时

图片相关插件共享同一日志文件。

---

# 日志职责

| 域 | 关注点 | 示例 |
|----|--------|------|
| Bot | 系统运行 | 是否正常启动、是否发生异常、插件是否加载成功 |
| Command | 用户调用 | 哪个命令被执行（执行结果和耗时暂未记录） |
| Image | 图片处理 | 收到图片、图片数量、处理结果 |

---

# Logger Service 架构

Logger Service 为所有模块提供统一日志入口。

整体结构如下：

```text
Plugin / Service
        │
        ▼
 Logger Service
        │
        ▼
   Domain Logger
        │
        ▼
   Log File
```

Plugin 不需要了解日志文件位置、输出格式及初始化流程，仅需获取对应领域的 Logger 即可完成日志记录。

---

# 日志格式

统一格式：

```
[时间] [级别] [域名] 消息
```

控制台和文件使用相同格式。文件 handler 为 INFO 级别（`logger.debug()` 不落盘），控制台在 `DEBUG=true` 时为 DEBUG 级别。

---

# 插件接入规范

所有插件遵循以下原则：

* 不自行创建 Logger。
* 不自行维护日志目录。
* 不自行管理日志格式。
* 不直接依赖日志实现细节。

插件只负责记录业务事件。日志实现由 Logger Service 统一维护。

---

# 日志内容规范

日志应记录机器人行为，而不是聊天内容。

推荐记录：

* 执行时间
* 用户标识
* 功能名称
* 操作结果
* 图片数量
* 异常信息

原则上不记录：

* 普通聊天消息
* 用户完整聊天内容
* 无业务意义的调试输出（debug 仅输出到控制台）

---

# 生命周期

当前版本已提供：

* 自动创建日志目录和日志文件
* 多领域 Logger 管理
* 日志轮转（RotatingFileHandler，单文件 10MB，保留 5 个）

未来版本计划支持：

* 日志保留策略（Retention）
* 自动压缩归档
* 结构化日志（JSON）
* 远程日志输出

以上能力均应在 Logger Service 内部实现，对业务模块保持透明。

---

# 不属于本文档范围

本文档不讨论：

* 日志分析
* 监控告警
* 各插件具体业务日志内容

---

# 总结

Logger Service 是 CommunityOS 的公共基础服务之一。

它负责统一日志能力，为系统、指令及业务模块提供一致的日志记录接口，并保证业务逻辑与日志实现相互独立。

随着 CommunityOS 的发展，新的模块应优先复用 Logger Service，而不是自行实现日志功能，从而保持整个系统日志体系的一致性与可维护性。
