"""
Logger Service — 按领域分日志文件

日志文件：
    logs/bot.log   — 系统、指令、其他
    logs/image.log — 图片业务（publish / obfuscate / decode）

用法：
    from services.logger import get_logger
    logger = get_logger("image")   # → image.log
    logger = get_logger("bot")     # → bot.log
    logger = get_logger(__name__)  # → bot.log（默认）
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from services.config import DEBUG, LOG_DIR

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 域名 → 日志文件名
_DOMAIN_FILES: dict[str, str] = {
    "image": "image.log",
    "command": "command.log",
}

_initialized = False


def setup_logging() -> None:
    """初始化日志系统（启动时调用一次）"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    level = logging.DEBUG if DEBUG else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # 控制台 handler（所有日志）
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console.setLevel(level)
    root.addHandler(console)

    # bot.log（兜底 + 系统日志）
    _add_file_handler("bot", "bot.log")

    # image.log（仅 image 域）
    _add_file_handler("image", "image.log")

    # command.log（仅 command 域）
    _add_file_handler("command", "command.log")

    # 抑制第三方噪音
    logging.getLogger("nonebot").setLevel(level)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("日志系统已初始化")


def _add_file_handler(domain: str, filename: str) -> None:
    """为指定领域创建文件 handler"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    file_level = logging.INFO  # 文件始终 INFO，debug 不落盘
    handler = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handler.setLevel(file_level)

    # 域名 handler 只收自己域；bot.log 排除所有有独立文件的域
    if domain == "bot":
        handler.addFilter(lambda record: record.name not in _DOMAIN_FILES)
    else:
        handler.addFilter(lambda record, d=domain: record.name == d)

    root = logging.getLogger()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger

    - "image" → image.log + console
    - 其他（含 __name__） → bot.log + console
    """
    return logging.getLogger(name)
