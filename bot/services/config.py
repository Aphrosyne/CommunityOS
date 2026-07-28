"""
配置服务 - 统一配置管理

基于 NoneBot2 的 pydantic 配置，提供类型安全的配置项。
"""
import os
from pathlib import Path

from version import BOT_VERSION

# Bot 根目录
BOT_ROOT = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = Path(os.getenv("DATA_DIR", BOT_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 日志目录
LOG_DIR = BOT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 备份目录
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", BOT_ROOT.parent / "backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 调试模式
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DEBUG_NONEBOT = os.getenv("DEBUG_NONEBOT", "false").lower() == "true"

# 权限（Bot Admin，非 QQ 群管理员）
OWNER = int(os.getenv("OWNER", "0"))
ADMINS: list[int] = [int(x.strip()) for x in os.getenv("ADMINS", "").split(",") if x.strip()]

# NoneBot2 超级用户（与 Bot Admin 无关）
import json  # noqa: E402
SUPERUSERS: list[str] = json.loads(os.getenv("SUPERUSERS", "[]"))

# 机器人 QQ
BOT_QQ = int(os.getenv("BOT_QQ", "0"))

# 被 @ 时的回复内容（已迁移至 runtime.json，见 services/runtime_config.py）

# 图片投稿
MANAGED_GROUPS: list[int] = [int(x.strip()) for x in os.getenv("MANAGED_GROUPS", "").split(",") if x.strip()]
IMAGE_MAX_FILE_SIZE = int(os.getenv("IMAGE_MAX_FILE_SIZE", "20"))
IMAGE_CACHE_MAX_MB = int(os.getenv("IMAGE_CACHE_MAX_MB", "500"))
IMAGE_MAX_PIXELS = int(os.getenv("IMAGE_MAX_PIXELS", "20000000"))
IMAGE_WEBSITE_MAX_PIXELS = int(os.getenv("IMAGE_WEBSITE_MAX_PIXELS", "8000000"))

# 发布模式超时
PUBLISH_TIMEOUT = int(os.getenv("PUBLISH_TIMEOUT", "180"))
SESSION_SCAN_INTERVAL = int(os.getenv("SESSION_SCAN_INTERVAL", "10"))
PUBLISH_MAX_IMAGES = int(os.getenv("PUBLISH_MAX_IMAGES", "10"))
PUBLISH_COOLDOWN_BASE = int(os.getenv("PUBLISH_COOLDOWN_BASE", "30"))
PUBLISH_COOLDOWN_PER_IMAGE = int(os.getenv("PUBLISH_COOLDOWN_PER_IMAGE", "10"))
PUBLISH_COOLDOWN_MAX = int(os.getenv("PUBLISH_COOLDOWN_MAX", "90"))

# 指令冷却等级（秒）
COMMAND_COOLDOWN_L0 = int(os.getenv("COMMAND_COOLDOWN_L0", "3"))
COMMAND_COOLDOWN_L1 = int(os.getenv("COMMAND_COOLDOWN_L1", "5"))
COMMAND_COOLDOWN_L2 = int(os.getenv("COMMAND_COOLDOWN_L2", "10"))

# 等级 → 秒数映射
COMMAND_COOLDOWNS = {
    0: COMMAND_COOLDOWN_L0,
    1: COMMAND_COOLDOWN_L1,
    2: COMMAND_COOLDOWN_L2,
}

# 版本号见 version.py（已从 .env 迁出）

# 图片存储目录
IMAGE_DIR = DATA_DIR / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_data_path(filename: str) -> Path:
    """获取 data/ 目录下文件的完整路径"""
    return DATA_DIR / filename


def get_log_path(filename: str) -> Path:
    """获取 logs/ 目录下文件的完整路径"""
    return LOG_DIR / filename
