"""Audit Service — 审计日志统一封装（TD1 / TD2 修复）

抽取自 mute.py / auto_recall.py / admin.py / command_dispatcher.py 中重复的
_log_mod / _log_cmd helper，统一封装 moderation_log / command_log 的写入逻辑。

依据:
    docs/architecture.md §公共服务
    docs/design/database.md §3.2 (moderation_log / command_log)
    docs/technical-debt.md TD1 / TD2

设计:
    - 所有写入失败仅记日志不抛出（Q4-A / Q1-A），不影响 bot 运行
    - 不做参数校验（DB 层已校验），只做 try/except 模板封装
    - 通过 services.database 模块级 API 写入，保持分层架构
"""
from __future__ import annotations

from services import database
from services.logger import get_logger

# audit 日志使用独立的 logger 域，便于按域筛选
_logger = get_logger("command")
_mod_logger = get_logger("moderation")


async def log_moderation(
    action: str,
    user_id: int,
    operator_id: int,
    group_id: int,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    """写入 moderation_log 审计日志

    失败仅记日志不抛出（Q4-A）。
    供 mute / auto_recall / admin / dispatcher 等插件统一调用。

    Args:
        action: 动作类型（如 mute / unmute / mute_denied / permission_set /
                permission_denied / auto_recall 等，见 database.md §3.2）
        user_id: 被操作用户 QQ
        operator_id: 操作者 QQ（系统操作使用 0）
        group_id: 群号（私聊/全局使用 0）
        reason: 原因简述
        details: 附加详情（JSON 序列化存储）
    """
    try:
        await database.log_moderation(
            action=action,
            user_id=user_id,
            operator_id=operator_id,
            group_id=group_id,
            reason=reason,
            details=details,
        )
    except Exception:
        _mod_logger.exception(
            f"DB 写入失败: moderation_log action={action}"
        )


async def log_command(
    user_id: int,
    group_id: int,
    command_name: str,
    raw_text: str | None = None,
    result: str = "success",
) -> None:
    """写入 command_log 审计日志

    失败仅记日志不抛出（Q1-A 额外要求）。
    供 command_dispatcher 统一调用。

    默认值与 database.log_command 保持一致（薄封装透传）。

    Args:
        user_id: 执行者 QQ
        group_id: 群号（私聊使用 0，见 database.md §3.2）
        command_name: 最终命令名（shortcut 命中时记录展开后的命令名，Q8-A）
        raw_text: 原始消息文本（截断至 200 字符，由 DB 层处理），默认 None
        result: success / error，默认 success
    """
    try:
        await database.log_command(
            user_id=user_id,
            group_id=group_id,
            command_name=command_name,
            raw_text=raw_text,
            result=result,
        )
    except Exception:
        _logger.exception(
            f"DB 写入失败: command_log cmd={command_name} result={result}"
        )
