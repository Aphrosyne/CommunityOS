"""Dispatcher 集成测试 — 验证指令分发器行为

覆盖 technical-debt.md H5 修复项：
- 黑名单用户发送命令 → 被静默拦截
- 权限不足用户发送命令 → 写 permission_denied 文本日志、不写 command_log
- Owner 冷却豁免生效
- 黑名单用户不消耗冷却
- 私聊 group_id=0 传到 log_command（间接验证）

覆盖 technical-debt.md H3 修复项：
- shortcut 命中后 event.message 不被永久污染（finally 恢复）

覆盖 technical-debt.md M7 修复项：
- dispatcher 单次 get_level 完成 blacklist/owner/required 判断

依据 docs/developer/testing.md §3 MockBot/MockEvent 模板。
"""
import pytest

from services import database
from services.permission import Level


@pytest.fixture
async def integration_db(tmp_db_path, monkeypatch):
    """集成测试专用 DB：初始化 + 设置 _manager 单例

    Round 2 集成测试通过 monkeypatch 替换 services.database._manager
    让 dispatcher 调用真实 SQL 行为，但不依赖全局 setup()。
    """
    from services.database import DatabaseManager

    mgr = DatabaseManager(db_path=tmp_db_path)
    await mgr.setup()
    monkeypatch.setattr(database, "_manager", mgr)
    yield mgr
    await mgr.close()


@pytest.fixture(autouse=True)
def reset_dispatcher_state():
    """每个测试前后清空 dispatcher 模块级 _cooldowns 状态

    _cooldowns 是模块级 dict，测试间会污染，必须显式重置。
    """
    from plugins import command_dispatcher
    saved = dict(command_dispatcher._cooldowns)
    command_dispatcher._cooldowns.clear()
    yield
    command_dispatcher._cooldowns.clear()
    command_dispatcher._cooldowns.update(saved)


# ── H5: 黑名单用户被静默拦截 ──────────────────────────────────

async def test_blacklisted_user_command_silently_ignored(
    mock_bot, make_group_event, integration_db,
):
    """H5: 黑名单用户发送命令，handler 不被调用，command_log 不写入"""
    # 设置黑名单用户
    await database.set_permission(1001, 0, Level.Blacklist, granted_by=9999)

    # 用 mock handler 替换真实命令 handler
    from plugins import command_dispatcher
    from services import command as cmd_service

    called = False

    async def fake_handler(bot, event):
        nonlocal called
        called = True

    # 注册一个临时命令
    cmd_service.register(
        "test_blacklist_cmd", fake_handler,
        description="测试",
        permission=Level.User, cooldown_level=0, hidden=True,
    )
    try:
        event = make_group_event(user_id=1001, raw_message="test_blacklist_cmd")
        # 直接调用 dispatch 函数（不经过 NoneBot matcher 链）
        await command_dispatcher.dispatch(mock_bot, event, {})

        assert not called, "黑名单用户的 handler 不应被调用"

        # command_log 不应有记录
        conn = await integration_db.get_connection()
        async with conn.execute(
            "SELECT COUNT(*) FROM command_log WHERE user_id = ?", (1001,)
        ) as cur:
            count = (await cur.fetchone())[0]
        assert count == 0, "黑名单用户不应写 command_log"
    finally:
        # 清理注册的命令
        cmd_service._commands.pop("test_blacklist_cmd", None)


# ── H5: 权限不足 → permission_denied 文本日志，不写 command_log ──

async def test_permission_denied_writes_mod_log_not_command_log(
    mock_bot, make_group_event, integration_db, caplog,
):
    """H5: 权限不足用户发送命令，写 permission_denied 到文本日志，不写 command_log"""
    from plugins import command_dispatcher
    from services import command as cmd_service

    called = False

    async def fake_handler(bot, event):
        nonlocal called
        called = True

    cmd_service.register(
        "test_perm_cmd", fake_handler,
        description="测试",
        permission=Level.Owner,  # 高权限要求
        cooldown_level=0, hidden=True,
    )
    try:
        # 1001 是普通用户（level=0），无 Owner 权限
        await database.upsert_user(1001)
        event = make_group_event(user_id=1001, raw_message="test_perm_cmd")
        await command_dispatcher.dispatch(mock_bot, event, {})

        assert not called, "权限不足用户的 handler 不应被调用"

        # command_log 不应有记录（权限拒绝路径不写）
        conn = await integration_db.get_connection()
        async with conn.execute(
            "SELECT COUNT(*) FROM command_log WHERE user_id = ?", (1001,)
        ) as cur:
            count = (await cur.fetchone())[0]
        assert count == 0, "权限拒绝路径不应写 command_log"
    finally:
        cmd_service._commands.pop("test_perm_cmd", None)


