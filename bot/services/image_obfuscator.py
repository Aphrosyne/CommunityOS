"""
图片混淆服务 - Gilbert 曲线像素置换（numpy 加速版）

移植自小番茄核心 JS (xiaofanqie.js)。

算法：
    1. 生成 Gilbert 曲线坐标序列
    2. 按黄金比例偏移在曲线上循环移位
    3. numpy 向量化置换像素
"""
import math
import io
import numpy as np
from PIL import Image

from services.logger import get_logger

logger = get_logger(__name__)


def _gilbert_coords(width: int, height: int) -> np.ndarray:
    """生成 Gilbert 曲线坐标序列，返回 shape (total, 2) 的 numpy 数组"""
    total = width * height
    coords = np.zeros((total, 2), dtype=np.int32)
    _counter = 0

    def _fill(x: int, y: int):
        nonlocal _counter
        coords[_counter] = (x, y)
        _counter += 1

    if width >= height:
        _generate2d(0, 0, width, 0, 0, height, _fill)
    else:
        _generate2d(0, 0, 0, height, width, 0, _fill)

    return coords


def _generate2d(
    x: int, y: int,
    ax: int, ay: int,
    bx: int, by: int,
    fill,
) -> None:
    w = abs(ax + ay)
    h = abs(bx + by)

    dax = 1 if ax > 0 else (-1 if ax < 0 else 0)
    day = 1 if ay > 0 else (-1 if ay < 0 else 0)
    dbx = 1 if bx > 0 else (-1 if bx < 0 else 0)
    dby = 1 if by > 0 else (-1 if by < 0 else 0)

    if h == 1:
        for _ in range(w):
            fill(x, y)
            x += dax
            y += day
        return

    if w == 1:
        for _ in range(h):
            fill(x, y)
            x += dbx
            y += dby
        return

    ax2 = ax // 2
    ay2 = ay // 2
    bx2 = bx // 2
    by2 = by // 2

    w2 = abs(ax2 + ay2)
    h2 = abs(bx2 + by2)

    if 2 * w > 3 * h:
        if w2 % 2 and w > 2:
            ax2 += dax
            ay2 += day

        _generate2d(x, y, ax2, ay2, bx, by, fill)
        _generate2d(x + ax2, y + ay2, ax - ax2, ay - ay2, bx, by, fill)
    else:
        if h2 % 2 and h > 2:
            bx2 += dbx
            by2 += dby

        _generate2d(x, y, bx2, by2, ax2, ay2, fill)
        _generate2d(x + bx2, y + by2, ax, ay, bx - bx2, by - by2, fill)
        _generate2d(
            x + (ax - dax) + (bx2 - dbx),
            y + (ay - day) + (by2 - dby),
            -bx2, -by2, -(ax - ax2), -(ay - ay2), fill,
        )


async def obfuscate(image_data: bytes) -> bytes:
    """对图片执行 Gilbert 曲线混淆

    Args:
        image_data: 原始图片 bytes

    Returns:
        混淆后的 JPEG bytes
    """
    img = Image.open(io.BytesIO(image_data)).convert("RGBA")
    width, height = img.size
    total = width * height

    logger.info(f"开始混淆: {width}x{height} ({total} 像素)")

    # 图片 → numpy (height, width, 4)
    pixels = np.array(img, dtype=np.uint8)

    # Gilbert 曲线坐标
    coords = _gilbert_coords(width, height)

    # 计算源/目标索引映射
    # old_index = coords[i, 0] + coords[i, 1] * width
    old_idx = coords[:, 0] + coords[:, 1] * width  # shape (total,)

    # 黄金比例偏移：像素沿曲线循环移位
    offset = round((math.sqrt(5) - 1) / 2 * total)
    new_idx = np.roll(old_idx, -offset)

    # numpy 向量化置换：result[new_idx] = pixels[old_idx]
    flat = pixels.reshape(-1, 4)  # (total, 4)
    result = np.zeros_like(flat)
    result[new_idx] = flat[old_idx]
    result_img = result.reshape(height, width, 4)

    # 输出 JPEG
    rgb = Image.fromarray(result_img, "RGBA").convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=95)

    logger.info(f"混淆完成: {width}x{height}")

    return buf.getvalue()


async def deobfuscate(image_data: bytes) -> bytes:
    """对混淆图片执行 Gilbert 曲线解混淆（DEC 模式）

    与 obfuscate() 置换方向相反。
    """
    img = Image.open(io.BytesIO(image_data)).convert("RGBA")
    width, height = img.size
    total = width * height

    logger.info(f"开始解混淆: {width}x{height} ({total} 像素)")

    pixels = np.array(img, dtype=np.uint8)
    coords = _gilbert_coords(width, height)

    old_idx = coords[:, 0] + coords[:, 1] * width
    offset = round((math.sqrt(5) - 1) / 2 * total)
    new_idx = np.roll(old_idx, offset)  # DEC: 反向置换

    flat = pixels.reshape(-1, 4)
    result = np.zeros_like(flat)
    result[new_idx] = flat[old_idx]
    result_img = result.reshape(height, width, 4)

    rgb = Image.fromarray(result_img, "RGBA").convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=95)

    logger.info(f"解混淆完成: {width}x{height}")

    return buf.getvalue()
