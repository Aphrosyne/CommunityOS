"""
指令分发器 - 按首词匹配已注册命令

规则：
    - 私聊：直接发命令名触发
    - 群聊：@bot 命令名 触发
    - 只匹配已注册命令，未注册的忽略（无提示）
    - 30 秒全局冷却
"""
import re
import time

from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.typing import T_State

from services.command import get as get_command
from services.config import COMMAND_COOLDOWNS
from services.permission import check as check_permission, is_owner
from services.shortcut import match as shortcut_match
from services.message_rule import check_command
from services.logger import get_logger

logger = get_logger("command")
_mod_log = get_logger("moderation")

# 冷却: {(user_id, group_id): {cooldown_level: last_time}}  # group_id=0 表示私聊
_cooldowns: dict[tuple[int, int], dict[int, float]] = {}

def _rule(event: MessageEvent) -> bool:
    return check_command(
        msg_type=event.message_type,
        group_id=getattr(event, "group_id", 0),
        to_me=event.to_me,
        text=event.get_plaintext(),
    )


dispatcher = on_message(rule=_rule, priority=1, block=False)


@dispatcher.handle()
async def dispatch(bot: Bot, event: MessageEvent, state: T_State):
    # 取首词作为命令名
    msg = event.get_plaintext().strip()
    if not msg:
        return

    cmd_name = msg.split()[0].lower()
    user_id = event.user_id
    group_id = getattr(event, "group_id", 0) or 0

    # 快捷映射：全句匹配 → 替换指令
    shortcut = shortcut_match(msg)
    if shortcut is not None:
        at_segs = [seg for seg in event.message if seg.type == "at"]
        at_target = at_segs[0].data["qq"] if at_segs else ""
        translated = shortcut.replace("{at}", f"[CQ:at,qq={at_target}]")

        # 解析 [CQ:at,qq=xxx] → MessageSegment（逆序插入保持原文顺序）
        parts = re.split(r"(\[CQ:at,qq=\d+\])", translated)
        for part in reversed(parts):
            m = re.match(r"\[CQ:at,qq=(\d+)\]", part)
            if m:
                event.message.insert(0, MessageSegment.at(m.group(1)))
            elif part.strip():
                event.message.insert(0, MessageSegment.text(part))

        cmd_name = re.sub(r"\[CQ:at,qq=\d+\]", "", translated).strip().split()[0].lower()

    # 只处理已注册命令，未注册的静默忽略
    cmd = get_command(cmd_name)
    if cmd is None:
        return

    # 冷却检查（Owner 豁免，分群独立）
    if not is_owner(user_id):
        level = cmd["cooldown_level"]
        cd_seconds = COMMAND_COOLDOWNS.get(level, 5)
        now = time.time()
        ck = (user_id, group_id)
        user_cd = _cooldowns.setdefault(ck, {})
        last = user_cd.get(level, 0)
        if now - last < cd_seconds:
            return  # 冷却期静默
        user_cd[level] = now

    # 权限检查（Bot Admin，非 QQ 群管理员）
    if not check_permission(user_id, cmd["permission"]):
        logger.info(f"用户 {user_id} 权限不足，拒绝执行 {cmd_name} (需要 {cmd['permission']})")
        _mod_log.info(
            f"action=permission_denied operator={user_id} "
            f"group={group_id} target=0 result=denied "
            f"reason=command={cmd_name} required_level={cmd['permission']}"
        )
        return

    # 调用
    logger.info(f"用户 {user_id} 执行命令: {cmd_name}")
    try:
        await cmd["handler"](bot, event)
    except Exception as e:
        logger.error(f"命令 {cmd_name} 执行异常: {e}")
        await dispatcher.finish("命令执行出错，请稍后重试。")
