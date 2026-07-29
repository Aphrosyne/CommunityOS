"""command_log 写入测试

依据:
    docs/design/database.md §3.2 command_log 表
    docs/design/database-roadmap.md Round 5
    Q1-A (无 FK) / Q5-A (raw_text 截断 200) / Q6-B (私聊 group_id=0)
"""
import pytest

from services.database import DatabaseManager


@pytest.mark.asyncio
async def test_write_command_success(db: DatabaseManager):
    """写入一条 success 指令记录，字段完整"""
    await db.log_command(
        user_id=123456,
        group_id=789,
        command_name="status",
        raw_text="状态",
        result="success",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT user_id, group_id, command_name, raw_text, result, timestamp "
        "FROM command_log WHERE user_id = ?",
        (123456,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == 123456
    assert row[1] == 789
    assert row[2] == "status"
    assert row[3] == "状态"
    assert row[4] == "success"
    assert row[5] is not None  # timestamp


@pytest.mark.asyncio
async def test_write_command_error(db: DatabaseManager):
    """写入 error 结果的指令记录"""
    await db.log_command(
        user_id=111,
        group_id=222,
        command_name="help",
        raw_text="help image",
        result="error",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT result FROM command_log WHERE user_id = ?",
        (111,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == "error"


@pytest.mark.asyncio
async def test_write_nonexistent_user_id(db: DatabaseManager):
    """Q1-A: 未注册用户 user_id 也能成功写入（无 FK 约束）"""
    # 不调用 upsert_user，直接写 command_log
    await db.log_command(
        user_id=999999,  # 不在 users 表
        group_id=888,
        command_name="status",
        raw_text="状态",
        result="success",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM command_log WHERE user_id = ?",
        (999999,),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 1  # 成功写入


@pytest.mark.asyncio
async def test_private_chat_group_id_zero(db: DatabaseManager):
    """Q6-B: 私聊 group_id=0"""
    await db.log_command(
        user_id=333,
        group_id=0,  # 私聊
        command_name="help",
        raw_text="help",
        result="success",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT group_id FROM command_log WHERE user_id = ?",
        (333,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == 0  # 私聊用 0，不是 NULL


@pytest.mark.asyncio
async def test_raw_text_truncation_200(db: DatabaseManager):
    """Q5-A: raw_text 超过 200 字符时截断至 200"""
    long_text = "x" * 300  # 300 字符
    await db.log_command(
        user_id=444,
        group_id=555,
        command_name="publish",
        raw_text=long_text,
        result="success",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT raw_text FROM command_log WHERE user_id = ?",
        (444,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert len(row[0]) == 200  # 截断至 200
    assert row[0] == "x" * 200


@pytest.mark.asyncio
async def test_raw_text_exact_200_not_truncated(db: DatabaseManager):
    """Q5-A: raw_text 恰好 200 字符不截断"""
    text_200 = "y" * 200
    await db.log_command(
        user_id=666,
        group_id=777,
        command_name="status",
        raw_text=text_200,
        result="success",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT raw_text FROM command_log WHERE user_id = ?",
        (666,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert len(row[0]) == 200


@pytest.mark.asyncio
async def test_raw_text_none_writes_null(db: DatabaseManager):
    """raw_text=None 写入 NULL"""
    await db.log_command(
        user_id=777,
        group_id=888,
        command_name="status",
        raw_text=None,
        result="success",
    )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT raw_text FROM command_log WHERE user_id = ?",
        (777,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] is None  # NULL


@pytest.mark.asyncio
async def test_default_result_is_success(db: DatabaseManager):
    """result 参数默认值为 success"""
    await db.log_command(
        user_id=1000,
        group_id=2000,
        command_name="help",
        raw_text="help",
    )  # 不传 result

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT result FROM command_log WHERE user_id = ?",
        (1000,),
    ) as cur:
        row = await cur.fetchone()

    assert row is not None
    assert row[0] == "success"


@pytest.mark.asyncio
async def test_write_multiple_records_ordering(db: DatabaseManager):
    """多条记录按时间倒序查询（timestamp 字典序 = 时间序）"""
    for i in range(5):
        await db.log_command(
            user_id=2000,
            group_id=3000,
            command_name=f"cmd_{i}",
            raw_text=f"cmd_{i}",
            result="success",
        )

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT command_name FROM command_log WHERE user_id = ? ORDER BY timestamp DESC",
        (2000,),
    ) as cur:
        rows = await cur.fetchall()

    assert len(rows) == 5
    # 最后写入的 cmd_4 应在首位
    assert rows[0][0] == "cmd_4"


@pytest.mark.asyncio
async def test_query_by_command_name(db: DatabaseManager):
    """按 command_name 查询"""
    await db.log_command(1100, 1200, "status", "状态", "success")
    await db.log_command(1100, 1200, "help", "help", "success")
    await db.log_command(1300, 1200, "status", "状态", "success")  # 不同 user

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM command_log WHERE command_name = ?",
        ("status",),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 2  # 两条 status 记录


@pytest.mark.asyncio
async def test_query_by_result(db: DatabaseManager):
    """按 result 查询（success/error）"""
    await db.log_command(1400, 1500, "cmd1", "cmd1", "success")
    await db.log_command(1400, 1500, "cmd2", "cmd2", "error")
    await db.log_command(1400, 1500, "cmd3", "cmd3", "success")

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM command_log WHERE result = ?",
        ("success",),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 2  # 两条 success


@pytest.mark.asyncio
async def test_query_by_group_id(db: DatabaseManager):
    """按 group_id 查询"""
    await db.log_command(1600, 1700, "cmd", "cmd", "success")
    await db.log_command(1600, 1800, "cmd", "cmd", "success")  # 不同 group
    await db.log_command(1600, 0, "cmd", "cmd", "success")  # 私聊

    conn = await db.get_connection()
    async with conn.execute(
        "SELECT COUNT(*) FROM command_log WHERE group_id = ?",
        (1700,),
    ) as cur:
        row = await cur.fetchone()

    assert row[0] == 1
