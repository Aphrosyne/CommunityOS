"""
群成员变更日志 - 记录 MANAGED_GROUPS 中的成员进出
"""
from nonebot import on_notice
from nonebot.adapters.onebot.v11 import (
    Bot, GroupIncreaseNoticeEvent, GroupDecreaseNoticeEvent,
)

from services.config import MANAGED_GROUPS
from services.logger import get_logger

logger = get_logger("member")

member_notice = on_notice(priority=5)


@member_notice.handle()
async def handle_member(bot: Bot, event):
    if isinstance(event, GroupIncreaseNoticeEvent):
        if event.group_id not in MANAGED_GROUPS:
            return
        logger.info(
            f"入群 group={event.group_id} user={event.user_id} "
            f"type={event.sub_type} operator={event.operator_id}"
        )

    elif isinstance(event, GroupDecreaseNoticeEvent):
        if event.group_id not in MANAGED_GROUPS:
            return
        label = "被踢" if event.sub_type == "kick" else "退群"
        logger.info(
            f"{label} group={event.group_id} user={event.user_id} "
            f"operator={event.operator_id}"
        )
