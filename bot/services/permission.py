"""
Permission Service — 统一权限检查

权限等级：
    User  (0) — 普通用户，所有公开功能
    Admin (1) — Bot 管理员（非 QQ 群管理员），机器人控制与跨群管理
    Owner (2) — 机器人所有者，系统级操作
"""
from services.config import OWNER, ADMINS
from services.logger import get_logger

logger = get_logger("command")


class Level:
    User = 0
    Admin = 1
    Owner = 2


def get_level(user_id: int) -> int:
    """返回用户权限等级"""
    if user_id == OWNER:
        return Level.Owner
    if user_id in ADMINS:
        return Level.Admin
    return Level.User


def check(user_id: int, required: int) -> bool:
    """检查用户是否满足最低权限要求"""
    return get_level(user_id) >= required


def is_owner(user_id: int) -> bool:
    """Owner 身份判断，用于冷却豁免等"""
    return user_id == OWNER
