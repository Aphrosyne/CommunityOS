"""
数据库服务 - SQLite 连接管理与迁移执行

依据:
    docs/design/database.md v0.1
    docs/architecture.md §数据库
    docs/design/database-roadmap.md Round 1 / Round 2

职责:
    - 管理 aiosqlite 单例连接
    - 启动时执行 PRAGMA 配置（foreign_keys / WAL / busy_timeout）
    - 扫描并应用 bot/migrations/*.sql 迁移脚本（仅 forward）
    - 跟踪已应用迁移于数据库内 _migrations 表
    - 提供 Repository 函数供插件调用（Round 2+: upsert_user / record_membership）

不做:
    - 不暴露给插件直接调用 connection（插件应通过本文件内的 Repository 函数）

失败策略（Q6，区分启动与运行时）:
    - 启动迁移失败 → 抛异常，禁止机器人启动
      （半升级状态比不升级更危险，尤其权限表结构不一致）
    - 运行时 Repository 写失败 → 抛异常给调用方，调用方（插件）应捕获并继续运行
      （DB 是查询层，单次写失败不应中断事件处理）
"""
from __future__ import annotations

import json
from datetime import datetime
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

    # ── Repository 函数（Round 2+） ──────────────────────────

    async def upsert_user(self, user_id: int) -> None:
        """插入或更新用户记录

        首次出现：插入 first_seen + last_updated
        已存在：仅更新 last_updated，first_seen 不变

        运行时失败：抛异常给调用方，调用方应捕获（见文件头 Q6 策略）。
        """
        assert self._conn is not None
        now = _now_iso()
        await self._conn.execute(
            "INSERT INTO users (user_id, first_seen, last_updated) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_updated = excluded.last_updated",
            (user_id, now, now),
        )
        await self._conn.commit()

    async def record_membership(
        self, user_id: int, group_id: int, event: str
    ) -> None:
        """记录群成员关系变更

        event:
            "join"  → status=active, join_count+1, left_at=NULL
            "leave" → status=left,    left_at=now
            "kick"  → status=kicked,  left_at=now

        自动调用 upsert_user 保证 FK 约束。
        leave/kick 对无历史记录的用户：插入存根记录（Q3-B，join_count=0）。

        运行时失败：抛异常给调用方，调用方应捕获（见文件头 Q6 策略）。
        """
        assert self._conn is not None
        await self.upsert_user(user_id)  # 保证 FK
        now = _now_iso()

        if event == "join":
            await self._conn.execute(
                "INSERT INTO group_memberships "
                "(user_id, group_id, status, joined_at, left_at, "
                " join_count, last_event) "
                "VALUES (?, ?, 'active', ?, NULL, 1, 'join') "
                "ON CONFLICT(user_id, group_id) DO UPDATE SET "
                "  status = 'active', "
                "  joined_at = excluded.joined_at, "
                "  left_at = NULL, "
                "  join_count = join_count + 1, "
                "  last_event = 'join'",
                (user_id, group_id, now),
            )
        elif event in ("leave", "kick"):
            status = "left" if event == "leave" else "kicked"
            cur = await self._conn.execute(
                "UPDATE group_memberships "
                "SET status = ?, left_at = ?, last_event = ? "
                "WHERE user_id = ? AND group_id = ?",
                (status, now, event, user_id, group_id),
            )
            if cur.rowcount == 0:
                # Q3-B: 无历史记录，插入存根（joined_at=NULL, join_count=0）
                await self._conn.execute(
                    "INSERT INTO group_memberships "
                    "(user_id, group_id, status, joined_at, left_at, "
                    " join_count, last_event) "
                    "VALUES (?, ?, ?, NULL, ?, 0, ?)",
                    (user_id, group_id, status, now, event),
                )
        else:
            raise ValueError(f"未知 event: {event!r}（应为 join/leave/kick）")

        await self._conn.commit()

    async def set_permission(
        self,
        user_id: int,
        group_id: int,
        level: int,
        granted_by: int | None = None,
        expires_at: str | None = None,
        reason: str | None = None,
    ) -> None:
        """设置用户权限等级（UPSERT 语义，Q11 单等级覆盖）

        高级覆盖低级：先删除该用户在该 group_id 的所有权限记录，
        再插入新 level（level=0 时不插入，等价于无记录）。

        group_id=0 表示全局生效（Q11-C）。
        level 值域: -1(黑名单) ~ 9(Owner)，见 database.md §3.1。

        运行时失败：抛异常给调用方（见文件头 Q6 策略）。
        """
        assert self._conn is not None
        await self.upsert_user(user_id)  # 保证 FK (user_id)
        if granted_by is not None:
            await self.upsert_user(granted_by)  # 保证 FK (granted_by)
        now = _now_iso()

        # 删除旧权限记录（覆盖语义）
        await self._conn.execute(
            "DELETE FROM user_permissions "
            "WHERE user_id = ? AND group_id = ?",
            (user_id, group_id),
        )

        # level=0 等于无记录，不插入
        if level != 0:
            await self._conn.execute(
                "INSERT INTO user_permissions "
                "(user_id, group_id, level, granted_by, granted_at, "
                " expires_at, reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, group_id, level, granted_by, now, expires_at, reason),
            )

        await self._conn.commit()

    async def get_permission(
        self, user_id: int, group_id: int
    ) -> int:
        """获取用户在某群的有效权限等级

        查询全局(group_id=0) + 群级(group_id=?) 的最高 level。
        过期权限自动失效（expires_at < now 则忽略）。
        无记录返回 0（普通用户）。

        Q6-A: 过期比较用 Python 端 now_iso，避免 SQLite datetime('now')
        与 ISO 8601 含时区格式的兼容问题。
        """
        assert self._conn is not None
        now = _now_iso()
        async with self._conn.execute(
            "SELECT MAX(level) FROM user_permissions "
            "WHERE user_id = ? AND group_id IN (0, ?) "
            "  AND (expires_at IS NULL OR expires_at > ?)",
            (user_id, group_id, now),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row[0] is not None else 0

    async def get_user_permissions(self, user_id: int) -> list[dict]:
        """查询用户所有权限记录（全局 + 各群）

        返回未过期的记录列表，按 group_id 升序。
        每条记录包含 group_id/level/granted_by/granted_at/expires_at/reason。
        用于 /perm @user 指令展示用户权限全貌。
        """
        assert self._conn is not None
        now = _now_iso()
        async with self._conn.execute(
            "SELECT group_id, level, granted_by, granted_at, expires_at, reason "
            "FROM user_permissions "
            "WHERE user_id = ? AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY group_id",
            (user_id, now),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "group_id": r[0],
                "level": r[1],
                "granted_by": r[2],
                "granted_at": r[3],
                "expires_at": r[4],
                "reason": r[5],
            }
            for r in rows
        ]

    async def clear_user_permissions(self, user_id: int) -> int:
        """清除用户所有权限记录（全局 + 各群）

        返回删除的记录数。
        注意：调用方应先做 Owner 保护检查，不可清除 Owner 的权限。
        """
        assert self._conn is not None
        cur = await self._conn.execute(
            "DELETE FROM user_permissions WHERE user_id = ?",
            (user_id,),
        )
        await self._conn.commit()
        return cur.rowcount

    async def log_moderation(
        self,
        action: str,
        user_id: int,
        operator_id: int,
        group_id: int,
        reason: str | None = None,
        details: dict | None = None,
    ) -> None:
        """写入审核日志记录

        审计日志优先级高于数据完整性约束：
            - 不做 FK 约束（user_id/operator_id 可能为不存在用户或 0=系统操作）
            - 不 upsert 用户，保证日志写入尽可能成功（Q1-A）

        action 值域（Q2-A，与文本日志一致）:
            mute / unmute / mute_denied / auto_recall /
            permission_set / permission_denied

        details: dict → JSON 字符串（Q5-A），None → NULL

        运行时失败：抛异常给调用方（见文件头 Q6 策略）。
        """
        assert self._conn is not None
        details_json = (
            json.dumps(details, ensure_ascii=False, default=str)
            if details is not None
            else None
        )
        await self._conn.execute(
            "INSERT INTO moderation_log "
            "(action, user_id, operator_id, group_id, reason, details, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                action,
                user_id,
                operator_id,
                group_id,
                reason,
                details_json,
                _now_iso(),
            ),
        )
        await self._conn.commit()

    async def log_command(
        self,
        user_id: int,
        group_id: int,
        command_name: str,
        raw_text: str | None = None,
        result: str = "success",
    ) -> None:
        """写入指令调用日志

        审计日志优先级高于数据完整性约束：
            - 不做 FK 约束（未注册用户可执行指令，Q1-A）
            - 不 upsert 用户，保证日志写入尽可能成功

        group_id: 0 表示私聊（Q6-B，与 dispatcher 现有逻辑一致）
        raw_text: Python 端截断至 200 字符（Q5-A），None → NULL
        result: success / error（其他状态如 permission_denied/cooldown_blocked
            本轮不记录，见 Q2-A/Q3-A/Q4-A）

        运行时失败：抛异常给调用方（见文件头 Q6 策略），
            调用方（command_dispatcher）应捕获并继续运行。
        """
        assert self._conn is not None
        truncated = raw_text[:200] if raw_text is not None else None
        await self._conn.execute(
            "INSERT INTO command_log "
            "(user_id, group_id, command_name, raw_text, result, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, group_id, command_name, truncated, result, _now_iso()),
        )
        await self._conn.commit()


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


