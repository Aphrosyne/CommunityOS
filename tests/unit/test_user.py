"""upsert_user 测试

依据 docs/developer/testing.md — 单元测试，不依赖 NoneBot2。
"""
import time


async def _fetch_user(conn, user_id):
    async with conn.execute(
        "SELECT user_id, first_seen, last_updated FROM users "
        "WHERE user_id = ?", (user_id,)
    ) as cur:
        return await cur.fetchone()


async def test_new_user_inserted(db):
    """新用户：插入一条记录，first_seen == last_updated"""
    await db.upsert_user(1001)
    conn = await db.get_connection()
    row = await _fetch_user(conn, 1001)
    assert row is not None
    assert row[0] == 1001
    assert row[1] is not None  # first_seen
    assert row[2] is not None  # last_updated
    assert row[1] == row[2]    # 首次两者相同


async def test_duplicate_user_not_re_inserted(db):
    """重复 upsert 不新增行"""
    await db.upsert_user(1001)
    await db.upsert_user(1001)
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM users WHERE user_id = 1001"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_duplicate_user_first_seen_unchanged(db):
    """重复 upsert 后 first_seen 不变，last_updated 更新"""
    await db.upsert_user(1001)
    conn = await db.get_connection()
    _, first_seen_1, _ = await _fetch_user(conn, 1001)

    time.sleep(0.01)  # 确保 last_updated 时间戳不同
    await db.upsert_user(1001)
    _, first_seen_2, last_updated_2 = await _fetch_user(conn, 1001)

    assert first_seen_2 == first_seen_1      # first_seen 不变
    assert last_updated_2 != first_seen_1    # last_updated 已更新


async def test_multiple_users_independent(db):
    """多个用户互不干扰"""
    await db.upsert_user(1001)
    await db.upsert_user(1002)
    await db.upsert_user(1003)
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT user_id FROM users ORDER BY user_id"
    ) as cur:
        rows = await cur.fetchall()
    assert [r[0] for r in rows] == [1001, 1002, 1003]
