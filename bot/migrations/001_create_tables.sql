-- CommunityOS 初始迁移
-- 依据: docs/design/database.md v0.1
-- 创建 5 张核心表 + 索引
-- 注: user_permissions.group_id = 0 表示全局生效（不使用 NULL，见 Q11-C）

-- users — 用户
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    first_seen  TEXT,
    last_updated TEXT
);

-- group_memberships — 群成员关系
CREATE TABLE IF NOT EXISTS group_memberships (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    group_id   INTEGER NOT NULL,
    status     TEXT    NOT NULL,
    joined_at  TEXT,
    left_at    TEXT,
    join_count INTEGER DEFAULT 1,
    last_event TEXT,
    UNIQUE (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- user_permissions — 权限
-- group_id = 0 表示全局生效
CREATE TABLE IF NOT EXISTS user_permissions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    group_id   INTEGER NOT NULL DEFAULT 0,
    level      INTEGER NOT NULL,
    granted_by INTEGER,
    granted_at TEXT,
    expires_at TEXT,
    reason     TEXT,
    UNIQUE (user_id, group_id, level),
    FOREIGN KEY (user_id)      REFERENCES users (user_id),
    FOREIGN KEY (granted_by)   REFERENCES users (user_id)
);

-- moderation_log — 审核记录
-- Q1-A: 不添加 FK 约束。审计日志优先级高于数据完整性约束：
--   - 被操作用户可能不存在于 users 表
--   - operator_id 可能为系统操作（0），无法满足 FK
--   - 日志写入尽可能成功，不因用户不存在而失败
CREATE TABLE IF NOT EXISTS moderation_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    operator_id INTEGER,
    group_id    INTEGER,
    action      TEXT NOT NULL,
    reason      TEXT,
    timestamp   TEXT NOT NULL,
    details     TEXT
);

-- command_log — 指令记录（查询层，文本日志保留）
-- Q1-A: 不添加 FK 约束。审计日志优先级高于数据完整性约束：
--   - 未注册用户可以执行指令
--   - 日志写入不应依赖 users 表存在
CREATE TABLE IF NOT EXISTS command_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    group_id     INTEGER,
    command_name TEXT NOT NULL,
    raw_text     TEXT,
    result       TEXT,
    timestamp    TEXT NOT NULL
);

-- 索引（按实际查询场景建立）
CREATE INDEX IF NOT EXISTS idx_memberships_user        ON group_memberships (user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_group_status ON group_memberships (group_id, status);
CREATE INDEX IF NOT EXISTS idx_permissions_user_group   ON user_permissions (user_id, group_id);
CREATE INDEX IF NOT EXISTS idx_permissions_expires      ON user_permissions (expires_at);
CREATE INDEX IF NOT EXISTS idx_mod_log_user_time       ON moderation_log (user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_cmd_log_user_time       ON command_log (user_id, timestamp);
