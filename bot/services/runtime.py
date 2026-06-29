"""
运行时服务 - 记录启动时间，提供运行状态信息
"""
import time
from datetime import timedelta

_start_time: float | None = None


def mark_start() -> None:
    """标记启动时间，在 core 启动钩子中调用"""
    global _start_time
    _start_time = time.time()


def get_uptime() -> str:
    """返回人类可读的运行时长"""
    if _start_time is None:
        return "未知"

    delta = int(time.time() - _start_time)
    td = timedelta(seconds=delta)

    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} 天")
    if hours:
        parts.append(f"{hours} 小时")
    parts.append(f"{minutes} 分")

    return " ".join(parts)
