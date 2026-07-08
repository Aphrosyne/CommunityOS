"""
帮助命令 - 支持参数化详细帮助

用法：
    help / 帮助          → 命令列表
    help 图片            → 图片三件套详细说明
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, list_all

# 属于「图片」分类的命令
IMAGE_COMMANDS = {"publish", "obfuscate", "decode"}


async def handle_help(bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    parts = msg.split(None, 1)
    param = parts[1].strip() if len(parts) > 1 else ""

    commands = list_all()

    if param == "图片":
        await _show_image_help(bot, event, commands)
        return

    await _show_list(bot, event, commands)


async def _show_list(bot: Bot, event: MessageEvent, commands: list[dict]):
    lines = ["可用命令：", ""]
    for cmd in commands:
        if cmd.get("hidden"):
            continue
        label = cmd["aliases"][0] if cmd.get("aliases") else cmd["name"]
        line = label
        if cmd["description"]:
            line += f" — {cmd['description']}"
        lines.append(line)

    lines.append("")
    lines.append("输入「帮助 图片」查看图片功能详细说明。")
    await bot.send(event, "\n".join(lines))


async def _show_image_help(bot: Bot, event: MessageEvent, commands: list[dict]):
    text = (
        "建议先添加机器人为好友，否则可能无法收到\发出图片。\n"
        "手机用户私聊解图时请勾选原图，否则无法解混淆正确。\n"
        "\n"
        "📷 发布 (publish | 发布)\n"
        "私聊发送「发布」→ 进入发布模式 → 发送图片 → 发送「完成」开始发布。\n"
        "最多 10 张，3 分钟超时，发布后动态冷却。\n"
        "所有图片混淆后合并为一条消息发到指定群。\n"
        "\n"
        "🔒 混淆 (obfuscate | 混淆)\n"
        "私聊发送「混淆」→ 进入混淆模式 → 发送图片 → 发送「完成」开始混淆。\n"
        "上限和冷却同上。混淆图由私聊一条消息返回，不发群。\n"
        "\n"
        "🔓 解图 (decode | 解图)\n"
        "① 私聊「解图」→ 上传混淆图 →「完成」→ 返回原图。\n"
        "② 直接转发群里的混淆消息 → 自动识别并即时返回。\n"
        "③ 群聊引用一条含图消息 + @bot 解图 → 私信返回原图。\n"
        "三种方式共用上限和冷却同上。"
    )
    await bot.send(event, text)


register("help", handle_help, description="显示帮助信息", aliases=["帮助"], accepts_args=("图片",))
