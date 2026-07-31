"""Audit Service 单元测试

依据:
    docs/technical-debt.md TD1 / TD2 (M7 audit log 重复代码抽取)
    bot/services/audit.py

覆盖:
    - log_moderation 委托 database.log_moderation 且参数透传
    - log_moderation 吞咽异常（Q4-A: 失败仅记日志不抛出）
    - log_command 委托 database.log_command 且参数透传
    - log_command 吞咽异常（Q1-A: 失败仅记日志不抛出）
    - details=None 透传
"""
from unittest.mock import AsyncMock, patch

import pytest

from services import audit


@pytest.mark.asyncio
async def test_log_moderation_delegates_to_database():
    """log_moderation 透传所有参数到 database.log_moderation"""
    with patch("services.database.log_moderation", new=AsyncMock()) as mock_fn:
        await audit.log_moderation(
            action="mute",
            user_id=123,
            operator_id=456,
            group_id=789,
            reason="test_reason",
            details={"result": "success"},
        )

    mock_fn.assert_awaited_once_with(
        action="mute",
        user_id=123,
        operator_id=456,
        group_id=789,
        reason="test_reason",
        details={"result": "success"},
    )


@pytest.mark.asyncio
async def test_log_moderation_defaults_none():
    """reason / details 默认 None 透传"""
    with patch("services.database.log_moderation", new=AsyncMock()) as mock_fn:
        await audit.log_moderation(
            action="auto_recall",
            user_id=111,
            operator_id=0,
            group_id=200,
        )

    mock_fn.assert_awaited_once_with(
        action="auto_recall",
        user_id=111,
        operator_id=0,
        group_id=200,
        reason=None,
        details=None,
    )


@pytest.mark.asyncio
async def test_log_moderation_swallows_exception():
    """Q4-A: database 抛异常时 log_moderation 不向上抛出"""
    with patch(
        "services.database.log_moderation",
        new=AsyncMock(side_effect=RuntimeError("DB down")),
    ):
        # 不应抛出
        await audit.log_moderation(
            action="mute",
            user_id=1,
            operator_id=2,
            group_id=3,
        )


@pytest.mark.asyncio
async def test_log_command_delegates_to_database():
    """log_command 透传所有参数到 database.log_command"""
    with patch("services.database.log_command", new=AsyncMock()) as mock_fn:
        await audit.log_command(
            user_id=100,
            group_id=200,
            command_name="help",
            raw_text="help 图片",
            result="success",
        )

    mock_fn.assert_awaited_once_with(
        user_id=100,
        group_id=200,
        command_name="help",
        raw_text="help 图片",
        result="success",
    )


@pytest.mark.asyncio
async def test_log_command_defaults():
    """raw_text 默认 None / result 默认 success 透传"""
    with patch("services.database.log_command", new=AsyncMock()) as mock_fn:
        await audit.log_command(
            user_id=10,
            group_id=0,
            command_name="mute",
        )

    mock_fn.assert_awaited_once_with(
        user_id=10,
        group_id=0,
        command_name="mute",
        raw_text=None,
        result="success",
    )


@pytest.mark.asyncio
async def test_log_command_swallows_exception():
    """Q1-A: database 抛异常时 log_command 不向上抛出"""
    with patch(
        "services.database.log_command",
        new=AsyncMock(side_effect=RuntimeError("DB locked")),
    ):
        # 不应抛出
        await audit.log_command(
            user_id=1,
            group_id=2,
            command_name="error_cmd",
            raw_text="error_cmd",
            result="error",
        )


@pytest.mark.asyncio
async def test_log_moderation_exception_does_not_block_caller():
    """Q4-A: 调用方在 log_moderation 失败后仍能继续执行（模拟插件流程）"""
    call_log = []

    async def caller():
        call_log.append("before")
        await audit.log_moderation(
            action="mute", user_id=1, operator_id=2, group_id=3
        )
        call_log.append("after")  # 应能执行到这里

    with patch(
        "services.database.log_moderation",
        new=AsyncMock(side_effect=Exception("fail")),
    ):
        await caller()

    assert call_log == ["before", "after"]
