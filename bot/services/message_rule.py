"""
Message Rule Service — 群消息规则匹配与路由

职责：接收群消息，按规则判断是否命中，返回匹配结果。
不执行指令、不撤回消息，只做匹配与路由。
"""
from services.command import get as get_command
from services.config import MANAGED_GROUPS
from services.shortcut import match as shortcut_match


def check_command(msg_type: str, group_id: int, to_me: bool, text: str) -> bool:
    """判断消息是否应路由到 Command System

    私聊 → 总是通过。
    群聊 → @bot 通过；管理群内低权限命令（<2）免 @bot 也通过。
    """
    if msg_type == "private":
        return True
    if to_me:
        return True

    if group_id not in MANAGED_GROUPS:
        return False

    # 先查 shortcut 映射，取映射后命令的首词
    sc = shortcut_match(text.strip(), group_id=group_id)
    actual = sc if sc else text
    word = actual.strip().split()[0].lower() if actual.strip() else ""
    cmd = get_command(word)
    if cmd and cmd.get("permission", 0) < 2:
        return True

    return False