async def upsert_user(user_id: int) -> None:
    """插入或更新用户记录（委托给单例）"""
    await _manager.upsert_user(user_id)


async def record_membership(
    user_id: int, group_id: int, event: str
) -> None:
    """记录群成员关系变更（委托给单例）"""
    await _manager.record_membership(user_id, group_id, event)


async def set_permission(
    user_id: int,
    group_id: int,
    level: int,
    granted_by: int | None = None,
    expires_at: str | None = None,
    reason: str | None = None,
) -> None:
    """设置用户权限等级（委托给单例）"""
    await _manager.set_permission(
        user_id, group_id, level, granted_by, expires_at, reason
    )


async def get_permission(user_id: int, group_id: int) -> int:
    """获取用户在某群的有效权限等级（委托给单例）"""
    return await _manager.get_permission(user_id, group_id)


async def get_user_permissions(user_id: int) -> list[dict]:
    """查询用户所有权限记录（委托给单例）"""
    return await _manager.get_user_permissions(user_id)


async def clear_user_permissions(user_id: int) -> int:
    """清除用户所有权限记录（委托给单例）"""
    return await _manager.clear_user_permissions(user_id)


async def log_moderation(
    action: str,
    user_id: int,
    operator_id: int,
    group_id: int,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    """写入审核日志记录（委托给单例）"""
    await _manager.log_moderation(
        action, user_id, operator_id, group_id, reason, details
    )


async def log_command(
    user_id: int,
    group_id: int,
    command_name: str,
    raw_text: str | None = None,
    result: str = "success",
) -> None:
    """写入指令调用日志（委托给单例）"""
    await _manager.log_command(
        user_id, group_id, command_name, raw_text, result
    )


def _now_iso() -> str:
    """当前时间的 ISO 8601 字符串（含本地时区偏移，Q1-C）

    示例: 2026-07-28T15:30:00+08:00
    """
    return datetime.now().astimezone().isoformat()
