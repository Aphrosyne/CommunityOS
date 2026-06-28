"""
打招呼插件 - 被 @ 时自动回复
"""
from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import MessageEvent

from services.config import GREETING_REPLY
from services.logger import get_logger

logger = get_logger(__name__)

greet = on_message(rule=to_me(), priority=10, block=False)


@greet.handle()
async def handle_greet(event: MessageEvent):
    logger.info(f"被 @，来自 {event.user_id}，回复: {GREETING_REPLY}")
    await greet.finish(GREETING_REPLY)
