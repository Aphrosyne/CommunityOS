"""
指令系统 - 命令注册与分发

所有插件通过此模块注册命令，由 command_dispatcher 统一分发。
"""

from collections.abc import Callable, Coroutine
from typing import Any

from services.logger import get_logger

logger = get_logger(__name__)

# {name: {handler, description}}
_commands: dict[str, dict[str, Any]] = {}

# 命令处理器签名: async def handler(bot: Bot, event: MessageEvent) -> None
Handler = Callable[..., Coroutine[Any, Any, None]]


def register(name: str, handler: Handler, description: str = "") -> None:
    """注册命令

    Args:
        name: 命令名（不含前缀，如 "help"）
        handler: 异步处理函数，签名为 async def handler(bot, event)
        description: 命令说明，/help 中展示
    """
    _commands[name] = {"handler": handler, "description": description}
    logger.info(f"命令已注册: /{name}")


def get(name: str) -> Handler | None:
    """查找命令处理器"""
    cmd = _commands.get(name)
    return cmd["handler"] if cmd else None


def list_all() -> dict[str, str]:
    """列出所有已注册命令: {name: description}"""
    return {name: info["description"] for name, info in _commands.items()}
