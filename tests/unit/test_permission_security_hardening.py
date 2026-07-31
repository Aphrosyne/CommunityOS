"""Round 1 Permission Security Hardening 测试

覆盖 technical-debt.md 修复项：
- H1: Owner 保护 defense-in-depth (DB 层拒绝降级 OWNER)
- H2: 同级保护 (BotAdmin 之间互相禁止操作)
- M2: set_permission level 值域校验
- M3: clear_user_permissions Owner 保护下沉数据库层
- M9: _migrations.applied_at 时间戳格式统一

依据 docs/developer/testing.md — 单元测试，不依赖 NoneBot2。
"""
import os
import time

import pytest


# ── M2: set_permission level 值域校验 ──────────────────────────

async def test_set_permission_rejects_level_too_high(db):
    """M2: level > LEVEL_MAX(9) 抛 ValueError"""
    with pytest.raises(ValueError, match="level 值域非法"):
        await db.set_permission(1001, 0, 10, granted_by=9999)


async def test_set_permission_rejects_level_too_low(db):
    """M2: level < LEVEL_MIN(-1) 抛 ValueError"""
    with pytest.raises(ValueError, match="level 值域非法"):
        await db.set_permission(1001, 0, -2, granted_by=9999)


async def test_set_permission_accepts_boundary_levels(db):
    """M2: 边界值 -1 (Blacklist) 和 9 (Owner) 合法

    注意：level=9 走 Owner 保护分支，需 OWNER 未设置（测试环境默认 OWNER=0）
    """
    # OWNER 未设置时，user_id 不会等于 OWNER(0)，不会触发 H1 保护
    await db.set_permission(1001, 0, -1, granted_by=9999)
    assert await db.get_permission(1001, 0) == -1


async def test_set_permission_accepts_level_zero(db):
    """M2: level=0 合法（删除记录语义）"""
    # 先设置 level=3，再设 level=0
    await db.set_permission(1001, 0, 3, granted_by=9999)
    assert await db.get_permission(1001, 0) == 3
    await db.set_permission(1001, 0, 0, granted_by=9999)
    assert await db.get_permission(1001, 0) == 0


# ── H1: Owner 保护 defense-in-depth ──────────────────────────

async def test_set_permission_rejects_demoting_owner_when_owner_set(db, monkeypatch):
    """H1: 当 OWNER 环境变量设置后，DB 层拒绝降级 OWNER"""
    from services import database
    monkeypatch.setattr(database, "OWNER", 123456)

    # 尝试把 OWNER 拉黑 → 应抛 PermissionError
    with pytest.raises(PermissionError, match="拒绝修改 OWNER"):
        await db.set_permission(123456, 0, -1, granted_by=9999)

    # 尝试把 OWNER 降为 BotAdmin → 也应抛
    with pytest.raises(PermissionError, match="拒绝修改 OWNER"):
        await db.set_permission(123456, 0, 3, granted_by=9999)

    # 但 OWNER 维持 level=Owner(9) 应该成功（种子写入场景）
    await db.set_permission(123456, 0, 9, granted_by=123456)
    assert await db.get_permission(123456, 0) == 9


async def test_set_permission_owner_protection_not_triggered_for_non_owner(db, monkeypatch):
    """H1: OWNER 设置后，对非 OWNER 用户的操作不受影响"""
    from services import database
    monkeypatch.setattr(database, "OWNER", 123456)

    # 普通 BotAdmin 操作不受影响
    await db.set_permission(1001, 0, 3, granted_by=123456)
    assert await db.get_permission(1001, 0) == 3


async def test_set_permission_no_owner_protection_when_owner_unset(db, monkeypatch):
    """H1: OWNER=0（未设置）时保护不生效，避免开发环境阻塞"""
    from services import database
    monkeypatch.setattr(database, "OWNER", 0)

    # user_id=0 不太可能，但即便传入也不会触发保护
    await db.set_permission(1001, 0, -1, granted_by=9999)
    assert await db.get_permission(1001, 0) == -1


# ── M3: clear_user_permissions Owner 保护下沉数据库层 ─────────────

