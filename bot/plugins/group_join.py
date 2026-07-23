"""
加群审核插件 - 校验申请人是否在中转群

业务流程：
1. 收到加群请求（sub_type=add）
2. 目标群在 MANAGED_GROUPS 中 → 记录到待审核缓存
3. GROUP_JOIN_AUTO_REJECT=true 且申请人不在中转群 → 拒绝（理由热更新）
4. 其他情况不处理（管理员手动同意）

不处理：被邀请入群（sub_type=invite）

测试指令（开关关闭时使用）：
- test_review / 审核测试：列出所有待审核请求及判断结果
- test_review_clear / 审核清空：清空待审核缓存
"""
import time
from dataclasses import dataclass

from nonebot import on_request, on_notice, on_message, on, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupRequestEvent, MessageEvent, NoticeEvent, RequestEvent

from services.command import register
from services.config import MANAGED_GROUPS, TRANSIT_GROUP
from services.runtime_config import get as get_runtime_config
from services.group_membership import is_member, get_cache_info
from services.logger import get_logger

logger = get_logger("group_join")


# === 临时诊断：用 driver 钩子拦截最原始的 WebSocket 消息 ===
_driver = get_driver()


@_driver.on_bot_connect
async def _hook_bot_events(bot: Bot):
    """bot 连接后，直接挂钩 bot 的事件处理方法，拦截所有原始事件"""
    from nonebot.adapters.onebot.v11 import Bot as V11Bot

    # 保存原始 handle_event 引用
    original_handle_event = bot.handle_event

    async def patched_handle_event(event):
        # 拦截所有事件，打印 post_type
        try:
            post_type = event.get("post_type") if isinstance(event, dict) else getattr(event, "post_type", "?")
            if post_type in ("request", "notice", "meta_event"):
                logger.warning(
                    f"[诊断-raw] post_type={post_type} "
                    f"raw={event if isinstance(event, dict) else vars(event)}"
                )
        except Exception as e:
            logger.warning(f"[诊断-raw] 读取失败: {e}")
        # 调用原始处理
        await original_handle_event(event)

    # 替换 bot 的 handle_event 方法
    bot.handle_event = patched_handle_event
    logger.warning("[诊断] 已挂钩 bot.handle_event 拦截所有原始事件")


group_req = on_request(priority=5, block=False)

# 兜底：监听所有 notice（防止 NapCat 把加群请求错归类）
_debug_notice = on_notice(priority=1, block=False)


@_debug_notice.handle()
async def _debug_notice_handler(bot: Bot, event: NoticeEvent):
    """记录所有 notice 事件，排查加群申请是否被归为 notice"""
    logger.warning(
        f"[诊断-notice] type={type(event).__name__} "
        f"notice_type={getattr(event, 'notice_type', '?')} "
        f"sub_type={getattr(event, 'sub_type', '?')}"
    )


@dataclass
class PendingRequest:
    """待审核加群请求（内存缓存项）"""
    flag: str
    user_id: int
    group_id: int
    received_at: float


# 待审核请求缓存（按收到顺序）
_pending: list[PendingRequest] = []


@group_req.handle()
async def handle_group_request(bot: Bot, event: GroupRequestEvent):
    # 无条件记录所有进入 handler 的群请求事件（便于排查事件是否到达）
    logger.info(
        f"收到群请求事件: group={event.group_id} user={event.user_id} "
        f"sub_type={event.sub_type}"
    )

    # 只处理主动申请加群
    if event.sub_type != "add":
        return

    group_id = event.group_id
    user_id = event.user_id
    flag = event.flag

    # 只审核受管理群
    if group_id not in MANAGED_GROUPS:
        return

    # 记录到待审核缓存
    pending = PendingRequest(flag=flag, user_id=user_id, group_id=group_id,
                              received_at=time.time())
    _pending.append(pending)
    logger.info(f"加群请求已缓存: group={group_id} user={user_id}")

    # 读取自动拒绝开关
    auto_reject = get_runtime_config("GROUP_JOIN_AUTO_REJECT", False)
    if not auto_reject:
        # 开关关闭，不执行拒绝
        return

    # 读取中转群配置（来自 .env，不热更新）
    transit_group = TRANSIT_GROUP
    if not transit_group:
        # 功能未启用，不处理
        return

    # 检查是否在中转群
    try:
        in_transit = await is_member(bot, transit_group, user_id)
    except Exception as e:
        # 查询失败时不处理，避免误拒
        logger.error(f"中转群查询失败，不处理: group={group_id} user={user_id} error={e}")
        return

    if in_transit:
        # 在中转群，不处理（管理员手动同意）
        logger.info(
            f"加群请求 不处理（在中转群）: group={group_id} user={user_id} "
            f"transit={transit_group}"
        )
    else:
        reason = get_runtime_config("GROUP_JOIN_REJECT_REASON", "非正常渠道入群，已驳回")
        await bot.set_group_add_request(
            flag=flag, sub_type="add", approve=False, reason=reason
        )
        logger.info(
            f"加群请求 拒绝: group={group_id} user={user_id} "
            f"transit={transit_group} reason={reason}"
        )