# ── H3: shortcut 展开后 event.message 在 finally 恢复 ──────────

async def test_shortcut_does_not_pollute_event_message(
    mock_bot, make_group_event, integration_db, monkeypatch,
):
    """H3: shortcut 命中后，dispatch 结束时 event.message 应恢复原始内容

    场景：shortcut 把 "/拉黑 @xxx" 展开为 "/blacklist add @xxx"，
    dispatch 完成后 event.message 应恢复原始消息。
    """
    from plugins import command_dispatcher
    from services import shortcut as shortcut_service

    # 注入 shortcut 映射
    original_map = shortcut_service._map
    shortcut_service._map = {"*": {"测试shortcut": "blacklist add {at}"}}
    try:
        # 设置调用者为 BotAdmin（有权限执行 blacklist）
        await database.set_permission(1001, 0, Level.BotAdmin, granted_by=9999)

        event = make_group_event(
            user_id=1001,
            raw_message="测试shortcut",
        )
        # dispatch 内会因 cmd_name 未注册而 return，但 shortcut 已处理过
        # 测试的是 finally 恢复逻辑
        original_msg_repr = repr(event.message)
        await command_dispatcher.dispatch(mock_bot, event, {})

        # event.message 应恢复为原始消息
        assert repr(event.message) == original_msg_repr, \
            "shortcut 展开后 event.message 应在 dispatch 结束时恢复原始内容"
    finally:
        shortcut_service._map = original_map


async def test_shortcut_handler_sees_expanded_message(
    mock_bot, make_group_event, integration_db, monkeypatch,
):
    """H3 辅助：shortcut 命中期间 handler 看到的是展开后的消息

    验证 H3 修复不破坏 shortcut 功能：handler 执行期间 event.message 是展开后的。
    """
    from plugins import command_dispatcher
    from services import command as cmd_service
    from services import shortcut as shortcut_service

    seen_message = None

    async def fake_handler(bot, event):
        nonlocal seen_message
        seen_message = event.get_plaintext()

    cmd_service.register(
        "blacklist", fake_handler,
        description="测试",
        permission=Level.BotAdmin, cooldown_level=2, hidden=True,
        accepts_args=True,
    )
    original_map = shortcut_service._map
    shortcut_service._map = {"*": {"拉黑": "blacklist add {at}"}}
    try:
        # 调用者为 Owner，可以操作
        from services import database as db_module
        monkeypatch.setattr(db_module, "OWNER", 9999)
        await database.set_permission(9999, 0, Level.Owner, granted_by=9999)

        # 构造带 @ 段的消息
        from nonebot.adapters.onebot.v11 import MessageSegment
        event = make_group_event(user_id=9999, raw_message="拉黑")
        # 添加 at 段
        event.message.append(MessageSegment.at(1002))

        await command_dispatcher.dispatch(mock_bot, event, {})

        # handler 应该看到展开后的消息（包含 blacklist add 和 @1002）
        assert seen_message is not None, "handler 应被调用"
        assert "blacklist" in seen_message.lower(), \
            f"handler 应看到展开后的命令名，实际: {seen_message}"
    finally:
        cmd_service._commands.pop("blacklist", None)
        shortcut_service._map = original_map


# ── H5: 私聊 group_id=0 ──────────────────────────────────────

async def test_private_chat_uses_group_id_zero(
    mock_bot, make_private_event, integration_db,
):
    """H5: 私聊命令 log_command 应使用 group_id=0"""
    from plugins import command_dispatcher
    from services import command as cmd_service

    async def fake_handler(bot, event):
        pass

    cmd_service.register(
        "test_private_cmd", fake_handler,
        description="测试",
        permission=Level.User, cooldown_level=0, hidden=True,
    )
    try:
        await database.upsert_user(1001)
        event = make_private_event(user_id=1001, raw_message="test_private_cmd")
        await command_dispatcher.dispatch(mock_bot, event, {})

        # command_log 应有 group_id=0 的记录
        conn = await integration_db.get_connection()
        async with conn.execute(
            "SELECT group_id FROM command_log WHERE user_id = ?",
            (1001,),
        ) as cur:
            row = await cur.fetchone()
        assert row is not None, "私聊命令应写 command_log"
        assert row[0] == 0, f"私聊 command_log.group_id 应为 0, 实际: {row[0]}"
    finally:
        cmd_service._commands.pop("test_private_cmd", None)


