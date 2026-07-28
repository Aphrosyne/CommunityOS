"""数据库服务测试

验证 DatabaseManager 生命周期与 PRAGMA 配置。
"""
import aiosqlite
import pytest

from services.database import DatabaseManager


async def test_get_connection_after_setup(db):
    """setup 后 get_connection 返回可用连接"""
    conn = await db.get_connection()
    assert isinstance(conn, aiosqlite.Connection)
    async with conn.execute("SELECT 1") as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_basic_read_write(db):
    """基本读写：建表、插入、查询"""
    conn = await db.get_connection()
    await conn.execute("CREATE TABLE t (x INTEGER)")
    await conn.execute("INSERT INTO t VALUES (42)")
    await conn.commit()
    async with conn.execute("SELECT x FROM t") as cur:
        row = await cur.fetchone()
    assert row[0] == 42


async def test_pragma_foreign_keys_on(db):
    """Q9: foreign_keys = ON"""
    conn = await db.get_connection()
    async with conn.execute("PRAGMA foreign_keys") as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_pragma_journal_mode_wal(db):
    """Q8: journal_mode = WAL"""
    conn = await db.get_connection()
    async with conn.execute("PRAGMA journal_mode") as cur:
        row = await cur.fetchone()
    assert row[0].lower() == "wal"


async def test_pragma_busy_timeout(db):
    """busy_timeout 已设置"""
    conn = await db.get_connection()
    async with conn.execute("PRAGMA busy_timeout") as cur:
        row = await cur.fetchone()
    assert row[0] == 5000


async def test_get_connection_before_setup_raises(tmp_db_path):
    """未初始化时 get_connection 抛 RuntimeError"""
    mgr = DatabaseManager(db_path=tmp_db_path)
    with pytest.raises(RuntimeError):
        await mgr.get_connection()


async def test_close_releases_connection(tmp_db_path):
    """close 后连接已关闭，再操作抛异常"""
    mgr = DatabaseManager(db_path=tmp_db_path)
    await mgr.setup()
    conn = await mgr.get_connection()
    await mgr.close()
    with pytest.raises(Exception):
        await conn.execute("SELECT 1")


async def test_setup_idempotent_same_manager(db):
    """同一 manager 重复 setup 不报错（_conn 已存在直接 return）"""
    await db.setup()
    conn = await db.get_connection()
    async with conn.execute("SELECT 1") as cur:
        row = await cur.fetchone()
    assert row[0] == 1


async def test_foreign_key_enforced(db):
    """外键约束生效：插入不存在的 user_id 应失败"""
    conn = await db.get_connection()
    with pytest.raises(aiosqlite.IntegrityError):
        await conn.execute(
            "INSERT INTO group_memberships (user_id, group_id, status) "
            "VALUES (999999, 123, 'active')"
        )
        await conn.commit()
