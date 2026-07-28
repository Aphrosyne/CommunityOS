"""
数据库服务 - SQLite 连接管理与迁移执行

依据:
    docs/design/database.md v0.1
    docs/architecture.md §数据库
    docs/design/database-roadmap.md Round 1

职责:
    - 管理 aiosqlite 单例连接
    - 启动时执行 PRAGMA 配置（foreign_keys / WAL / busy_timeout）
    - 扫描并应用 bot/migrations/*.sql 迁移脚本（仅 forward）
    - 跟踪已应用迁移于数据库内 _migrations 表

不做:
    - 不提供业务 CRUD（留给 Round 2+ 在本文件内追加 Repository 函数）
    - 不暴露给插件直接调用 connection（插件应通过本文件内的 Repository 函数）
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite

from services.config import DATA_DIR
from services.logger import get_logger

logger = get_logger("database")

# 数据库文件路径
DB_PATH: Path = DATA_DIR / "communityos.db"

# 迁移脚本目录（bot/migrations/）
MIGRATIONS_DIR: Path = Path(__file__).resolve().parent.parent / "migrations"


class DatabaseManager:
    """SQLite 连接与迁移管理器

    生命周期:
        setup()  → 打开连接、配置 PRAGMA、执行迁移
        get_connection() → 取得连接（供 Repository 函数使用）
        close()  → 关闭连接

    单例用法:
        from services import database
        await database.setup()
        await database.close()
    """

    def __init__(self, db_path: Path = DB_PATH,
                 migrations_dir: Path = MIGRATIONS_DIR) -> None:
        self._db_path = db_path
        self._migrations_dir = migrations_dir
        self._conn: aiosqlite.Connection | None = None

    async def setup(self) -> None:
        """初始化数据库：打开连接、配置 PRAGMA、执行迁移

        幂等：重复调用不会重复建表。
        失败策略：fail-fast，异常向上传播（数据库是核心依赖，起不来不如不起）。
        """
        if self._conn is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"正在打开数据库: {self._db_path}")
        self._conn = await aiosqlite.connect(self._db_path)

        # PRAGMA 配置
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA busy_timeout = 5000")
        await self._conn.commit()

        await self._run_migrations()
        logger.info("数据库已就绪")

    async def _run_migrations(self) -> None:
        """执行未应用的迁移脚本"""
        assert self._conn is not None

        # 迁移跟踪表
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "  name TEXT PRIMARY KEY,"
            "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        await self._conn.commit()

        applied = await self._get_applied_migrations()

        if not self._migrations_dir.exists():
            logger.warning(f"迁移目录不存在: {self._migrations_dir}")
            return

        pending = sorted(
            (f for f in self._migrations_dir.glob("*.sql")
             if f.name not in applied),
            key=lambda f: f.name,
        )

        if not pending:
            logger.info(f"无待执行迁移（已应用 {len(applied)} 个）")
            return

        for migration in pending:
            await self._apply_migration(migration)
        logger.info(f"已应用 {len(pending)} 个迁移")

    async def _get_applied_migrations(self) -> set[str]:
        assert self._conn is not None
        async with self._conn.execute("SELECT name FROM _migrations") as cur:
            rows = await cur.fetchall()
        return {row[0] for row in rows}

    async def _apply_migration(self, path: Path) -> None:
        """执行单个迁移脚本并记录到 _migrations

        CREATE TABLE/INDEX IF NOT EXISTS 保证脚本幂等，
        即使 _migrations 记录丢失，重跑也安全。
        """
        assert self._conn is not None
        sql = path.read_text(encoding="utf-8")
        logger.info(f"正在应用迁移: {path.name}")
        try:
            await self._conn.executescript(sql)
            await self._conn.execute(
                "INSERT INTO _migrations (name) VALUES (?)", (path.name,)
            )
            await self._conn.commit()
        except Exception:
            # executescript 失败时连接回到自动提交状态；
            # 因脚本幂等，重跑安全，故仅记录并向上抛出
            await self._conn.rollback()
            logger.error(f"迁移失败: {path.name}", exc_info=True)
            raise

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("数据库连接已关闭")

    async def get_connection(self) -> aiosqlite.Connection:
        """取得当前连接

        仅供 database.py 内的 Repository 函数及测试使用，
        插件不应直接调用。
        """
        if self._conn is None:
            raise RuntimeError("数据库未初始化，请先调用 setup()")
        return self._conn


# 模块级单例
_manager: DatabaseManager = DatabaseManager()


async def setup() -> None:
    """初始化模块级单例数据库连接（启动钩子调用）"""
    await _manager.setup()


async def close() -> None:
    """关闭模块级单例数据库连接（关闭钩子调用）"""
    await _manager.close()


async def get_connection() -> aiosqlite.Connection:
    """取得模块级单例连接（Repository 函数使用）"""
    return await _manager.get_connection()