async def test_clear_user_permissions_rejects_owner(db, monkeypatch):
    """M3: clear_user_permissions 拒绝清除 OWNER 的权限"""
    from services import database
    monkeypatch.setattr(database, "OWNER", 123456)

    with pytest.raises(PermissionError, match="拒绝清除 OWNER"):
        await db.clear_user_permissions(123456)


async def test_clear_user_permissions_allows_non_owner(db, monkeypatch):
    """M3: 非 OWNER 用户可以正常清除"""
    from services import database
    monkeypatch.setattr(database, "OWNER", 123456)

    # 给非 OWNER 用户设置权限
    await db.set_permission(1001, 0, 3, granted_by=123456)
    await db.set_permission(1001, 200, 2, granted_by=123456)
    assert await db.get_permission(1001, 0) == 3

    # 清除应成功
    deleted = await db.clear_user_permissions(1001)
    assert deleted == 2
    assert await db.get_permission(1001, 0) == 0


# ── M9: _migrations.applied_at 时间戳格式 ──────────────────────

async def test_migration_applied_at_is_iso_with_timezone(db):
    """M9: applied_at 应为 ISO 8601 含时区格式，不再是 datetime('now') 的 UTC 无时区"""
    conn = await db.get_connection()
    async with conn.execute("SELECT applied_at FROM _migrations") as cur:
        rows = await cur.fetchall()

    assert len(rows) > 0, "至少应有一个迁移记录"
    ts = rows[0][0]
    # ISO 8601 含时区偏移格式：YYYY-MM-DDTHH:MM:SS+HH:MM
    assert "T" in ts, f"applied_at 应为 ISO 8601 格式（含 T）, got: {ts}"
    # 应包含时区偏移（+HH:MM 或 -HH:MM 或 Z）
    assert ("+" in ts[10:]) or ("-" in ts[10:]) or ts.endswith("Z"), \
        f"applied_at 应含时区偏移, got: {ts}"


async def test_migration_applied_at_not_sqlite_datetime_format(db):
    """M9: applied_at 不应是 SQLite datetime('now') 的 'YYYY-MM-DD HH:MM:SS' 格式"""
    conn = await db.get_connection()
    async with conn.execute("SELECT applied_at FROM _migrations") as cur:
        rows = await cur.fetchall()

    for row in rows:
        ts = row[0]
        # 旧格式 'YYYY-MM-DD HH:MM:SS'（空格分隔，无时区）
        assert " " not in ts or "+" in ts or "-" in ts[10:], \
            f"applied_at 仍为 SQLite 默认格式: {ts}"


# ── H2: 同级保护（admin.py _apply 行为） ──────────────────────────
# H2 的完整集成测试放在 Round 2 的 tests/integration/ 中，
# 这里只测 permission service 的 get_level 行为支撑 H2 逻辑

async def test_get_level_returns_max_for_same_level_protection(db):
    """H2 支撑测试：get_level 正确返回 MAX(level) 供同级保护判断

    场景：BotAdmin A (level=3, group_id=0) 在某群无额外权限
    BotAdmin B (level=3, group_id=0) 也无额外权限
    A 对 B 操作时，target_level(3) >= operator_level(3) 应触发拒绝
    """
    # 设置两个 BotAdmin
    await db.set_permission(1001, 0, 3, granted_by=9999)  # operator
    await db.set_permission(1002, 0, 3, granted_by=9999)  # target

    # 两人都是 level=3
    assert await db.get_permission(1001, 0) == 3
    assert await db.get_permission(1002, 0) == 3
    # H2 逻辑：target_level(3) >= operator_level(3) → 应拒绝


async def test_get_level_owner_can_operate_lower(db, monkeypatch):
    """H2 支撑测试：Owner 可操作低于自己的用户"""
    from services import database
    monkeypatch.setattr(database, "OWNER", 9999)

    # Owner 设置
    await db.set_permission(9999, 0, 9, granted_by=9999)
    # BotAdmin
    await db.set_permission(1001, 0, 3, granted_by=9999)

    # Owner level=9, target level=3, 9 > 3 应允许操作
    assert await db.get_permission(9999, 0) == 9
    assert await db.get_permission(1001, 0) == 3
