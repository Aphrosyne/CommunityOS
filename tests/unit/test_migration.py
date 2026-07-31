"""迁移脚本测试

验证 001_create_tables.sql 建表结果与 docs/design/database.md §3.2 一致。
验证 002_add_audit_indexes.sql 索引创建（L8）。
"""
EXPECTED_TABLES = {
    "users",
    "group_memberships",
    "user_permissions",
    "moderation_log",
    "command_log",
    "_migrations",
}

EXPECTED_INDEXES = {
    "idx_memberships_user",
    "idx_memberships_group_status",
    "idx_permissions_user_group",
    "idx_permissions_expires",
    "idx_mod_log_user_time",
    "idx_cmd_log_user_time",
    # 002_add_audit_indexes.sql（L8）
    "idx_mod_log_action",
    "idx_cmd_log_command_name",
}


async def _fetch_tables(conn):
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cur:
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def _fetch_columns(conn, table):
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        rows = await cur.fetchall()
    return {row[1] for row in rows}


async def _fetch_indexes(conn):
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name NOT LIKE 'sqlite_%'"
    ) as cur:
        rows = await cur.fetchall()
    return {row[0] for row in rows}


async def test_all_tables_exist(db):
    """5 张业务表 + _migrations 均存在"""
    conn = await db.get_connection()
    tables = await _fetch_tables(conn)
    assert EXPECTED_TABLES.issubset(tables)


async def test_users_columns(db):
    conn = await db.get_connection()
    assert await _fetch_columns(conn, "users") == {
        "user_id", "first_seen", "last_updated"
    }


async def test_group_memberships_columns(db):
    conn = await db.get_connection()
    assert await _fetch_columns(conn, "group_memberships") == {
        "id", "user_id", "group_id", "status",
        "joined_at", "left_at", "join_count", "last_event",
    }


async def test_user_permissions_columns(db):
    conn = await db.get_connection()
    assert await _fetch_columns(conn, "user_permissions") == {
        "id", "user_id", "group_id", "level",
        "granted_by", "granted_at", "expires_at", "reason",
    }


async def test_moderation_log_columns(db):
    conn = await db.get_connection()
    assert await _fetch_columns(conn, "moderation_log") == {
        "id", "user_id", "operator_id", "group_id",
        "action", "reason", "timestamp", "details",
    }


async def test_command_log_columns(db):
    conn = await db.get_connection()
    assert await _fetch_columns(conn, "command_log") == {
        "id", "user_id", "group_id", "command_name",
        "raw_text", "result", "timestamp",
    }


async def test_indexes_exist(db):
    """核心索引按实际查询场景建立"""
    conn = await db.get_connection()
    indexes = await _fetch_indexes(conn)
    assert EXPECTED_INDEXES.issubset(indexes)


async def test_user_permissions_group_id_default_zero(db):
    """Q11-C: group_id NOT NULL DEFAULT 0（0 表示全局生效）"""
    conn = await db.get_connection()
    await conn.execute("INSERT INTO users (user_id) VALUES (1001)")
    await conn.execute(
        "INSERT INTO user_permissions (user_id, level) VALUES (1001, 9)"
    )
    await conn.commit()
    async with conn.execute(
        "SELECT group_id FROM user_permissions WHERE user_id = 1001"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 0


async def test_migration_recorded(db):
    """_migrations 表记录了 001_create_tables.sql 与 002_add_audit_indexes.sql"""
    conn = await db.get_connection()
    async with conn.execute("SELECT name FROM _migrations") as cur:
        rows = await cur.fetchall()
    names = {row[0] for row in rows}
    assert "001_create_tables.sql" in names
    assert "002_add_audit_indexes.sql" in names


async def test_setup_idempotent_across_managers(tmp_db_path):
    """同一数据库文件被两个 manager 依次 setup，迁移不重复记录"""
    from services.database import DatabaseManager

    mgr1 = DatabaseManager(db_path=tmp_db_path)
    await mgr1.setup()
    await mgr1.close()

    mgr2 = DatabaseManager(db_path=tmp_db_path)
    await mgr2.setup()
    conn = await mgr2.get_connection()
    async with conn.execute("SELECT COUNT(*) FROM _migrations") as cur:
        row = await cur.fetchone()
    assert row[0] == 2  # 001 + 002
    await mgr2.close()
