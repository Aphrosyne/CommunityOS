"""record_membership 测试

依据 docs/developer/testing.md — 单元测试，不依赖 NoneBot2。
"""
import pytest


async def _fetch_membership(conn, user_id, group_id):
    async with conn.execute(
        "SELECT status, joined_at, left_at, join_count, last_event "
        "FROM group_memberships WHERE user_id = ? AND group_id = ?",
        (user_id, group_id),
    ) as cur:
        return await cur.fetchone()


async def test_first_join(db):
    """首次入群：status=active, join_count=1, left_at=NULL"""
    await db.record_membership(1001, 789012, "join")
    conn = await db.get_connection()
    row = await _fetch_membership(conn, 1001, 789012)
    assert row is not None
    assert row[0] == "active"
    assert row[1] is not None   # joined_at
    assert row[2] is None       # left_at
    assert row[3] == 1          # join_count
    assert row[4] == "join"     # last_event


async def test_leave_after_join(db):
    """退群：status=left, left_at 非空, last_event=leave"""
    await db.record_membership(1001, 789012, "join")
    await db.record_membership(1001, 789012, "leave")
    conn = await db.get_connection()
    row = await _fetch_membership(conn, 1001, 789012)
    assert row[0] == "left"
    assert row[2] is not None   # left_at
    assert row[4] == "leave"


async def test_kick_after_join(db):
    """被踢：status=kicked, left_at 非空, last_event=kick"""
    await db.record_membership(1001, 789012, "join")
    await db.record_membership(1001, 789012, "kick")
    conn = await db.get_connection()
    row = await _fetch_membership(conn, 1001, 789012)
    assert row[0] == "kicked"
    assert row[2] is not None   # left_at
    assert row[4] == "kick"


async def test_rejoin_increments_join_count(db):
    """反复进出：join→leave→join，join_count=2，left_at 被 NULL 化"""
    await db.record_membership(1001, 789012, "join")   # count=1
    await db.record_membership(1001, 789012, "leave")  # count 仍 1
    await db.record_membership(1001, 789012, "join")   # count=2
    conn = await db.get_connection()
    row = await _fetch_membership(conn, 1001, 789012)
    assert row[0] == "active"
    assert row[2] is None       # left_at 重新 NULL 化
    assert row[3] == 2          # join_count 递增
    assert row[4] == "join"


async def test_join_auto_upserts_user(db):
    """join 前自动 upsert_user（FK 约束满足）"""
    await db.record_membership(1001, 789012, "join")
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = 1001"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_leave_no_history_inserts_stub(db):
    """Q3-B: 无历史记录的 leave 插入存根（joined_at=NULL, join_count=0）"""
    await db.record_membership(1001, 789012, "leave")
    conn = await db.get_connection()
    row = await _fetch_membership(conn, 1001, 789012)
    assert row is not None
    assert row[0] == "left"
    assert row[1] is None       # joined_at NULL（存根）
    assert row[2] is not None   # left_at
    assert row[3] == 0          # join_count 0（存根）
    assert row[4] == "leave"


async def test_kick_no_history_inserts_stub(db):
    """Q3-B: 无历史记录的 kick 插入存根"""
    await db.record_membership(1001, 789012, "kick")
    conn = await db.get_connection()
    row = await _fetch_membership(conn, 1001, 789012)
    assert row is not None
    assert row[0] == "kicked"
    assert row[1] is None       # joined_at NULL（存根）
    assert row[3] == 0          # join_count 0（存根）
    assert row[4] == "kick"


async def test_different_groups_independent(db):
    """同 user 在不同群有独立 membership 行"""
    await db.record_membership(1001, 111, "join")
    await db.record_membership(1001, 222, "join")
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT group_id, status FROM group_memberships "
        "WHERE user_id = 1001 ORDER BY group_id"
    ) as cur:
        rows = await cur.fetchall()
    assert len(rows) == 2
    assert rows[0] == (111, "active")
    assert rows[1] == (222, "active")


async def test_invalid_event_raises(db):
    """未知 event 抛 ValueError"""
    with pytest.raises(ValueError):
        await db.record_membership(1001, 789012, "invalid")
