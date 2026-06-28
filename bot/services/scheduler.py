"""
定时调度服务 - 管理定时任务

基于 APScheduler，支持：
    - cron 表达式
    - 固定间隔
    - 单次定时
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.logger import get_logger

logger = get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """启动调度器"""
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    logger.info("定时调度器已启动")


def stop_scheduler() -> None:
    """停止调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("定时调度器已停止")


def get_scheduler() -> AsyncIOScheduler:
    """获取调度器实例"""
    if _scheduler is None:
        raise RuntimeError("调度器尚未启动，请先调用 start_scheduler()")
    return _scheduler


def add_cron_job(func, cron_expr: str, job_id: str | None = None) -> str:
    """添加 cron 定时任务

    Args:
        func: 任务函数
        cron_expr: cron 表达式，如 "0 0 * * *"（每天零点）
        job_id: 任务标识（可选）

    Returns:
        job_id: 任务标识

    Example:
        add_cron_job(daily_backup, "0 3 * * *", job_id="daily_backup")
    """
    minute, hour, day, month, day_of_week = cron_expr.split()
    scheduler = get_scheduler()
    job = scheduler.add_job(
        func,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"已添加 cron 任务: {job_id or job.id} (schedule: {cron_expr})")
    return job.id


def add_interval_job(func, seconds: int, job_id: str | None = None) -> str:
    """添加固定间隔任务

    Args:
        func: 任务函数
        seconds: 间隔秒数
        job_id: 任务标识（可选）
    """
    scheduler = get_scheduler()
    job = scheduler.add_job(
        func,
        "interval",
        seconds=seconds,
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"已添加间隔任务: {job_id or job.id} (每 {seconds}s)")
    return job.id


def remove_job(job_id: str) -> None:
    """移除定时任务"""
    scheduler = get_scheduler()
    scheduler.remove_job(job_id)
    logger.info(f"已移除任务: {job_id}")
