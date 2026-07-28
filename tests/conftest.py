"""共享 pytest fixtures

依据 docs/developer/testing.md §3
"""
import pytest


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