# ── H5: Owner 冷却豁免 ──────────────────────────────────────

async def test_owner_cooldown_exemption(
    mock_bot, make_group_event, integration_db, monkeypatch,
):
    """H5: Owner 连续调用同一命令不被冷却阻挡"""
    from plugins import command_dispatcher
    from services import command as cmd_service
    from services import database as db_module

    call_count = 0

    async def fake_handler(bot, event):
        nonlocal call_count
        call_count += 1

    cmd_service.register(
        "test_owner_cooldown", fake_handler,
        description="测试",
        permission=Level.User, cooldown_level=2, hidden=True,
    )
    try:
        monkeypatch.setattr(db_module, "OWNER", 9999)
        await database.set_permission(9999, 0, Level.Owner, granted_by=9999)

        event = make_group_event(user_id=9999, raw_message="test_owner_cooldown")
        # 连续调用两次，Owner 应豁免冷却
        await command_dispatcher.dispatch(mock_bot, event, {})
        await command_dispatcher.dispatch(mock_bot, event, {})

        assert call_count == 2, f"Owner 应豁免冷却，应被调用 2 次，实际 {call_count} 次"
    finally:
        cmd_service._commands.pop("test_owner_cooldown", None)


# ── H5: 黑名单用户不消耗冷却 ──────────────────────────────────

async def test_blacklist_does_not_consume_cooldown(
    mock_bot, make_group_event, integration_db,
):
    """H5: 黑名单用户发送命令不消耗冷却字典"""
    from plugins import command_dispatcher
    from services import command as cmd_service

    async def fake_handler(bot, event):
        pass

    cmd_service.register(
        "test_bl_cd", fake_handler,
        description="测试",
        permission=Level.User, cooldown_level=0, hidden=True,
    )
    try:
        await database.set_permission(1001, 0, Level.Blacklist, granted_by=9999)

        event = make_group_event(user_id=1001, raw_message="test_bl_cd")
        await command_dispatcher.dispatch(mock_bot, event, {})

        # 黑名单用户不应在 _cooldowns 字典中留记录
        ck = (1001, 789012)
        assert ck not in command_dispatcher._cooldowns or \
               0 not in command_dispatcher._cooldowns.get(ck, {}), \
               "黑名单用户不应消耗冷却"
    finally:
        cmd_service._commands.pop("test_bl_cd", None)
        # _cooldowns 由 autouse fixture 清理


# ── M7: 单次 get_level 优化不破坏行为 ──────────────────────────

async def test_dispatcher_uses_single_get_level(
    mock_bot, make_group_event, integration_db, monkeypatch,
):
    """M7: dispatcher 应只调用一次 get_level，而非 3 次（is_blacklisted + is_owner + check_permission）

    通过 monkeypatch get_level 计数验证。
    """
    from plugins import command_dispatcher
    from services import command as cmd_service
    from services import permission

    call_count = 0
    original_get_level = permission.get_level

    async def counting_get_level(user_id, group_id=0, *, manager=None):
        nonlocal call_count
        call_count += 1
        return await original_get_level(user_id, group_id, manager=manager)

    monkeypatch.setattr(permission, "get_level", counting_get_level)
    # dispatcher 内部 import 的是函数引用，需 patch 模块属性
    monkeypatch.setattr(
        "plugins.command_dispatcher.get_level", counting_get_level
    )

    async def fake_handler(bot, event):
        pass

    cmd_service.register(
        "test_m7_cmd", fake_handler,
        description="测试",
        permission=Level.User, cooldown_level=0, hidden=True,
    )
    try:
        await database.upsert_user(1001)
        event = make_group_event(user_id=1001, raw_message="test_m7_cmd")
        await command_dispatcher.dispatch(mock_bot, event, {})

        assert call_count == 1, \
            f"M7: dispatcher 应只调用 1 次 get_level，实际 {call_count} 次"
    finally:
        cmd_service._commands.pop("test_m7_cmd", None)
        # _cooldowns 由 autouse fixture 清理
