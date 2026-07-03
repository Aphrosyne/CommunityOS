"""快捷映射查询"""
import re

from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register
from services.shortcut import list as list_shortcuts


async def _humanize(bot: Bot, group_id: int, text: str) -> str:
    """将 CQ 码和占位符转为人可读的名称"""
    # {at} → 被@的用户
    text = text.replace("{at}", "{被@的用户}")

    # [CQ:at,qq=xxx] → @群昵称
    def _resolve(qq_str: str):
        return qq_str  # 占位，下面异步替换

    # 找到所有 QQ 号
    ats = list(re.finditer(r"\[CQ:at,qq=(\d+)\]", text))
    for m in reversed(ats):
        qq = int(m.group(1))
        try:
            info = await bot.get_group_member_info(group_id=group_id, user_id=qq)
            name = info.get("card") or info.get("nickname", str(qq))
            text = text[:m.start()] + f"@{name}" + text[m.end():]
        except Exception:
            text = text[:m.start()] + f"@QQ:{qq}" + text[m.end():]

    return text


async def handle_shortcuts(bot: Bot, event: MessageEvent):
    if event.message_type != "group":
        await bot.send(event, "请私聊使用「帮助 图片」。")
        return

    group_id = getattr(event, "group_id", 0)
    sc = list_shortcuts(group_id)
    if not sc:
        await bot.send(event, "无快捷映射。")
        return

    lines = ["快捷映射：", ""]
    for k, v in sc.items():
        display = await _humanize(bot, group_id, v)
        lines.append(f"{k} → {display}")
    await bot.send(event, "\n".join(lines))


register(
    "shortcuts", handle_shortcuts,
    description="列出快捷映射",
    permission=1,
    aliases=["映射"],
    hidden=True,
)
