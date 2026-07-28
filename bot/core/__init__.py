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
    from services.scheduler import start_scheduler, add_interval_job
    from services.runtime import mark_start
    from services.cleanup import run_cleanup
    from services import database
    start_scheduler()
    mark_start()
    add_interval_job(run_cleanup, seconds=600, job_id="cleanup")
    await database.setup()
    from services.permission import seed_from_env
    await seed_from_env()


@driver.on_shutdown
async def on_shutdown():
    """机器人关闭时执行"""
    from services.scheduler import stop_scheduler
    from services import database
    stop_scheduler()
    await database.close()