async def handle_test_review(bot: Bot, event: MessageEvent):
    """加群审核测试 - 列出所有待审核请求及判断结果

    强制刷新一次中转群成员缓存，对所有待审核请求判断是否在中转群。
    仅展示，不执行拒绝。
    """
    if not _pending:
        await bot.send(event, "当前没有待审核的加群请求")
        return

    transit_group = TRANSIT_GROUP
    if not transit_group:
        await bot.send(event, "加群审核功能未启用（TRANSIT_GROUP=0）")
        return

    # 强制刷新一次中转群成员缓存（所有请求共用一次刷新）
    try:
        # 用第一个请求触发刷新
        await is_member(bot, transit_group, _pending[0].user_id, force_refresh=True)
    except Exception as e:
        await bot.send(event, f"刷新中转群成员缓存失败: {e}")
        return

    info = get_cache_info(transit_group)

    # 对每个请求判断（此时缓存已刷新，走命中路径）
    lines = [
        f"待审核请求共 {len(_pending)} 条：",
        f"中转群: {transit_group}（成员数: {info['member_count']}）",
        "",
    ]
    for i, p in enumerate(_pending, 1):
        try:
            in_transit = await is_member(bot, transit_group, p.user_id)
            result = "在中转群 → 不拒绝" if in_transit else "不在中转群 → 会拒绝"
        except Exception as e:
            result = f"查询失败: {e}"
        ts = time.strftime("%m-%d %H:%M", time.localtime(p.received_at))
        lines.append(f"{i}. user={p.user_id} group={p.group_id} [{ts}] {result}")

    await bot.send(event, "\n".join(lines))


async def handle_test_review_clear(bot: Bot, event: MessageEvent):
    """清空待审核加群请求缓存"""
    count = len(_pending)
    _pending.clear()
    await bot.send(event, f"已清空 {count} 条待审核请求缓存")


register(
    "test_review", handle_test_review,
    description="加群审核测试",
    aliases=["审核测试"],
    permission=2,
    cooldown_level=2,
    hidden=True,
    accepts_args=False,
)

register(
    "test_review_clear", handle_test_review_clear,
    description="清空审核测试缓存",
    aliases=["审核清空"],
    permission=2,
    cooldown_level=2,
    hidden=True,
    accepts_args=False,
)


async def handle_debug_group_msg(bot: Bot, event: MessageEvent):
    """临时诊断：调用 get_group_system_msg 查看群系统消息"""
    msg = event.get_plaintext().strip().split()
    if len(msg) < 2:
        await bot.send(event, "用法: debug_group_msg <群号>")
        return
    try:
        group_id = int(msg[1])
    except ValueError:
        await bot.send(event, "群号无效")
        return

    try:
        result = await bot.call_api("get_group_system_msg", group_id=group_id)
        await bot.send(event, f"群 {group_id} 系统消息:\n{result}")
    except Exception as e:
        await bot.send(event, f"调用失败: {type(e).__name__}: {e}")


register(
    "debug_group_msg", handle_debug_group_msg,
    description="查看群系统消息",
    permission=2,
    cooldown_level=2,
    hidden=True,
    accepts_args=True,
)


async def handle_debug_group_info(bot: Bot, event: MessageEvent):
    """临时诊断：调用 get_group_info 查看群信息"""
    msg = event.get_plaintext().strip().split()
    if len(msg) < 2:
        await bot.send(event, "用法: debug_group_info <群号>")
        return
    try:
        group_id = int(msg[1])
    except ValueError:
        await bot.send(event, "群号无效")
        return

    try:
        result = await bot.call_api("get_group_info", group_id=group_id)
        await bot.send(event, f"群 {group_id} 信息:\n{result}")
    except Exception as e:
        await bot.send(event, f"调用失败: {type(e).__name__}: {e}")


register(
    "debug_group_info", handle_debug_group_info,
    description="查看群信息",
    permission=2,
    cooldown_level=2,
    hidden=True,
    accepts_args=True,
)
