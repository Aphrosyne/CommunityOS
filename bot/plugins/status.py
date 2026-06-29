"""
/status - 系统运行状态
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register
from services.runtime import get_uptime
from services.config import BOT_VERSION


async def handle_status(bot: Bot, event: MessageEvent):
    reply = (
        f"CommunityOS Status\n"
        f"运行时间：{get_uptime()}\n"
        f"版本：{BOT_VERSION}"
    )
    await bot.send(event, reply)


register("status", handle_status, description="查看系统运行状态")
