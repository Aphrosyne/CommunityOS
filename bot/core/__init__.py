"""
核心模块 - NoneBot2 初始化与启动钩子
"""
from nonebot import get_driver
from services.logger import setup_logging

driver = get_driver()


@driver.on_startup
async def on_startup():
    """机器人启动时执行"""
    setup_logging()
    from services.scheduler import start_scheduler
    start_scheduler()


@driver.on_shutdown
async def on_shutdown():
    """机器人关闭时执行"""
    from services.scheduler import stop_scheduler
    stop_scheduler()
