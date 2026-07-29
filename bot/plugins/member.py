"""
群成员变更日志 - 记录 MANAGED_GROUPS 中的成员进出
"""
from nonebot import on_notice
from nonebot.adapters.onebot.v11 import (
    Bot, GroupIncreaseNoticeEvent, GroupDecreaseNoticeEvent,
)

from services import database
from services import runtime_config
from services.logger import get_logger

logger = get_logger("member")

member_notice = on_notice(priority=5)


@member_notice.handle()
async def handle_member(bot: Bot, event):
    if isinstance(event, GroupIncreaseNoticeEvent):
        if event.group_id not in runtime_config.get("MANAGED_GROUPS", []):
            return
        # Q2-A: 跳过 bot 自身入群
        if event.user_id == event.self_id:
            return
        logger.info(
            f"入群 group={event.group_id} user={event.user_id} "
            f"type={event.sub_type} operator={event.operator_id}"
        )
        try:
            await database.record_membership(
                event.user_id, event.group_id, "join"
            )
        except Exception:
            logger.exception(
                f"DB 写入失败: join group={event.group_id} "
                f"user={event.user_id}"
            )

    elif isinstance(event, GroupDecreaseNoticeEvent):
        if event.group_id not in runtime_config.get("MANAGED_GROUPS", []):
            return
        # Q2-A: 跳过 bot 自身退群
        if event.user_id == event.self_id:
            return
        label = "被踢" if event.sub_type == "kick" else "退群"
        logger.info(
            f"{label} group={event.group_id} user={event.user_id} "
            f"operator={event.operator_id}"
        )
        event_type = "kick" if event.sub_type == "kick" else "leave"
        try:
            await database.record_membership(
                event.user_id, event.group_id, event_type
            )
        except Exception:
            logger.exception(
                f"DB 写入失败: {event_type} group={event.group_id} "
                f"user={event.user_id}"
            )
