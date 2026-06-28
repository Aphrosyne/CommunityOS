"""
日志服务 - 集中管理所有日志

输出目标：
    - 控制台（开发调试）
    - 文件（bot/logs/，保留 30 天）
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from services.config import DEBUG, LOG_DIR

LOG_FORMAT = (
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """初始化日志系统"""
    level = logging.DEBUG if DEBUG else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console.setLevel(level)
    root.addHandler(console)

    # 文件输出（按大小轮转，每文件 10MB，保留 5 个）
    file_handler = RotatingFileHandler(
        LOG_DIR / "bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    file_handler.setLevel(logging.INFO)
    root.addHandler(file_handler)

    # 抑制第三方库的 DEBUG 日志
    logging.getLogger("nonebot").setLevel(level)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("日志系统已初始化")


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger"""
    return logging.getLogger(name)
