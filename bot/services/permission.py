"""
Permission Service — 统一权限检查（基于数据库）

依据:
    docs/design/database.md §3.1 权限层级
    docs/design/database-roadmap.md Round 3

权限等级（9 级体系，Q1-A 迁移）:
    -1  黑名单  Blacklist      禁止使用任何功能
     0  普通    User           默认等级
     1  白名单  Whitelist      豁免批量清人（后续轮次）
     2  群管理  GroupAdmin     仅对应群内有效（后续轮次）
     3  管理员  BotAdmin       跨群机器人管理
     9  拥有者  Owner          最高权限

旧值映射（Q1-A）:
    旧 0 (User)   → 0
    旧 1 (Admin)  → 3
    旧 2 (Owner)  → 9

失败策略（Q5-A fail-closed）:
    DB 查询失败 → 权限检查默认拒绝（视为无权限）。
    调用方应捕获异常并决定是否继续，但 check() 本身返回 False。

Q7-A 测试注入:
    所有查询函数接收可选 manager 参数，默认用 database._manager 单例。
    测试时传入 db fixture（DatabaseManager 实例）。
"""
from __future__ import annotations

from services import database
from services.config import OWNER, ADMINS
from services.database import DatabaseManager
from services.logger import get_logger

logger = get_logger("command")


class Level:
    """权限等级常量（对应 database.md §3.1）"""
    Blacklist = -1
    User = 0
    Whitelist = 1
    GroupAdmin = 2
    BotAdmin = 3
    Owner = 9


async def get_level(
    user_id: int,
    group_id: int = 0,
    *,
    manager: DatabaseManager | None = None,
) -> int:
    """返回用户在指定群的有效权限等级

    group_id=0 表示私聊/全局场景，只查全局权限。
    """
    mgr = manager if manager is not None else database._manager
    try:
        return await mgr.get_permission(user_id, group_id)
    except Exception:
        logger.exception(
            f"权限查询失败: user={user_id} group={group_id}"
        )
        return 0  # fail-closed：查询失败视为普通用户


async def check(
    user_id: int,
    group_id: int,
    required: int,
    *,
    manager: DatabaseManager | None = None,
) -> bool:
    """检查用户是否满足最低权限要求

    Q5-A fail-closed: 黑名单(level=-1) 或查询失败 → 拒绝。
    """
    level = await get_level(user_id, group_id, manager=manager)
    if level == Level.Blacklist:
        return False  # 黑名单禁止任何功能
    return level >= required


async def is_owner(
    user_id: int,
    *,
    manager: DatabaseManager | None = None,
) -> bool:
    """Owner 身份判断，用于冷却豁免等（Q2-A 仅 Owner 豁免冷却）"""
    return await get_level(user_id, 0, manager=manager) >= Level.Owner


async def is_blacklisted(
    user_id: int,
    group_id: int = 0,
    *,
    manager: DatabaseManager | None = None,
) -> bool:
    """黑名单判断"""
    return await get_level(user_id, group_id, manager=manager) == Level.Blacklist


async def seed_from_env() -> None:
    """启动时从 .env 种子写入 Owner 和 Admins（幂等）

    Q3-A: ADMINS 也种子写入 level=3。
    种子写入使用 set_permission（覆盖语义），保证重启后权限不丢失。
    """
    if OWNER:
        await database.set_permission(
            user_id=OWNER,
            group_id=0,
            level=Level.Owner,
            granted_by=OWNER,
            reason="seed from .env OWNER",
        )
        logger.info(f"Owner 种子写入: {OWNER}")

    for admin_id in ADMINS:
        await database.set_permission(
            user_id=admin_id,
            group_id=0,
            level=Level.BotAdmin,
            granted_by=OWNER if OWNER else admin_id,
            reason="seed from .env ADMINS",
        )
        logger.info(f"BotAdmin 种子写入: {admin_id}")
