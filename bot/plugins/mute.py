"""
禁言指令 - 群聊 @bot 禁言/解除禁言 @用户 [时长]
"""
import random
import re

from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

from services.command import register, CooldownTier
from services.permission import Level
from services.permission import is_owner
from services.runtime_config import get as get_runtime_config
from services.logger import get_logger

m_log = get_logger("moderation")

# 时间解析正则
_TIME_RE = re.compile(
    r"(?P<d>\d+)\s*(?:d|天|日)\s*|"
    r"(?P<h>\d+)\s*(?:h|小时|时)\s*|"
    r"(?P<m>\d+)\s*(?:m(?!s)|分钟|分)\s*|"
    r"(?P<s>\d+)\s*(?:s|秒)\s*"
)


def _parse_duration(text: str) -> int:
    """解析时间字符串为秒，失败返回 -1"""
    if not text:
        return -1
    total = 0
    matched = False
    for m in _TIME_RE.finditer(text):
        matched = True
        if m.group("d"):
            total += int(m.group("d")) * 86400
        if m.group("h"):
            total += int(m.group("h")) * 3600
        if m.group("m"):
            total += int(m.group("m")) * 60
        if m.group("s"):
            total += int(m.group("s"))
    return total if matched and total > 0 else -1


def _format_duration(seconds: int) -> str:
    """秒数 → 人类可读"""
    if seconds >= 86400:
        return f"{seconds // 86400}天"
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}小时{m}分钟" if m else f"{h}小时"
    if seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        return f"{m}分{s}秒" if s else f"{m}分钟"
    return f"{seconds}秒"


async def _check_bot_is_admin(bot: Bot, group_id: int) -> bool:
    """检查机器人是否群管理员"""
    try:
        info = await bot.get_group_member_info(
            group_id=group_id, user_id=bot.self_id
        )
        return info.get("role", "member") in ("admin", "owner")
    except Exception:
        return False


async def handle_mute(bot: Bot, event: MessageEvent):
    """禁言 / 解除禁言"""
    if event.message_type != "group":
        return

    operator_id = event.user_id
    group_id = event.group_id
    msg = event.get_plaintext().strip()

    # 解除禁言
    if msg.startswith("解除"):
        targets = [seg for seg in event.message if seg.type == "at"]
        if not targets:
            return
        target_id = int(targets[0].data["qq"])

        try:
            await bot.set_group_ban(group_id=group_id, user_id=target_id, duration=0)
            m_log.info(
                f"action=unmute operator={operator_id} group={group_id} "
                f"target={target_id} result=success"
            )
        except Exception as e:
            m_log.info(
                f"action=unmute operator={operator_id} group={group_id} "
                f"target={target_id} result=failed reason={e}"
            )
        return

    # 禁言
    if msg.startswith("禁言"):
        targets = [seg for seg in event.message if seg.type == "at"]
        if not targets:
            return
        target_id = int(targets[0].data["qq"])

        if await is_owner(target_id):
            m_log.info(
                f"action=mute_denied operator={operator_id} group={group_id} "
                f"target={target_id} result=denied reason=target_is_owner"
            )
            return

        raw_time = msg.removeprefix("禁言").strip()

        # 随机时长：-r min-max 或 -r（默认 1-60）
        m = re.search(r"-r\s*(\d*)-?(\d*)", raw_time)
        if m:
            lo = int(m.group(1)) if m.group(1) else 1
            hi = int(m.group(2)) if m.group(2) else 10
            if lo > hi:
                lo, hi = hi, lo
            duration = random.randint(lo, hi) * 60

        elif not raw_time:
            duration = 60  # 默认 1 分钟
        else:
            duration = _parse_duration(raw_time)
        if duration <= 0 or duration > 30 * 86400:
            return

        if not await _check_bot_is_admin(bot, group_id):
            m_log.info(
                f"action=mute operator={operator_id} group={group_id} "
                f"target={target_id} result=failed reason=bot_not_admin"
            )
            return

        try:
            await bot.set_group_ban(group_id=group_id, user_id=target_id, duration=duration)
            m_log.info(
                f"action=mute operator={operator_id} group={group_id} "
                f"target={target_id} result=success duration={duration}s"
            )
        except Exception as e:
            m_log.info(
                f"action=mute operator={operator_id} group={group_id} "
                f"target={target_id} result=failed reason={e}"
            )
        return


async def handle_self_mute(bot: Bot, event: MessageEvent):
    """自禁——任意用户可用，禁言自己"""
    if event.message_type != "group":
        return
    group_id = event.group_id
    operator_id = event.user_id
    raw = event.get_plaintext().strip().removeprefix("自禁").strip()
    if raw:
        dur = _parse_duration(raw)
        if dur <= 0 and raw.isdigit():
            dur = int(raw) * 60
        if dur > 3600:
            dur = 3600  # 上限 60 分钟
        duration = dur if dur > 0 else random.randint(1, 5) * 60
    else:
        duration = random.randint(1, 5) * 60

    try:
        await bot.set_group_ban(group_id=group_id, user_id=operator_id, duration=duration)
        m_log.info(
            f"action=mute operator={operator_id} group={group_id} "
            f"target={operator_id} result=success duration={duration}s type=self"
        )
        replies = get_runtime_config("SELF_MUTE_REPLIES", [])
        if replies:
            msg = MessageSegment.at(operator_id) + MessageSegment.text(random.choice(replies))
            await bot.send(event, msg)
    except Exception as e:
        m_log.info(
            f"action=mute operator={operator_id} group={group_id} "
            f"target={operator_id} result=failed reason={e} type=self"
        )


register(
    "mute", handle_mute,
    permission=Level.BotAdmin, cooldown_level=CooldownTier.Admin, hidden=True,
    aliases=["禁言", "解除"],
    accepts_args=True, group_only=True,
)
register(
    "self_mute", handle_self_mute,
    description="随机自禁言",
    permission=Level.User, cooldown_level=CooldownTier.Query,
    aliases=["自禁"],
    accepts_args=True, group_only=True,
)
