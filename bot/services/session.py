"""
SessionService — 通用多步交互会话管理

所有需要多步交互的插件复用此服务。
"""
import time
from dataclasses import dataclass, field
from typing import Any

from services.logger import get_logger

logger = get_logger(__name__)

# {user_id: {session_type: Session}}
_sessions: dict[str, dict[str, "Session"]] = {}


@dataclass
class Session:
    user_id: str
    session_type: str
    state: str = "active"  # active | complete | cancelled
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def __post_init__(self):
        if not self.expires_at:
            self.expires_at = self.created_at + 300  # 默认 5 分钟


def create(
    user_id: int,
    session_type: str,
    timeout: int = 300,
    initial_data: dict[str, Any] | None = None,
) -> Session:
    """创建新会话，覆盖同类型旧会话"""
    uid = str(user_id)
    session = Session(
        user_id=uid,
        session_type=session_type,
        data=initial_data or {},
        expires_at=time.time() + timeout,
    )
    _sessions.setdefault(uid, {})[session_type] = session
    logger.info(f"会话创建: user={uid} type={session_type} timeout={timeout}s")
    return session


def get_active(user_id: int, session_type: str) -> Session | None:
    """获取活跃会话，超时自动清理"""
    uid = str(user_id)
    user_sessions = _sessions.get(uid, {})
    session = user_sessions.get(session_type)

    if session is None:
        return None

    if session.state != "active":
        return None

    if time.time() > session.expires_at:
        session.state = "cancelled"
        del user_sessions[session_type]
        logger.info(f"会话超时: user={uid} type={session_type}")
        return None

    return session


def append_data(session: Session, data: dict[str, Any]) -> None:
    """向会话追加数据"""
    session.data.update(data)


def complete(session: Session) -> None:
    """完成会话"""
    session.state = "complete"
    _sessions.get(session.user_id, {}).pop(session.session_type, None)
    logger.info(f"会话完成: user={session.user_id} type={session.session_type}")


def cancel(session: Session) -> None:
    """取消会话"""
    session.state = "cancelled"
    _sessions.get(session.user_id, {}).pop(session.session_type, None)
    logger.info(f"会话取消: user={session.user_id} type={session.session_type}")


def get_expired(session_type: str) -> list[int]:
    """扫描所有超时会话，取消并返回用户 ID 列表"""
    expired = []
    now = time.time()
    for uid, user_sessions in list(_sessions.items()):
        session = user_sessions.get(session_type)
        if session and session.state == "active" and now > session.expires_at:
            session.state = "cancelled"
            del user_sessions[session_type]
            logger.info(f"会话超时: user={uid} type={session_type}")
            expired.append(int(uid))
    return expired
