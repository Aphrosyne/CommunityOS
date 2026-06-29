"""
帮助命令 - /help 列出所有可用命令
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, list_all


async def handle_help(bot: Bot, event: MessageEvent):
    commands = list_all()
    if not commands:
        await bot.send(event, "暂无可用命令。")
        return

    lines = ["可用命令：", ""]
    for name, desc in commands.items():
        line = f"/{name}"
        if desc:
            line += f" - {desc}"
        lines.append(line)

    await bot.send(event, "\n".join(lines))


register("help", handle_help, description="显示帮助信息")
