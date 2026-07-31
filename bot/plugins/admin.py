"""
权限管理指令 - /botadmin /groupadmin /whitelist /blacklist /perm

依据:
    docs/design/database.md §3.1 权限层级
    docs/design/database-roadmap.md Round 3
    Q9-C / Q11 / Q12-A 设计决策

内部统一 set_permission(user, level, group_id)（Q11 单等级覆盖语义），
外部保留快捷命令:
    /botadmin add @xxx     → set_permission(xxx, 0, 3)   (permission=9,  全局)
    /botadmin remove @xxx  → set_permission(xxx, 0, 0)   (permission=9,  全局)
    /groupadmin add @xxx   → set_permission(xxx, 当前群, 2)  (permission=3, 群级)
    /groupadmin remove @xxx→ set_permission(xxx, 当前群, 0)  (permission=3, 群级)
    /whitelist add @xxx    → set_permission(xxx, 0, 1)   (permission=3,  全局)
    /whitelist remove @xxx → set_permission(xxx, 0, 0)   (permission=3,  全局)
    /blacklist add @xxx    → set_permission(xxx, 0, -1)  (permission=3,  全局)
    /blacklist remove @xxx → set_permission(xxx, 0, 0)   (permission=3,  全局)
    /perm @xxx             → 查询用户所有权限记录
    /perm @xxx clear       → 清除用户所有权限记录
    /perm @xxx in <群号>    → 查询用户在指定群的有效权限

Q13-A Owner 保护: target 当前 level=9 时拒绝操作。
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register, CooldownTier
from services import database
from services.permission import Level, get_level, is_owner
from services.audit import log_moderation as _log_mod
from services.logger import get_logger

logger = get_logger("command")
m_log = get_logger("moderation")


async def _resolve_target(event: MessageEvent) -> int | None:
    """从消息中提取 @目标 user_id，无则返回 None"""
    for seg in event.message:
        if seg.type == "at":
            return int(seg.data["qq"])
    return None


async def _apply(
    bot: Bot, event: MessageEvent, target_id: int, level: int, label: str,
    group_id: int = 0,
) -> None:
    """统一的权限设置执行器

    Q13-A: Owner(level=9) 受保护，不可被降级或拉黑。
    H2: 同级保护——非 Owner 操作者不可影响 level >= 自身的用户
        （防止 BotAdmin 互相降级/拉黑的横向越权）。
    group_id: 权限作用范围。0=全局（默认），>0=群级。
        - /botadmin /whitelist /blacklist 传 group_id=0（全局）
        - /groupadmin 传当前群 group_id（群级）
    """
    operator_id = event.user_id

    # 查操作者与目标的有效权限（target 查 MAX 覆盖全局+群级，L9 defense-in-depth）
    operator_level = await get_level(operator_id, group_id)
    target_level = await get_level(target_id, group_id)

    # Owner 保护（查全局 level，Owner 在任何群都受保护）
    if target_level >= Level.Owner:
        await bot.send(event, f"无法操作：{target_id} 是 Owner，受保护。")
        m_log.info(
            f"action=permission_denied operator={operator_id} "
            f"target={target_id} group={group_id} result=denied "
            f"reason=target_is_owner"
        )
        await _log_mod(
            "permission_denied", target_id, operator_id, group_id,
            reason="target_is_owner",
            details={"result": "denied"},
        )
        return

    # H2: 同级保护——非 Owner 操作者不可操作 level >= 自身的目标
    # （Owner 可操作任何非 Owner 用户；BotAdmin 之间互相禁止）
    if operator_level < Level.Owner and target_level >= operator_level:
        await bot.send(
            event,
            f"无法操作：{target_id} 的权限等级（{target_level}）"
            f"不低于你（{operator_level}），无权操作。",
        )
        m_log.info(
            f"action=permission_denied operator={operator_id} "
            f"target={target_id} group={group_id} result=denied "
            f"reason=target_level_gte_operator "
            f"operator_level={operator_level} target_level={target_level}"
        )
        await _log_mod(
            "permission_denied", target_id, operator_id, group_id,
            reason="target_level_gte_operator",
            details={
                "result": "denied",
                "operator_level": operator_level,
                "target_level": target_level,
            },
        )
        return

    try:
        await database.set_permission(
            user_id=target_id,
            group_id=group_id,
            level=level,
            granted_by=operator_id,
            reason=f"{label} by {operator_id}",
        )
    except Exception:
        logger.exception(
            f"DB 写入失败: set_permission target={target_id} "
            f"level={level} group={group_id}"
        )
        await bot.send(event, "操作失败，请稍后重试。")
        return

    action = f"设为{label}" if level != 0 else "移除"
    scope = f"群{group_id}" if group_id else "全局"
    await bot.send(event, f"已{action}（{scope}）: {target_id}")
    m_log.info(
        f"action=permission_set operator={operator_id} target={target_id} "
        f"level={level} group={group_id} result=success"
    )
    await _log_mod(
        "permission_set", target_id, operator_id, group_id,
        reason=f"{label} by {operator_id}",
        details={"level": level, "label": label, "result": "success",
                 "group_id": group_id},
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


async def handle_groupadmin(bot: Bot, event: MessageEvent):
    """群管理员管理: /groupadmin add|remove @user

    区别于 /botadmin（全局 level=3）：
        - /groupadmin 设置群级权限（group_id=当前群，level=2）
        - 仅在当前群生效，不影响其他群
        - 必须在群聊中执行（group_only）
        - 调用权限 BotAdmin(3)，低于 /botadmin 的 Owner(9)

    remove 时 set_permission(target, 当前群, 0)：
        - 删除该群的群级权限记录
        - 用户在该群回退到全局权限（可能是 0 或全局白名单等）
    """
    msg = event.get_plaintext().strip().split()
    if len(msg) < 2 or msg[1] not in ("add", "remove"):
        await bot.send(event, "用法：/groupadmin add|remove @用户")
        return

    target_id = await _resolve_target(event)
    if target_id is None:
        await bot.send(event, "请 @目标用户。")
        return

    group_id = event.group_id
    level = Level.GroupAdmin if msg[1] == "add" else Level.User
    await _apply(bot, event, target_id, level, "GroupAdmin", group_id=group_id)


# ── 权限查询指令 ──────────────────────────────────────────

_LEVEL_NAMES = {
    -1: "黑名单",
    0: "普通用户",
    1: "白名单",
    2: "群管理员",
    3: "BotAdmin",
    9: "Owner",
}


async def handle_perm(bot: Bot, event: MessageEvent):
    """权限查询与管理: /perm @user [clear|in <群号>]

    子命令:
        /perm @user              → 列出用户所有权限记录
        /perm @user clear        → 清除用户所有权限记录（Owner 保护）
        /perm @user in <群号>     → 查看用户在指定群的有效权限
    """
    msg = event.get_plaintext().strip().split()
    target_id = await _resolve_target(event)
    if target_id is None:
        await bot.send(event, "用法：/perm @用户 [clear | in <群号>]")
        return

    operator_id = event.user_id

    # 子命令: clear
    if len(msg) >= 2 and msg[1] == "clear":
        # Owner 保护 + 同级保护（H2 一致性）
        operator_level = await get_level(operator_id, 0)
        target_level = await get_level(target_id, 0)
        if target_level >= Level.Owner:
            await bot.send(event, f"无法操作：{target_id} 是 Owner，受保护。")
            m_log.info(
                f"action=permission_denied operator={operator_id} "
                f"target={target_id} result=denied reason=target_is_owner "
                f"action_subtype=perm_clear"
            )
            await _log_mod(
                "permission_denied", target_id, operator_id, 0,
                reason="target_is_owner",
                details={"result": "denied", "subaction": "perm_clear"},
            )
            return
        if operator_level < Level.Owner and target_level >= operator_level:
            await bot.send(
                event,
                f"无法操作：{target_id} 的权限等级（{target_level}）"
                f"不低于你（{operator_level}），无权清除。",
            )
            m_log.info(
                f"action=permission_denied operator={operator_id} "
                f"target={target_id} result=denied "
                f"reason=target_level_gte_operator "
                f"action_subtype=perm_clear "
                f"operator_level={operator_level} target_level={target_level}"
            )
            await _log_mod(
                "permission_denied", target_id, operator_id, 0,
                reason="target_level_gte_operator",
                details={
                    "result": "denied",
                    "subaction": "perm_clear",
                    "operator_level": operator_level,
                    "target_level": target_level,
                },
            )
            return

        try:
            deleted = await database.clear_user_permissions(target_id)
        except Exception:
            logger.exception(
                f"DB 写入失败: clear_user_permissions target={target_id}"
            )
            await bot.send(event, "操作失败，请稍后重试。")
            return

        await bot.send(event, f"已清除 {target_id} 的 {deleted} 条权限记录。")
        m_log.info(
            f"action=permission_set operator={operator_id} target={target_id} "
            f"result=success action_subtype=perm_clear deleted={deleted}"
        )
        await _log_mod(
            "permission_set", target_id, operator_id, 0,
            reason=f"perm clear by {operator_id}",
            details={"result": "success", "subaction": "perm_clear",
                     "deleted": deleted},
        )
        return

    # 子命令: in <群号>
    if len(msg) >= 3 and msg[1] == "in":
        try:
            query_group = int(msg[2])
        except ValueError:
            await bot.send(event, "群号格式无效，请输入数字。")
            return

        try:
            effective = await database.get_permission(target_id, query_group)
            records = await database.get_user_permissions(target_id)
        except Exception:
            logger.exception(
                f"DB 查询失败: get_permission target={target_id} "
                f"group={query_group}"
            )
            await bot.send(event, "查询失败，请稍后重试。")
            return

        # 过滤出该群相关记录（全局 + 该群）
        related = [r for r in records
                   if r["group_id"] == 0 or r["group_id"] == query_group]
        lines = [f"用户 {target_id} 在群 {query_group} 的有效权限："
                 f"{effective}（{_LEVEL_NAMES.get(effective, '未知')}）"]
        if related:
            lines.append("明细：")
            for r in related:
                scope = "全局" if r["group_id"] == 0 else f"群{r['group_id']}"
                exp = f" 过期:{r['expires_at']}" if r["expires_at"] else ""
                lines.append(
                    f"  {scope} level={r['level']}"
                    f"（{_LEVEL_NAMES.get(r['level'], '未知')}）{exp}"
                )
        else:
            lines.append("（无相关记录，使用默认权限）")
        await bot.send(event, "\n".join(lines))
        return

    # 默认: 列出所有权限记录
    try:
        records = await database.get_user_permissions(target_id)
    except Exception:
        logger.exception(
            f"DB 查询失败: get_user_permissions target={target_id}"
        )
        await bot.send(event, "查询失败，请稍后重试。")
        return

    if not records:
        await bot.send(event, f"用户 {target_id} 无权限记录（普通用户）。")
        return

    lines = [f"用户 {target_id} 的权限记录（{len(records)} 条）："]
    for r in records:
        scope = "全局" if r["group_id"] == 0 else f"群{r['group_id']}"
        exp = f" 过期:{r['expires_at']}" if r["expires_at"] else ""
        lines.append(
            f"  {scope} level={r['level']}"
            f"（{_LEVEL_NAMES.get(r['level'], '未知')}）{exp}"
        )
    await bot.send(event, "\n".join(lines))


register(
    "botadmin", handle_botadmin,
    description="管理员管理",
    permission=Level.Owner, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["sba"],
    accepts_args=True,
)
register(
    "whitelist", handle_whitelist,
    description="白名单管理",
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["swl"],
    accepts_args=True,
)
register(
    "blacklist", handle_blacklist,
    description="黑名单管理",
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["sbl"],
    accepts_args=True,
)
register(
    "groupadmin", handle_groupadmin,
    description="群管理员管理（群级）",
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["sga"],
    accepts_args=True, group_only=True,
)
register(
    "perm", handle_perm,
    description="权限查询与管理",
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["spm"],
    accepts_args=True,
)
