"""
指令分发器 - 按首词匹配已注册命令

规则：
    - 私聊：直接发命令名触发
    - 群聊：@bot 命令名 触发
    - 只匹配已注册命令，未注册的忽略（无提示）
    - 30 秒全局冷却
"""
import time

from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.typing import T_State

from services.command import get as get_command, list_all
from services.config import COMMAND_COOLDOWN
from services.logger import get_logger

logger = get_logger("command")

# 冷却: {user_id: last_time}
_cooldowns: dict[int, float] = {}

dispatcher = on_message(rule=to_me(), priority=1, block=False)


@dispatcher.handle()
async def dispatch(bot: Bot, event: MessageEvent, state: T_State):
    # 取首词作为命令名
    msg = event.get_plaintext().strip()
    if not msg:
        return

    cmd_name = msg.split()[0].lower()
    user_id = event.user_id

    # 只处理已注册命令，未注册的静默忽略
    handler = get_command(cmd_name)
    if handler is None:
        return

    # 冷却检查
    now = time.time()
    last = _cooldowns.get(user_id, 0)
    if now - last < COMMAND_COOLDOWN:
        return  # 冷却期静默
    _cooldowns[user_id] = now

    # 调用
    logger.info(f"用户 {user_id} 执行命令: {cmd_name}")
    try:
        await handler(bot, event)
    except Exception as e:
        logger.error(f"命令 {cmd_name} 执行异常: {e}")
        await dispatcher.finish("命令执行出错，请稍后重试。")
