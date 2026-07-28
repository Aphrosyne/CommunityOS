"""
指令系统 - 命令注册与分发

所有插件通过此模块注册命令，由 command_dispatcher 统一分发。
支持命令别名：同一 handler 可被多个名称触发。
"""

from collections.abc import Callable, Coroutine
from typing import Any, Sequence

from services.logger import get_logger

logger = get_logger(__name__)


class CooldownTier:
    """冷却等级（对应 config.py 的 COMMAND_COOLDOWNS 索引）"""
    Query = 0      # 查询类命令（默认）
    Session = 1    # 会话启动类（如发布/混淆/解图）
    Admin = 2      # 管理类（如禁言/重载）


# {name: {handler, description}}
_commands: dict[str, dict[str, Any]] = {}

# {alias: name} — 别名 → 主命令名
_aliases: dict[str, str] = {}

# 命令处理器签名: async def handler(bot: Bot, event: MessageEvent) -> None
Handler = Callable[..., Coroutine[Any, Any, None]]


def register(
    name: str,
    handler: Handler,
    description: str = "",
    aliases: Sequence[str] | None = None,
    help_text: str = "",
    permission: int = 0,
    cooldown_level: int = 0,
    hidden: bool = False,
    accepts_args: bool | Sequence[str] = False,
    group_only: bool = False,
) -> None:
    """注册命令

    Args:
        name: 命令名（如 "help"）
        handler: 异步处理函数
        description: 命令简短说明，help 中展示
        aliases: 别名列表（如 ["帮助"]），可选
        help_text: 详细帮助说明（如 "帮助 xxx" 时展示），可选
        permission: 最低权限等级（-1=黑名单, 0=User, 1=Whitelist, 3=BotAdmin, 9=Owner），默认 0
        cooldown_level: 冷却等级（0=查询, 1=会话启动, 2=管理），默认 0
        hidden: 是否在 help 中隐藏，默认 False
        accepts_args: 参数规则。False 时必须纯指令触发（消息全文等于命令名/别名）；
            True 时允许指令后带任意参数（如 "禁言 @用户 1m"）；
            Sequence[str] 时为参数白名单，第二词必须在白名单内（如 help 只允许 "图片"）。
            默认 False
        group_only: 是否仅群聊有效。True 时私聊发送该命令将被忽略（不消耗冷却、不调用 handler）。
            默认 False
    """
    _commands[name] = {
        "handler": handler, "description": description,
        "help_text": help_text, "permission": permission,
        "cooldown_level": cooldown_level, "hidden": hidden,
        "accepts_args": accepts_args, "group_only": group_only,
    }
    logger.info(f"命令已注册: {name}")

    if aliases:
        for alias in aliases:
            _aliases[alias] = name
            logger.info(f"  别名: {alias} → {name}")


def get(name: str) -> dict[str, Any] | None:
    """查找命令信息，支持别名"""
    cmd = _commands.get(name)
    if cmd:
        return cmd

    real_name = _aliases.get(name)
    if real_name:
        return _commands[real_name]

    return None


def get_handler(name: str) -> Handler | None:
    """查找命令处理器，支持别名"""
    cmd = get(name)
    return cmd["handler"] if cmd else None


def list_all() -> list[dict[str, Any]]:
    """列出所有已注册命令，含别名和详细说明"""
    result = []
    for name, info in _commands.items():
        cmd_aliases = [a for a, n in _aliases.items() if n == name]
        result.append({
            "name": name,
            "description": info["description"],
            "aliases": cmd_aliases,
            "help_text": info.get("help_text", ""),
            "permission": info.get("permission", 0),
            "hidden": info.get("hidden", False),
        })
    return result


def matches_args(cmd: dict[str, Any], words: list[str]) -> bool:
    """检查消息词列表是否符合命令的参数规则

    Args:
        cmd: 命令信息字典（来自 get/list_all）
        words: 消息按空白分割后的词列表（words[0] 为命令名/别名）

    Returns:
        True 表示参数规则通过，应继续处理
    """
    accepts = cmd.get("accepts_args", False)
    if accepts is True:
        # 允许任意参数
        return True
    if accepts is False:
        # 纯指令：只能有命令名，无参数
        return len(words) == 1
    # Sequence[str] 白名单：无参数允许；有参数则第二词必须在白名单内
    if len(words) == 1:
        return True
    return words[1] in accepts
