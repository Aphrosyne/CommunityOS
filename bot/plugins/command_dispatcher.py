"""
指令分发器 - 识别 /cmd 并分发给已注册的命令处理器

规则：
    - 私聊：直接 /cmd 触发
    - 群聊：@bot /cmd 触发
    - 30 秒全局冷却
"""
import time

from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.typing import T_State

from services.command import get as get_command
from services.config import COMMAND_PREFIX, COMMAND_COOLDOWN
from services.logger import get_logger

logger = get_logger(__name__)

# 冷却: {user_id: last_time}
_cooldowns: dict[int, float] = {}

dispatcher = on_message(rule=to_me(), priority=1, block=False)


@dispatcher.handle()
async def dispatch(bot: Bot, event: MessageEvent, state: T_State):
    msg = event.get_plaintext().strip()

    # 只处理以指令前缀开头的消息
    if not msg.startswith(COMMAND_PREFIX):
        return

    # 解析命令名（取前缀后到空格或结尾的部分）
    parts = msg[len(COMMAND_PREFIX):].split()
    if not parts:
        return

    cmd_name = parts[0].lower()
    user_id = event.user_id

    # 冷却检查
    now = time.time()
    last = _cooldowns.get(user_id, 0)
    if now - last < COMMAND_COOLDOWN:
        remaining = int(COMMAND_COOLDOWN - (now - last))
        logger.debug(f"用户 {user_id} 指令 /{cmd_name} 冷却中: {remaining}s")
        return  # 冷却期静默
    _cooldowns[user_id] = now

    # 查找命令
    handler = get_command(cmd_name)
    if handler is None:
        await dispatcher.finish(
            f"未知命令 /{cmd_name}，输入 /help 查看可用命令。"
        )

    # 调用
    logger.info(f"用户 {user_id} 执行 /{cmd_name}")
    try:
        await handler(bot, event)
    except Exception as e:
        logger.error(f"命令 /{cmd_name} 执行异常: {e}")
        await dispatcher.finish("命令执行出错，请稍后重试。")
