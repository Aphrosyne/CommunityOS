"""
权限管理指令 - /botadmin /whitelist /blacklist

依据:
    docs/design/database.md §3.1 权限层级
    docs/design/database-roadmap.md Round 3
    Q9-C / Q11 / Q12-A 设计决策

内部统一 set_permission(user, level)（Q11 单等级覆盖语义），
外部保留快捷命令:
    /botadmin add @xxx    → set_permission(xxx, 0, 3)   (permission=9)
    /botadmin remove @xxx → set_permission(xxx, 0, 0)   (permission=9)
    /whitelist add @xxx    → set_permission(xxx, 0, 1)   (permission=3)
    /whitelist remove @xxx → set_permission(xxx, 0, 0)   (permission=3)
    /blacklist add @xxx    → set_permission(xxx, 0, -1)  (permission=3)
    /blacklist remove @xxx → set_permission(xxx, 0, 0)   (permission=3)

Q13-A Owner 保护: target 当前 level=9 时拒绝操作。
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, CooldownTier
from services import database
from services.permission import Level, get_level, is_owner
from services.logger import get_logger

logger = get_logger("command")
m_log = get_logger("moderation")


async def _log_mod(
    action: str,
    user_id: int,
    operator_id: int,
    group_id: int,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    """写入审核日志到 DB，失败仅记日志不抛出（Q4-A）"""
    try:
        await database.log_moderation(
            action=action,
            user_id=user_id,
            operator_id=operator_id,
            group_id=group_id,
            reason=reason,
            details=details,
        )
    except Exception:
        m_log.exception(f"DB 写入失败: moderation_log action={action}")


async def _resolve_target(event: MessageEvent) -> int | None:
    """从消息中提取 @目标 user_id，无则返回 None"""
    for seg in event.message:
        if seg.type == "at":
            return int(seg.data["qq"])
    return None


async def _apply(
    bot: Bot, event: MessageEvent, target_id: int, level: int, label: str
) -> None:
    """统一的权限设置执行器

    Q13-A: Owner(level=9) 受保护，不可被降级或拉黑。
    """
    operator_id = event.user_id

    # Owner 保护
    target_level = await get_level(target_id, 0)
    if target_level >= Level.Owner:
        await bot.send(event, f"无法操作：{target_id} 是 Owner，受保护。")
        m_log.info(
            f"action=permission_denied operator={operator_id} "
            f"target={target_id} result=denied reason=target_is_owner"
        )
        await _log_mod(
            "permission_denied", target_id, operator_id, 0,
            reason="target_is_owner",
            details={"result": "denied"},
        )
        return

    try:
        await database.set_permission(
            user_id=target_id,
            group_id=0,
            level=level,
            granted_by=operator_id,
            reason=f"{label} by {operator_id}",
        )
    except Exception:
        logger.exception(
            f"DB 写入失败: set_permission target={target_id} level={level}"
        )
        await bot.send(event, "操作失败，请稍后重试。")
        return

    action = f"设为{label}" if level != 0 else "移除"
    await bot.send(event, f"已{action}: {target_id}")
    m_log.info(
        f"action=permission_set operator={operator_id} target={target_id} "
        f"level={level} result=success"
    )
    await _log_mod(
        "permission_set", target_id, operator_id, 0,
        reason=f"{label} by {operator_id}",
        details={"level": level, "label": label, "result": "success"},
    )


async def handle_botadmin(bot: Bot, event: MessageEvent):
    """管理员管理: /botadmin add|remove @user"""
    msg = event.get_plaintext().strip().split()
    if len(msg) < 2 or msg[1] not in ("add", "remove"):
        await bot.send(event, "用法：/botadmin add|remove @用户")
        return

    target_id = await _resolve_target(event)
    if target_id is None:
        await bot.send(event, "请 @目标用户。")
        return

    level = Level.BotAdmin if msg[1] == "add" else Level.User
    await _apply(bot, event, target_id, level, "BotAdmin")


async def handle_whitelist(bot: Bot, event: MessageEvent):
    """白名单管理: /whitelist add|remove @user"""
    msg = event.get_plaintext().strip().split()
    if len(msg) < 2 or msg[1] not in ("add", "remove"):
        await bot.send(event, "用法：/whitelist add|remove @用户")
        return

    target_id = await _resolve_target(event)
    if target_id is None:
        await bot.send(event, "请 @目标用户。")
        return

    level = Level.Whitelist if msg[1] == "add" else Level.User
    await _apply(bot, event, target_id, level, "Whitelist")


async def handle_blacklist(bot: Bot, event: MessageEvent):
    """黑名单管理: /blacklist add|remove @user"""
    msg = event.get_plaintext().strip().split()
    if len(msg) < 2 or msg[1] not in ("add", "remove"):
        await bot.send(event, "用法：/blacklist add|remove @用户")
        return

    target_id = await _resolve_target(event)
    if target_id is None:
        await bot.send(event, "请 @目标用户。")
        return

    level = Level.Blacklist if msg[1] == "add" else Level.User
    await _apply(bot, event, target_id, level, "Blacklist")


register(
    "botadmin", handle_botadmin,
    description="管理员管理",
    permission=Level.Owner, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["管理员"],
    accepts_args=True,
)
register(
    "whitelist", handle_whitelist,
    description="白名单管理",
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["白名单"],
    accepts_args=True,
)
register(
    "blacklist", handle_blacklist,
    description="黑名单管理",
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["黑名单"],
    accepts_args=True,
)
