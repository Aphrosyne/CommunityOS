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
    for cmd in commands:
        names = [cmd["name"], *cmd["aliases"]]
        label = " | ".join(names)
        line = label
        if cmd["description"]:
            line += f" — {cmd['description']}"
        lines.append(line)

    await bot.send(event, "\n".join(lines))


register("help", handle_help, description="显示帮助信息", aliases=["帮助"])
