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
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.exception import MatcherException
from nonebot.typing import T_State

from services.command import get as get_command, matches_args
from services.config import COMMAND_COOLDOWNS
from services.permission import (
    Level,
    get_level,
)
from services.shortcut import match as shortcut_match
from services.message_rule import check_command
from services import database
from services.logger import get_logger

logger = get_logger("command")
_mod_log = get_logger("moderation")


async def _log_cmd(
    user_id: int,
    group_id: int,
    command_name: str,
    raw_text: str | None,
    result: str,
) -> None:
    """写入指令日志到 DB，失败仅记日志不抛出（Q1-A 额外要求）"""
    try:
        await database.log_command(
            user_id=user_id,
            group_id=group_id,
            command_name=command_name,
            raw_text=raw_text,
            result=result,
        )
    except Exception:
        logger.exception(f"DB 写入失败: command_log cmd={command_name} result={result}")

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
    shortcut_hit = False
    # H3: 保存原始消息引用，shortcut 展开用新 Message 对象替换 event.message，
    # handler 执行完毕后恢复原始消息，避免污染其它 matcher 读到的 event.message。
    original_message = event.message

    # 快捷映射：全句匹配 → 替换指令
    shortcut = shortcut_match(msg, group_id=group_id)
    if shortcut is not None:
        shortcut_hit = True
        at_segs = [seg for seg in event.message if seg.type == "at"]
        at_target = at_segs[0].data["qq"] if at_segs else ""
        translated = shortcut.replace("{at}", f"[CQ:at,qq={at_target}]")

        # 解析 [CQ:at,qq=xxx] → MessageSegment，构造新 Message 对象
        # H3: 不再 event.message.clear() / extend() 原地修改，改为构造新 Message
        new_msg = Message()
        parts = re.split(r"(\[CQ:at,qq=\d+\])", translated)
        for part in parts:
            m = re.match(r"\[CQ:at,qq=(\d+)\]", part)
            if m:
                new_msg.append(MessageSegment.at(m.group(1)))
            elif part.strip():
                new_msg.append(MessageSegment.text(part))
        # 临时替换 event.message，handler 看到展开后的消息
        event.message = new_msg

        words = re.sub(r"\[CQ:at,qq=\d+\]", "", translated).strip().split()
        cmd_name = words[0].lower() if words else ""
        if not cmd_name:
            event.message = original_message  # 恢复
            return

    try:
        # 只处理已注册命令，未注册的静默忽略
        cmd = get_command(cmd_name)
        if cmd is None:
            return

        # 参数规则校验（accepts_args）：
        #   False → 纯指令；True → 任意参数；Sequence[str] → 白名单
        # shortcut 命中时跳过：快捷映射是显式配置，应信任
        if not shortcut_hit:
            if not matches_args(cmd, msg.split()):
                return

        # 场景校验：group_only 命令在私聊中直接忽略
        # （不消耗冷却、不调用 handler）
        if cmd.get("group_only") and event.message_type != "group":
            return

        # M7: 单次 get_level 取得用户有效权限，本地判断 blacklist/owner/required
        # 避免 is_blacklisted + is_owner + check_permission 三次 SELECT
        user_level = await get_level(user_id, group_id)

        # 黑名单拦截（Q8-A: 静默忽略，不消耗冷却）
        if user_level == Level.Blacklist:
            return

        # 冷却检查（Owner 豁免，分群独立）
        if user_level < Level.Owner:
            level = cmd["cooldown_level"]
            cd_seconds = COMMAND_COOLDOWNS.get(level, 5)
            now = time.time()
            ck = (user_id, group_id)
            user_cd = _cooldowns.setdefault(ck, {})
            last = user_cd.get(level, 0)
            if now - last < cd_seconds:
                return  # 冷却期静默
            user_cd[level] = now

        # 权限检查（基于数据库，Q5-A fail-closed）
        # user_level 由 get_level fail-closed 返回（异常时返回 0）
        if user_level < cmd["permission"]:
            logger.info(
                f"用户 {user_id} 权限不足，拒绝执行 {cmd_name} "
                f"(需要 {cmd['permission']}, 实际 {user_level})"
            )
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
        except MatcherException:
            # NoneBot 控制流异常（finish/pause/reject 等）属于正常执行完成
            await _log_cmd(user_id, group_id, cmd_name, msg, "success")
            raise
        except Exception as e:
            logger.error(f"命令 {cmd_name} 执行异常: {e}")
            await _log_cmd(user_id, group_id, cmd_name, msg, "error")
            await dispatcher.finish("命令执行出错，请稍后重试。")
        else:
            await _log_cmd(user_id, group_id, cmd_name, msg, "success")
    finally:
        # H3: 恢复原始 event.message，避免污染后续 matcher
        event.message = original_message
