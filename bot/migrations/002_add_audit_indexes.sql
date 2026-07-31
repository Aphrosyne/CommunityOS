-- 002_add_audit_indexes.sql
-- 依据: docs/technical-debt.md L8 / X4
--
-- 为 moderation_log.action 和 command_log.command_name 添加索引，
-- 支持按动作类型 / 命令名筛选查询（WebUI 接入前置优化）。
--
-- 幂等：IF NOT EXISTS 保证重跑安全（即使 _migrations 记录丢失）。
-- 已有的 idx_mod_log_user_time / idx_cmd_log_user_time 保持不变，
-- 本迁移只补充按 action / command_name 维度的查询索引。

CREATE INDEX IF NOT EXISTS idx_mod_log_action ON moderation_log (action);
CREATE INDEX IF NOT EXISTS idx_cmd_log_command_name ON command_log (command_name);
