"""
图片投稿插件 - 私聊收图 → 混淆 → 转发到指定群

功能：
    - 任意用户私聊机器人发送图片
    - Gilbert 曲线混淆
    - 转发混淆图到 .env 配置的目标群
    - 60 秒冷却时间
"""
import io
import time
from pathlib import Path

import httpx
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from PIL import Image as PILImage

from services.config import IMAGE_SUBMIT_GROUP, IMAGE_COOLDOWN, IMAGE_DECODE_URL, IMAGE_DIR
from services.image_obfuscator import obfuscate
from services.logger import get_logger

logger = get_logger(__name__)

# 冷却记录: {user_id: last_submit_timestamp}
_cooldowns: dict[int, float] = {}


def _check_cooldown(user_id: int) -> tuple[bool, int]:
    """检查用户是否在冷却中

    Returns:
        (是否冷却中, 剩余秒数)
    """
    now = time.time()
    last = _cooldowns.get(user_id, 0)
    elapsed = now - last
    if elapsed < IMAGE_COOLDOWN:
        return True, int(IMAGE_COOLDOWN - elapsed)
    return False, 0


# 仅匹配私聊消息
image_submit = on_message(priority=5, block=True)


@image_submit.handle()
async def handle_image_submit(bot: Bot, event: MessageEvent):
    # 仅处理私聊
    if event.message_type != "private":
        return

    # 检查是否配置了目标群
    if IMAGE_SUBMIT_GROUP == 0:
        await image_submit.finish("图片投稿功能尚未配置，请联系管理员。")
        return

    # 提取图片段
    images = [seg for seg in event.message if seg.type == "image"]
    if not images:
        await image_submit.finish(
            "请发送一张图片进行投稿。\n"
            "提示：直接发送图片即可，不需要额外文字。"
        )
        return

    user_id = event.user_id

    # 冷却检查 + 立即标记（防止并发提交绕过冷却）
    cooling, remaining = _check_cooldown(user_id)
    if cooling:
        await image_submit.finish(f"投稿冷却中，请等待 {remaining} 秒后再试。")
        return
    _cooldowns[user_id] = time.time()

    # 处理第一张图片
    img_seg = images[0]
    url = img_seg.data.get("url", "")

    if not url:
        await image_submit.finish("图片下载链接获取失败，请重试。")
        return

    # 下载图片
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            image_data = resp.content
    except Exception as e:
        logger.error(f"下载图片失败: {e}")
        await image_submit.finish("图片下载失败，请稍后重试。")
        return

    # 格式过滤：GIF 不支持
    fmt = PILImage.open(io.BytesIO(image_data)).format
    if fmt == "GIF":
        await image_submit.finish("暂不支持 GIF 投稿，请发送静态图片。")
        return

    # 混淆处理
    try:
        obfuscated_data = await obfuscate(image_data)
    except Exception as e:
        logger.error(f"混淆处理失败: {e}")
        await image_submit.finish("图片处理失败，请稍后重试。")
        return

    # 写入临时文件
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    tmp_path = IMAGE_DIR / f"_{timestamp}_{user_id}.jpg"

    try:
        tmp_path.write_bytes(obfuscated_data)
    except Exception as e:
        logger.error(f"写入临时文件失败: {e}")
        await image_submit.finish("图片保存失败，请稍后重试。")
        return

    # 转发到目标群（@投稿人 + 混淆图）
    try:
        abs_path = tmp_path.resolve()
        msg = (
            MessageSegment.at(user_id)
            + MessageSegment.image(file=str(abs_path))
            + MessageSegment.text(f" {IMAGE_DECODE_URL}")
        )
        await bot.send_group_msg(
            group_id=IMAGE_SUBMIT_GROUP,
            message=msg,
        )
    except Exception as e:
        logger.error(f"转发到群失败: {e}")
        await image_submit.finish("投稿失败，请稍后重试。")
        return
    finally:
        # 发送完成后删除临时文件
        if tmp_path.exists():
            tmp_path.unlink()

    logger.info(f"用户 {user_id} 投稿完成")
    await image_submit.finish("已投稿 ✅")
