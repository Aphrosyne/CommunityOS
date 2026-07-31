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


# ── M5: setup() 失败恢复 ────────────────────────────────────────


async def test_setup_failure_clears_connection(tmp_db_path, monkeypatch):
    """M5: setup 失败后 _conn 被清空，不会残留半升级连接

    场景：迁移阶段抛异常，self._conn 已赋值但状态未知。
    修复前：_conn 残留，重试 setup 直接 return，跳过迁移。
    修复后：失败分支调 _safe_close() 清空 _conn，重试安全。
    """
    mgr = DatabaseManager(db_path=tmp_db_path)

    original_run_migrations = mgr._run_migrations

    async def boom(*args, **kwargs):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(mgr, "_run_migrations", boom)

    with pytest.raises(RuntimeError, match="migration failed"):
        await mgr.setup()

    # M5 关键断言：失败后 _conn 必须为 None
    assert mgr._conn is None

    # 重试 setup 可成功（_run_migrations 恢复原实现）
    monkeypatch.setattr(mgr, "_run_migrations", original_run_migrations)
    await mgr.setup()
    conn = await mgr.get_connection()
    async with conn.execute("SELECT 1") as cur:
        row = await cur.fetchone()
    assert row[0] == 1
    await mgr.close()


async def test_setup_failure_during_pragma_clears_connection(tmp_db_path, monkeypatch):
    """M5: PRAGMA 阶段失败也清空 _conn"""
    mgr = DatabaseManager(db_path=tmp_db_path)

    # 让 PRAGMA 执行抛异常
    original_connect = aiosqlite.connect

    async def fake_connect(path):
        conn = await original_connect(path)
        # 第一次 execute（PRAGMA foreign_keys）抛异常
        original_execute = conn.execute

        call_count = {"n": 0}

        async def boom_execute(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("PRAGMA failed")
            return await original_execute(*args, **kwargs)

        conn.execute = boom_execute
        return conn

    monkeypatch.setattr(aiosqlite, "connect", fake_connect)

    with pytest.raises(RuntimeError, match="PRAGMA failed"):
        await mgr.setup()

    assert mgr._conn is None


async def test_safe_close_swallows_close_exception(tmp_db_path):
    """M5: _safe_close 吞咽 close() 异常，仍清空 _conn"""
    mgr = DatabaseManager(db_path=tmp_db_path)
    await mgr.setup()

    # 让 conn.close() 抛异常
    conn = mgr._conn
    original_close = conn.close

    async def boom_close():
        raise RuntimeError("close failed")

    conn.close = boom_close

    # 不应抛出
    await mgr._safe_close()
    assert mgr._conn is None

