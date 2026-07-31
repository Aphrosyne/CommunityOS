"""共享 pytest fixtures

依据 docs/developer/testing.md §3
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# 让 tests/ 可以 import bot/ 下的模块
BOT_ROOT = Path(__file__).resolve().parent.parent / "bot"
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))


@pytest.fixture
def tmp_db_path(tmp_path):
    """临时数据库文件路径（每个测试独立隔离）"""
    return tmp_path / "test.db"


@pytest.fixture
async def db(tmp_db_path):
    """初始化好的 DatabaseManager（临时数据库），测试结束自动关闭"""
    from services.database import DatabaseManager

    mgr = DatabaseManager(db_path=tmp_db_path)
    await mgr.setup()
    yield mgr
    await mgr.close()


@pytest.fixture
def mock_bot():
    """MockBot fixture — 测试用 NoneBot2 Bot 替身

    依据 docs/developer/testing.md §3 MockBot 模板。
    覆盖常用平台 API：send / delete_msg / set_group_kick / set_group_ban。
    """
    bot = AsyncMock()
    bot.send = AsyncMock()
    bot.delete_msg = AsyncMock()
    bot.set_group_kick = AsyncMock()
    bot.set_group_ban = AsyncMock()
    bot.get_group_member_info = AsyncMock()
    bot.get_group_member_list = AsyncMock()
    return bot


@pytest.fixture
def make_group_event():
    """MockEvent 工厂 — 构造 NoneBot2 GroupMessageEvent

    依据 docs/developer/testing.md §3 MockEvent 模板。
    返回工厂函数，调用时指定 user_id / group_id / raw_message。
    """
    from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
    from nonebot.adapters.onebot.v11.event import Sender

    def _make(user_id: int = 123456, group_id: int = 789012, raw_message: str = ""):
        return GroupMessageEvent(
            time=1234567890,
            self_id=111111,
            post_type="message",
            message_type="group",
            sub_type="normal",
            user_id=user_id,
            group_id=group_id,
            message=Message(raw_message),
            raw_message=raw_message,
            font=0,
            sender=Sender(user_id=user_id, nickname="测试用户"),
            message_id=1,
            message_seq=1,
        )
    return _make


@pytest.fixture
def make_private_event():
    """MockEvent 工厂 — 构造 NoneBot2 PrivateMessageEvent"""
    from nonebot.adapters.onebot.v11 import PrivateMessageEvent, Message
    from nonebot.adapters.onebot.v11.event import Sender

    def _make(user_id: int = 123456, raw_message: str = ""):
        return PrivateMessageEvent(
            time=1234567890,
            self_id=111111,
            post_type="message",
            message_type="private",
            sub_type="friend",
            user_id=user_id,
            message=Message(raw_message),
            raw_message=raw_message,
            font=0,
            sender=Sender(user_id=user_id, nickname="测试用户"),
            message_id=1,
            message_seq=1,
        )
    return _make

