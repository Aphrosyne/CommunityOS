"""moderation_log 写入测试

依据:
    docs/design/database.md §3.2 moderation_log 表
    docs/design/database-roadmap.md Round 4
    Q1-A (无 FK) / Q2-A (action 值域) / Q5-A (JSON details)
"""
import json

import pytest

from services.database import DatabaseManager


@pytest.mark.asyncio
async def test_write_mute_success(db: DatabaseManager):
    """写入一条 mute 成功记录，字段完整"""
    await db.log_moderation(
        action="mute",
        user_id=123456,
        operator_id=789,
        group_id=100,
        reason="mute",
        details={"duration": 60, "type": "normal", "result": "success"},
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT action, user_id, operator_id, group_id, reason, details, timestamp "
        "FROM moderation_log WHERE user_id = ?",
        (123456,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == "mute"
    assert row[1] == 123456
    assert row[2] == 789
    assert row[3] == 100
    assert row[4] == "mute"
    details = json.loads(row[5])
    assert details["duration"] == 60
    assert details["type"] == "normal"
    assert details["result"] == "success"
    assert row[6] is not None  # timestamp 非空


@pytest.mark.asyncio
async def test_write_auto_recall_system_operator(db: DatabaseManager):
    """auto_recall 记录，operator_id=0 表示系统操作"""
    await db.log_moderation(
        action="auto_recall",
        user_id=111,
        operator_id=0,
        group_id=200,
        reason="keyword_hit",
        details={"keywords": ["spam"], "message_id": 999, "result": "success"},
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT operator_id, details FROM moderation_log WHERE action = ?",
        ("auto_recall",),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == 0  # 系统操作
    details = json.loads(row[1])
    assert details["keywords"] == ["spam"]
    assert details["message_id"] == 999


@pytest.mark.asyncio
async def test_write_permission_set_global(db: DatabaseManager):
    """permission_set 记录，group_id=0 全局权限"""
    await db.log_moderation(
        action="permission_set",
        user_id=222,
        operator_id=333,
        group_id=0,
        reason="BotAdmin by 333",
        details={"level": 3, "label": "BotAdmin", "result": "success"},
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT group_id, details FROM moderation_log WHERE action = ?",
        ("permission_set",),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == 0  # 全局
    details = json.loads(row[1])
    assert details["level"] == 3
    assert details["label"] == "BotAdmin"


@pytest.mark.asyncio
async def test_details_none_writes_null(db: DatabaseManager):
    """details=None 时写入 NULL"""
    await db.log_moderation(
        action="mute",
        user_id=444,
        operator_id=555,
        group_id=300,
        reason="mute",
        details=None,
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT details FROM moderation_log WHERE user_id = ?",
        (444,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] is None  # NULL


@pytest.mark.asyncio
async def test_details_json_serialization_roundtrip(db: DatabaseManager):
    """details JSON 序列化可正确反序列化"""
    original = {
        "duration": 120,
        "type": "normal",
        "keywords": ["a", "b", "c"],
        "nested": {"foo": "bar"},
        "message_id": 12345,
    }
    await db.log_moderation(
        action="auto_recall",
        user_id=666,
        operator_id=0,
        group_id=400,
        reason="keyword_hit",
        details=original,
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT details FROM moderation_log WHERE user_id = ?",
        (666,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    restored = json.loads(row[0])
    assert restored == original


@pytest.mark.asyncio
async def test_write_nonexistent_user_id(db: DatabaseManager):
    """Q1-A: user_id 不在 users 表也能成功写入（无 FK 约束）"""
    # 不调用 upsert_user，直接写 moderation_log
    await db.log_moderation(
        action="mute",
        user_id=999999,  # 不在 users 表
        operator_id=888888,  # 也不在 users 表
        group_id=500,
        reason="mute",
        details={"result": "success"},
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM moderation_log WHERE user_id = ? AND operator_id = ?",
        (999999, 888888),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 1  # 成功写入


@pytest.mark.asyncio
async def test_write_multiple_records_ordering(db: DatabaseManager):
    """多条记录按时间倒序查询（timestamp 字典序 = 时间序）"""
    for i in range(5):
        await db.log_moderation(
            action="mute",
            user_id=777,
            operator_id=888,
            group_id=600,
            reason=f"mute_{i}",
            details={"index": i},
        )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT reason FROM moderation_log WHERE user_id = ? ORDER BY timestamp DESC",
        (777,),
    ) as cur:
        rows = await cur.fetchall()

    assert len(rows) == 5
    # 最后写入的 reason=mute_4 应在首位
    assert rows[0][0] == "mute_4"


@pytest.mark.asyncio
async def test_all_action_types(db: DatabaseManager):
    """Q2-A: 所有 action 值域都能正确写入"""
    actions = [
        "mute",
        "unmute",
        "mute_denied",
        "auto_recall",
        "permission_set",
        "permission_denied",
    ]
    for i, action in enumerate(actions):
        await db.log_moderation(
            action=action,
            user_id=1000 + i,
            operator_id=2000,
            group_id=700,
            reason=f"test_{action}",
            details={"index": i},
        )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT action FROM moderation_log WHERE group_id = ? ORDER BY id",
        (700,),
    ) as cur:
        rows = await cur.fetchall()

    assert len(rows) == 6
    for i, (action,) in enumerate(rows):
        assert action == actions[i]


@pytest.mark.asyncio
async def test_query_by_user_id(db: DatabaseManager):
    """按 user_id 查询审核历史"""
    await db.log_moderation(
        "mute", 1100, 1200, 800, "mute", {"result": "success"}
    )
    await db.log_moderation(
        "unmute", 1100, 1200, 800, "unmute", {"result": "success"}
    )
    await db.log_moderation(
        "mute", 1300, 1200, 800, "mute", {"result": "success"}
    )  # 不同 user

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT action FROM moderation_log WHERE user_id = ?",
        (1100,),
    ) as cur:
        rows = await cur.fetchall()

    assert len(rows) == 2
    assert {rows[0][0], rows[1][0]} == {"mute", "unmute"}


@pytest.mark.asyncio
async def test_query_by_group_id(db: DatabaseManager):
    """按 group_id 查询"""
    await db.log_moderation(
        "mute", 1400, 1500, 900, "mute", {"result": "success"}
    )
    await db.log_moderation(
        "mute", 1600, 1500, 1000, "mute", {"result": "success"}
    )  # 不同 group

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM moderation_log WHERE group_id = ?",
        (900,),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 1


@pytest.mark.asyncio
async def test_query_by_action_type(db: DatabaseManager):
    """按 action 类型查询"""
    await db.log_moderation(
        "mute", 1700, 1800, 1100, "mute", {"result": "success"}
    )
    await db.log_moderation(
        "auto_recall", 1900, 0, 1100, "keyword_hit", {"result": "success"}
    )
    await db.log_moderation(
        "mute", 2000, 1800, 1100, "mute", {"result": "success"}
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM moderation_log WHERE action = ?",
        ("mute",),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 2
