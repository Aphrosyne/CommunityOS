"""
禁言指令 - 群聊 @bot 禁言/解除禁言 @用户 [时长]
"""
import re

from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register
from services.config import OWNER
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
        await bot.send(event, "禁言指令仅限群聊使用。")
        return

    operator_id = event.user_id
    group_id = event.group_id

    msg = event.get_plaintext().strip()

    # 解除禁言
    if msg.startswith("解除禁言"):
        targets = [seg for seg in event.message if seg.type == "at"]
        if not targets:
            await bot.send(event, "请 @ 要解除禁言的用户。")
            return
        target_id = int(targets[0].data["qq"])

        try:
            await bot.set_group_ban(group_id=group_id, user_id=target_id, duration=0)
            m_log.info(
                f"action=unmute operator={operator_id} group={group_id} "
                f"target={target_id} result=success"
            )
            await bot.send(event, "已解除禁言。")
        except Exception as e:
            m_log.info(
                f"action=unmute operator={operator_id} group={group_id} "
                f"target={target_id} result=failed reason={e}"
            )
            await bot.send(event, "解除禁言失败，请检查机器人是否有管理权限。")
        return

    # 禁言
    if msg.startswith("禁言"):
        targets = [seg for seg in event.message if seg.type == "at"]
        if not targets:
            await bot.send(event, "请 @ 要禁言的用户，例如：@bot 禁言 @用户 10m")
            return
        target_id = int(targets[0].data["qq"])

        # 不允许禁言 Owner
        if target_id == OWNER:
            m_log.info(
                f"action=mute_denied operator={operator_id} group={group_id} "
                f"target={target_id} result=denied reason=target_is_owner"
            )
            await bot.send(event, "无法对 Owner 执行此操作。")
            return

        # 解析时长
        raw_time = msg.removeprefix("禁言").strip()
        if not raw_time:
            await bot.send(event, "请指定禁言时长，例如：@bot 禁言 @用户 10m")
            return

        duration = _parse_duration(raw_time)
        if duration <= 0:
            await bot.send(event, "无法识别的时长格式。支持：1m, 10m, 1h, 1d, 1分钟, 1小时 等")
            return

        if duration > 30 * 86400:
            await bot.send(event, "禁言时长不能超过 30 天。")
            return

        # 检查机器人是否有管理权限
        if not await _check_bot_is_admin(bot, group_id):
            m_log.info(
                f"action=mute operator={operator_id} group={group_id} "
                f"target={target_id} result=failed reason=bot_not_admin"
            )
            await bot.send(event, "机器人不是本群管理员，无法执行禁言操作。")
            return

        try:
            await bot.set_group_ban(group_id=group_id, user_id=target_id, duration=duration)
            m_log.info(
                f"action=mute operator={operator_id} group={group_id} "
                f"target={target_id} result=success duration={duration}s"
            )
            await bot.send(event, f"已禁言 {_format_duration(duration)}。")
        except Exception as e:
            m_log.info(
                f"action=mute operator={operator_id} group={group_id} "
                f"target={target_id} result=failed reason={e}"
            )
            await bot.send(event, "禁言失败，请检查机器人是否有管理权限。")
        return

    # 未匹配


register(
    "mute", handle_mute,
    permission=1, cooldown_level=2, hidden=True,
    aliases=["禁言", "解除禁言"],
)
