"""
存储服务 - 文件持久化
"""
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Optional

from services.config import IMAGE_DIR
from services.logger import get_logger

logger = get_logger(__name__)


async def save_image(data: bytes, user_id: int, filename: Optional[str] = None) -> Path:
    """保存图片到 data/images/

    Args:
        data: 图片二进制数据
        user_id: 投稿用户 QQ 号
        filename: 自定义文件名（不含路径），不传则自动生成

    Returns:
        保存后的文件路径
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"{timestamp}_{user_id}.png"

    filepath = IMAGE_DIR / filename
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(data)

    logger.info(f"图片已保存: {filepath}")
    return filepath


def get_image_path(filename: str) -> Path:
    """获取图片完整路径"""
    return IMAGE_DIR / filename
