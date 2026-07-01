"""
帮助命令 - 支持参数化详细帮助

用法：
    help / 帮助          → 命令列表
    help 图片处理         → 图片三件套详细说明
    help publish / 帮助 混淆 → 单个命令详细说明
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, list_all

# 属于「图片处理」分类的命令
IMAGE_COMMANDS = {"publish", "obfuscate", "decode"}


async def handle_help(bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    parts = msg.split(None, 1)
    param = parts[1].strip() if len(parts) > 1 else ""

    commands = list_all()

    if param == "图片处理":
        await _show_image_help(bot, event, commands)
        return

    await _show_list(bot, event, commands)


async def _show_list(bot: Bot, event: MessageEvent, commands: list[dict]):
    lines = ["可用命令：", ""]
    for cmd in commands:
        names = [cmd["name"], *cmd["aliases"]]
        label = " | ".join(names)
        line = label
        if cmd["description"]:
            line += f" — {cmd['description']}"
        lines.append(line)

    lines.append("")
    lines.append("输入「帮助 图片处理」查看图片功能详细说明。")
    await bot.send(event, "\n".join(lines))


async def _show_image_help(bot: Bot, event: MessageEvent, commands: list[dict]):
    lines = []
    for cmd in commands:
        if cmd["name"] not in IMAGE_COMMANDS:
            continue
        lines.append(cmd["help_text"] or f"{cmd['name']} — {cmd['description']}")
        lines.append("")

    if not lines:
        await bot.send(event, "暂无图片处理相关命令。")
        return

    await bot.send(event, "\n".join(lines).rstrip())


register("help", handle_help, description="显示帮助信息", aliases=["帮助"])
