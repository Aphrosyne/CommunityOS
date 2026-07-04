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


# ── 违禁词 ──

import json  # noqa: E402
from pathlib import Path  # noqa: E402

_KEYWORDS_PATH = Path(__file__).resolve().parent.parent / "config" / "keywords.json"
_keywords: dict[str, list[str]] = {}


def _load_keywords() -> None:
    global _keywords
    try:
        if _KEYWORDS_PATH.exists():
            _keywords = json.loads(_KEYWORDS_PATH.read_text(encoding="utf-8"))
        else:
            _keywords = {}
    except Exception:
        _keywords = {}


def check_keywords(group_id: int, text: str) -> list[str]:
    """返回命中的违禁词列表。先查群专属，再查全局 *"""
    hits = []
    gid = str(group_id)
    for kw in _keywords.get(gid, []):
        if kw in text:
            hits.append(kw)
    for kw in _keywords.get("*", []):
        if kw not in hits and kw in text:
            hits.append(kw)
    return hits


def list_keywords(group_id: int) -> list[str]:
    """返回该群的关键词列表（群专属 + 全局去重）"""
    gid = str(group_id)
    all_kw = list(_keywords.get("*", []))
    for kw in _keywords.get(gid, []):
        if kw not in all_kw:
            all_kw.append(kw)
    return all_kw


_load_keywords()
