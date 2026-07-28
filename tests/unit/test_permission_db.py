"""权限 Repository 测试（set_permission / get_permission）

依据 docs/developer/testing.md — 单元测试，不依赖 NoneBot2。
覆盖 Round 3 设计确认的 Q1-A/Q4-A/Q5-A/Q6-A/Q11/Q13-A 等决策。
"""
import time

import pytest


async def test_no_record_returns_zero(db):
    """无任何权限记录的用户返回 0（普通用户）"""
    level = await db.get_permission(1001, 0)
    assert level == 0


async def test_set_and_get_permission(db):
    """set_permission 后 get_permission 返回正确 level"""
    await db.set_permission(1001, 0, 3, granted_by=9999, reason="test")
    assert await db.get_permission(1001, 0) == 3


async def test_set_level_zero_removes_record(db):
    """Q11: set_permission(level=0) 等价于无记录"""
    await db.set_permission(1001, 0, 3, granted_by=9999)
    assert await db.get_permission(1001, 0) == 3
    await db.set_permission(1001, 0, 0, granted_by=9999)
    assert await db.get_permission(1001, 0) == 0


async def test_high_level_overrides_low(db):
    """Q11: 高级覆盖低级，用户只有当前最高 level"""
    await db.set_permission(1001, 0, 1, granted_by=9999)  # Whitelist
    assert await db.get_permission(1001, 0) == 1
    await db.set_permission(1001, 0, 3, granted_by=9999)  # BotAdmin 覆盖
    assert await db.get_permission(1001, 0) == 3
    # 不应同时存在 level=1 和 level=3
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM user_permissions WHERE user_id = 1001"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_blacklist_level(db):
    """黑名单 level=-1"""
    await db.set_permission(1001, 0, -1, granted_by=9999, reason="blacklist")
    assert await db.get_permission(1001, 0) == -1


async def test_owner_level(db):
    """Owner level=9"""
    await db.set_permission(1001, 0, 9, granted_by=9999, reason="seed")
    assert await db.get_permission(1001, 0) == 9


async def test_global_permission_applies_to_all_groups(db):
    """全局权限(group_id=0)对所有群生效"""
    await db.set_permission(1001, 0, 3, granted_by=9999)
    # 在不同群查询也应返回全局 level
    assert await db.get_permission(1001, 111) == 3
    assert await db.get_permission(1001, 222) == 3


async def test_group_level_overrides_global(db):
    """群级权限与全局权限取 MAX"""
    await db.set_permission(1001, 0, 1, granted_by=9999)   # 全局白名单
    await db.set_permission(1001, 111, 3, granted_by=9999)  # 群 111 管理员
    # 群 111 查询应取 MAX(1, 3) = 3
    assert await db.get_permission(1001, 111) == 3
    # 其他群只有全局 1
    assert await db.get_permission(1001, 222) == 1


async def test_expired_permission_ignored(db):
    """Q6-A: 过期权限自动失效"""
    # 设置一个已过期的权限
    expired = "2020-01-01T00:00:00+08:00"
    await db.set_permission(
        1001, 0, 3, granted_by=9999, expires_at=expired
    )
    # 查询应返回 0（过期失效）
    assert await db.get_permission(1001, 0) == 0


async def test_non_expired_permission_valid(db):
    """Q6-A: 未过期权限有效"""
    # 设置一个未来过期的权限
    future = "2099-12-31T23:59:59+08:00"
    await db.set_permission(
        1001, 0, 3, granted_by=9999, expires_at=future
    )
    assert await db.get_permission(1001, 0) == 3


async def test_permanent_permission_no_expiry(db):
    """永久权限(expires_at=NULL)不过期"""
    await db.set_permission(
        1001, 0, 9, granted_by=9999, expires_at=None
    )
    assert await db.get_permission(1001, 0) == 9


async def test_set_permission_auto_upserts_user(db):
    """set_permission 自动 upsert_user 保证 FK"""
    await db.set_permission(1001, 0, 3, granted_by=9999)
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = 1001"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_set_permission_idempotent(db):
    """重复 set 同一权限不重复插入（覆盖语义）"""
    await db.set_permission(1001, 0, 3, granted_by=9999)
    await db.set_permission(1001, 0, 3, granted_by=9999)
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM user_permissions WHERE user_id = 1001"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_demote_via_set_zero(db):
    """Q11: 降级流程 whitelist → user → blacklist"""
    await db.set_permission(1001, 0, 1, granted_by=9999)   # Whitelist
    assert await db.get_permission(1001, 0) == 1
    await db.set_permission(1001, 0, 0, granted_by=9999)   # 降为 User
    assert await db.get_permission(1001, 0) == 0
    await db.set_permission(1001, 0, -1, granted_by=9999)  # Blacklist
    assert await db.get_permission(1001, 0) == -1


# ── permission service 层测试（通过 manager 参数注入） ──

from services.permission import (
    check, is_owner, is_blacklisted, get_level, Level,
)


async def test_check_permission_granted(db):
    """check() 返回 True 当 level >= required"""
    await db.set_permission(1001, 0, 3, granted_by=9999)
    assert await check(1001, 0, 3, manager=db) is True
    assert await check(1001, 0, 0, manager=db) is True  # BotAdmin > User


async def test_check_permission_denied(db):
    """check() 返回 False 当 level < required"""
    await db.set_permission(1001, 0, 0, granted_by=9999)  # User
    assert await check(1001, 0, 3, manager=db) is False


async def test_check_blacklist_denies_all(db):
    """Q5-A: 黑名单禁止任何功能，即使 required=0"""
    await db.set_permission(1001, 0, -1, granted_by=9999)
    assert await check(1001, 0, 0, manager=db) is False
    assert await check(1001, 0, -1, manager=db) is False


async def test_is_owner(db):
    """is_owner 判断"""
    await db.set_permission(1001, 0, 9, granted_by=9999)
    assert await is_owner(1001, manager=db) is True
    assert await is_owner(1002, manager=db) is False  # 无记录


async def test_is_blacklisted(db):
    """is_blacklisted 判断"""
    await db.set_permission(1001, 0, -1, granted_by=9999)
    assert await is_blacklisted(1001, 0, manager=db) is True
    assert await is_blacklisted(1002, 0, manager=db) is False


async def test_get_level_defaults_zero(db):
    """get_level 对无记录用户返回 0"""
    assert await get_level(1001, 0, manager=db) == 0


async def test_level_constants():
    """Level 常量值正确"""
    assert Level.Blacklist == -1
    assert Level.User == 0
    assert Level.Whitelist == 1
    assert Level.GroupAdmin == 2
    assert Level.BotAdmin == 3
    assert Level.Owner == 9
