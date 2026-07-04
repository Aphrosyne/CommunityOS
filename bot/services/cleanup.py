"""定期清理过期条目——防止内存无限增长"""
import time

from services.logger import get_logger

logger = get_logger("bot")

CLEANUP_INTERVAL = 600  # 10 分钟


async def run_cleanup() -> None:
    """清理所有增长字典中的过期键"""
    now = time.time()
    removed = 0

    # ── publish/obfuscate/decode _cd_expires ──
    for plugin_name in ("publish", "obfuscate", "decode"):
        try:
            mod = __import__(f"plugins.{plugin_name}", fromlist=["_cd_expires"])
            cd: dict = mod._cd_expires
            expired = [uid for uid, exp in cd.items() if now > exp]
            for uid in expired:
                del cd[uid]
            removed += len(expired)
        except Exception:
            pass

    # ── command_dispatcher _cooldowns ──
    try:
        from plugins.command_dispatcher import _cooldowns as cds
        expired = [k for k, inner in list(cds.items())
                   for _, t in inner.items() if now - t > 30]
        for k in expired:
            del cds[k]
        removed += len(expired)
    except Exception:
        pass

    # ── throttle _sent ──
    try:
        from services.throttle import _sent
        expired = [k for k, t in _sent.items() if now - t > 60]
        for k in expired:
            del _sent[k]
        removed += len(expired)
    except Exception:
        pass

    # ── session _sessions 空外层 ──
    try:
        from services.session import _sessions
        empty = [uid for uid, inner in _sessions.items() if not inner]
        for uid in empty:
            del _sessions[uid]
        removed += len(empty)
    except Exception:
        pass

    if removed:
        logger.info(f"内存清理: 移除 {removed} 个过期条目")
