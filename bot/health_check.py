"""数据库健康检查脚本

部署后手动核验表结构是否正确。

用法:
    cd bot
    python health_check.py

依据 docs/design/database-roadmap.md Round 1 验证项。
"""
import sqlite3
import sys
from pathlib import Path

from version import BOT_VERSION, PROJECT_NAME

EXPECTED_TABLES = [
    "users",
    "group_memberships",
    "user_permissions",
    "moderation_log",
    "command_log",
    "_migrations",
]

EXPECTED_INDEXES = [
    "idx_memberships_user",
    "idx_memberships_group_status",
    "idx_permissions_user_group",
    "idx_permissions_expires",
    "idx_mod_log_user_time",
    "idx_cmd_log_user_time",
]

DB_PATH = Path(__file__).resolve().parent / "data" / "communityos.db"


def main() -> int:
    print(f"{PROJECT_NAME} v{BOT_VERSION} 数据库健康检查")
    print(f"数据库路径: {DB_PATH}")
    print()

    if not DB_PATH.exists():
        print(f"[FAIL] 数据库文件不存在: {DB_PATH}")
        print("请先启动一次机器人以触发初始化。")
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        # 表检查
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing_tables = [t for t in EXPECTED_TABLES if t not in tables]
        if missing_tables:
            print(f"[FAIL] 缺失表: {missing_tables}")
            return 1
        print(f"[OK] 表检查通过（{len(EXPECTED_TABLES)} 张）")

        # 索引检查
        indexes = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        missing_indexes = [i for i in EXPECTED_INDEXES if i not in indexes]
        if missing_indexes:
            print(f"[FAIL] 缺失索引: {missing_indexes}")
            return 1
        print(f"[OK] 索引检查通过（{len(EXPECTED_INDEXES)} 个）")

        # journal_mode 是数据库级持久化设置
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"[INFO] journal_mode = {journal}")
        if journal.lower() != "wal":
            print("[WARN] journal_mode 非 WAL，请确认 DatabaseManager 是否正常初始化")

        # 已应用迁移
        applied = [
            row[0] for row in conn.execute(
                "SELECT name FROM _migrations ORDER BY name"
            ).fetchall()
        ]
        print(f"[INFO] 已应用迁移: {applied}")

        # 各表行数
        print()
        print("表行数:")
        for table in EXPECTED_TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:24s} {count}")

        print()
        print("[OK] 全部检查通过")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
