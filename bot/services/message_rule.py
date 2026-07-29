"""
Message Rule Service — 群消息规则匹配与路由

职责：接收群消息，按规则判断是否命中，返回匹配结果。
不执行指令、不撤回消息，只做匹配与路由。
"""
from services.command import get as get_command, matches_args
from services import runtime_config
from services.permission import Level
from services.shortcut import match as shortcut_match
from services.logger import get_logger


def check_command(msg_type: str, group_id: int, to_me: bool, text: str) -> bool:
    """判断消息是否应路由到 Command System

    私聊 → 总是通过。
    群聊 → @bot 通过；管理群内低权限命令（<2）免 @bot 也通过。
    """
    if msg_type == "private":
        return True
    if to_me:
        return True

    if group_id not in runtime_config.get("MANAGED_GROUPS", []):
        return False

    # 先查 shortcut 映射，取映射后命令的首词
    sc = shortcut_match(text.strip(), group_id=group_id)
    actual = sc if sc is not None else text
    actual = actual.strip()
    if not actual:
        return False
    words = actual.split()
    word = words[0].lower()
    cmd = get_command(word)
    if not cmd or cmd.get("permission", 0) >= Level.BotAdmin:
        return False

    # 无 @ 路径精确匹配规则（设计文档 4.2）：
    # shortcut 命中时跳过（显式配置应信任）；否则按 accepts_args 规则校验
    if sc is not None:
        return True
    return matches_args(cmd, words)


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
    except Exception as e:
        log = get_logger("bot")
        log.error(f"加载 keywords.json 失败: {e}")
        _keywords = {}


def reload_keywords() -> tuple[bool, str]:
    """重新加载 keywords.json

    Returns:
        (success, error_msg)
    """
    global _keywords
    try:
        if not _KEYWORDS_PATH.exists():
            _keywords = {}
            return False, f"配置文件不存在: {_KEYWORDS_PATH.name}"
        _keywords = json.loads(_KEYWORDS_PATH.read_text(encoding="utf-8"))
        return True, ""
    except Exception as e:
        log = get_logger("bot")
        log.error(f"重载 keywords.json 失败: {e}")
        _keywords = {}
        return False, str(e)


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
