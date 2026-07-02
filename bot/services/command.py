"""
指令系统 - 命令注册与分发

所有插件通过此模块注册命令，由 command_dispatcher 统一分发。
支持命令别名：同一 handler 可被多个名称触发。
"""

from collections.abc import Callable, Coroutine
from typing import Any, Sequence

from services.logger import get_logger

logger = get_logger(__name__)

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
) -> None:
    """注册命令

    Args:
        name: 命令名（如 "help"）
        handler: 异步处理函数
        description: 命令简短说明，help 中展示
        aliases: 别名列表（如 ["帮助"]），可选
        help_text: 详细帮助说明（如 "帮助 xxx" 时展示），可选
        permission: 最低权限等级（0=User, 1=BotAdmin, 2=Owner），默认 0
        cooldown_level: 冷却等级（0=查询, 1=会话启动, 2=管理），默认 0
    """
    _commands[name] = {
        "handler": handler, "description": description,
        "help_text": help_text, "permission": permission,
        "cooldown_level": cooldown_level,
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
        })
    return result
