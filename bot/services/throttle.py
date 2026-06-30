"""
ThrottleService — 控制机器人回复频率，防止刷屏

与 Cooldown（限制用户行为）和 Session（管理多步交互）不同，
Throttle 限制的是机器人对重复消息的回复频率。

规则：同一个 (user_id, reply_type) 在窗口时间内只回复一次。
"""
import time

from services.logger import get_logger

logger = get_logger(__name__)

# {(user_id, reply_type): last_reply_timestamp}
_sent: dict[tuple[int, str], float] = {}

DEFAULT_WINDOW = 5  # 默认沉默窗口秒数


def should_reply(user_id: int, reply_type: str, window: int = DEFAULT_WINDOW) -> bool:
    """是否应该回复

    第一次调用返回 True 并记录时间戳；
    窗口期内再次调用返回 False。

    Args:
        user_id: 用户 QQ 号
        reply_type: 提示类型（如 "cooldown"、"publish_session"、"not_found"）
        window: 沉默窗口秒数，默认 5
    """
    key = (user_id, reply_type)
    now = time.time()
    last = _sent.get(key, 0)

    if now - last >= window:
        _sent[key] = now
        return True

    return False
