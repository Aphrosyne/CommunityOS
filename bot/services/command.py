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
) -> None:
    """注册命令

    Args:
        name: 命令名（如 "help"）
        handler: 异步处理函数
        description: 命令说明，help 中展示
        aliases: 别名列表（如 ["帮助"]），可选
    """
    _commands[name] = {"handler": handler, "description": description}
    logger.info(f"命令已注册: {name}")

    if aliases:
        for alias in aliases:
            _aliases[alias] = name
            logger.info(f"  别名: {alias} → {name}")


def get(name: str) -> Handler | None:
    """查找命令处理器，支持别名"""
    # 先查主命令，再查别名
    cmd = _commands.get(name)
    if cmd:
        return cmd["handler"]

    real_name = _aliases.get(name)
    if real_name:
        return _commands[real_name]["handler"]

    return None


def list_all() -> list[dict[str, Any]]:
    """列出所有已注册命令，含别名信息"""
    result = []
    for name, info in _commands.items():
        # 找出指向此命令的所有别名
        cmd_aliases = [a for a, n in _aliases.items() if n == name]
        result.append({
            "name": name,
            "description": info["description"],
            "aliases": cmd_aliases,
        })
    return result
