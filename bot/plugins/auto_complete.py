"""网址自动补全 — 尾号 N网 Mod ID"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, CooldownTier
from services.permission import Level
from services.runtime_config import get as get_runtime_config


async def handle_autocomplete(bot: Bot, event: MessageEvent):
    prefix = get_runtime_config("URL_AUTOCOMPLETE_PREFIX", "")
    if not prefix:
        await bot.send(event, "网址补全功能尚未配置。")
        return

    parts = event.get_plaintext().strip().split(None, 1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    if not arg or not arg.isdigit():
        await bot.send(event, "用法：尾号 <数字ID>")
        return

    url = prefix.rstrip("/") + "/" + arg
    await bot.send(event, url)


register(
    "autocomplete", handle_autocomplete,
    description="补全网址",
    permission=Level.User,
    aliases=["尾号"],
    accepts_args=True,
)
