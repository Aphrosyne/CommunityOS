"""违禁词自动撤回 + 关键词查询"""
import time

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, CooldownTier
from services.config import MANAGED_GROUPS
from services.message_rule import check_keywords, list_keywords
from services.permission import Level, is_owner
from services.logger import get_logger

m_log = get_logger("moderation")

# 每群每用户 5 秒冷却
_recall_cd: dict[tuple[int, int], float] = {}
RECALL_CD = 5


async def handle_keywords(bot: Bot, event: MessageEvent):
    if event.message_type != "group":
        return
    group_id = getattr(event, "group_id", 0)
    kws = list_keywords(group_id)
    if not kws:
        await bot.send(event, "当前群无违禁词。")
        return
    await bot.send(event, "违禁词：" + "、".join(kws))


register(
    "keywords", handle_keywords,
    description="列出违禁词",
    permission=Level.BotAdmin,
    aliases=["违禁词"],
    hidden=True,
)

auto_mod = on_message(priority=0, block=False)


@auto_mod.handle()
async def handle_auto_mod(bot: Bot, event: MessageEvent):
    if event.message_type != "group":
        return

    group_id = getattr(event, "group_id", 0)
    if group_id not in MANAGED_GROUPS:
        return

    if await is_owner(event.user_id):
        return

    # 冷却检查
    now = time.time()
    ck = (group_id, event.user_id)
    if now - _recall_cd.get(ck, 0) < RECALL_CD:
        return
    _recall_cd[ck] = now

    text = event.get_plaintext()
    hits = check_keywords(group_id, text)
    if not hits:
        return

    try:
        await bot.delete_msg(message_id=event.message_id)
    except Exception as e:
        m_log.info(
            f"action=auto_recall operator=system group={group_id} "
            f"target={event.user_id} result=failed reason={e}"
        )
        return

    m_log.info(
        f"action=auto_recall operator=system group={group_id} "
        f"target={event.user_id} result=success keywords={','.join(hits)}"
    )
