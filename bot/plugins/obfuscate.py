"""
混淆插件 - 私聊图片混淆

流程：
    用户发「混淆」→ 进入混淆模式 → 发送图片 → 发「完成」→ 回复混淆图
"""
import asyncio
import io
import time

import httpx
import nonebot
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from PIL import Image as PILImage

from services.command import register
from services.config import (
    IMAGE_DIR,
    PUBLISH_COOLDOWN_BASE,
    PUBLISH_COOLDOWN_MAX,
    PUBLISH_COOLDOWN_PER_IMAGE,
    PUBLISH_MAX_IMAGES,
    PUBLISH_TIMEOUT,
    SESSION_SCAN_INTERVAL,
)
from services.image_obfuscator import obfuscate
from services.session import (
    create, get_active, complete, cancel, get_expired,
)
from services.throttle import should_reply
from services.logger import get_logger

logger = get_logger(__name__)

OBFUSCATE_TYPE = "obfuscate"

# 每用户一把锁，串行化同用户 session 操作
_user_locks: dict[int, asyncio.Lock] = {}


def _get_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = _user_locks[user_id] = asyncio.Lock()
    return lock


async def _reply(bot: Bot, event: MessageEvent, msg: str, reply_type: str) -> None:
    if should_reply(event.user_id, reply_type):
        await bot.send(event, msg)


_cd_expires: dict[int, float] = {}


# ── 命令入口 ──


async def handle_obfuscate(bot: Bot, event: MessageEvent):
    if event.message_type != "private":
        await _reply(bot, event, "请私聊发送「混淆」使用此功能。", "obf_private_only")
        return

    expires = _cd_expires.get(event.user_id, 0)
    if time.time() < expires:
        remaining = int(expires - time.time())
        await _reply(bot, event, f"混淆冷却中，请等待 {remaining} 秒后再试。", "obf_cooldown")
        return

    create(
        event.user_id,
        OBFUSCATE_TYPE,
        timeout=PUBLISH_TIMEOUT,
        initial_data={"images": []},
    )
    await _reply(
        bot, event,
        f"📷 已进入混淆模式（最多 {PUBLISH_MAX_IMAGES} 张）。\n"
        "请发送图片。发送「完成」开始混淆，发送「取消」退出。",
        "obf_start",
    )


register("obfuscate", handle_obfuscate, description="私聊图片混淆", aliases=["混淆"])

# ── 会话消息拦截 ──


def _obfuscate_rule(event: MessageEvent) -> bool:
    if event.message_type != "private":
        return False
    if get_active(event.user_id, OBFUSCATE_TYPE):
        return True
    return event.get_plaintext().strip() in ("混淆", "obfuscate")


obfuscate_session = on_message(rule=_obfuscate_rule, priority=0, block=True)


@obfuscate_session.handle()
async def handle_session(bot: Bot, event: MessageEvent):
    async with _get_lock(event.user_id):
        await _handle_session_locked(bot, event)


async def _handle_session_locked(bot: Bot, event: MessageEvent):
    msg_text = event.get_plaintext().strip()
    session = get_active(event.user_id, OBFUSCATE_TYPE)

    if session is None:
        await handle_obfuscate(bot, event)
        return

    # 取消
    if msg_text == "取消":
        cancel(session)
        await _reply(bot, event, "已取消混淆。", "obf_cancel")
        return

    # 完成
    if msg_text == "完成":
        images = session.data.get("images", [])
        session.data["images"] = []  # 清空但保留 key，防止并发收图丢失引用
        if not images:
            await _reply(bot, event, "尚未收到任何图片，请先发送图片。", "obf_empty")
            return

        await _reply(bot, event, f"开始处理 {len(images)} 张图片……", "obf_process")

        tmp_paths = []
        for i, image_data in enumerate(images):
            try:
                obfuscated_data = await obfuscate(image_data)
            except Exception as e:
                logger.error(f"混淆失败: {e}")
                continue

            timestamp = time.strftime("%Y-%m-%d_%H%M%S")
            tmp_path = IMAGE_DIR / f"_obfuscate_{timestamp}_{event.user_id}_{i}.jpg"
            tmp_path.write_bytes(obfuscated_data)
            tmp_paths.append(tmp_path)

        if not tmp_paths:
            await _reply(bot, event, "所有图片处理失败，请稍后重试。", "obf_failed")
            complete(session)
            return

        # 合并为一条消息回复
        msg = MessageSegment.text("")
        for p in tmp_paths:
            msg += MessageSegment.image(file=str(p.resolve()))

        sent = 0
        try:
            await bot.send(event, msg)
            sent = len(tmp_paths)
        except Exception as e:
            logger.error(f"发送混淆图失败: {e}")
        finally:
            for p in tmp_paths:
                if p.exists():
                    p.unlink()

        complete(session)
        cd = min(
            PUBLISH_COOLDOWN_BASE + PUBLISH_COOLDOWN_PER_IMAGE * sent,
            PUBLISH_COOLDOWN_MAX,
        )
        _cd_expires[event.user_id] = time.time() + cd

        await _reply(bot, event, f"✓ 已混淆 {sent} 张图片。\n冷却 {cd} 秒后可再次使用。", "obf_done")
        return

    # 收集图片
    img_segs = [seg for seg in event.message if seg.type == "image"]
    if img_segs:
        images = session.data.setdefault("images", [])
        current = len(images)
        for img_seg in img_segs:
            if current >= PUBLISH_MAX_IMAGES:
                await _reply(bot, event, f"已达到上限 {PUBLISH_MAX_IMAGES} 张，发送「完成」开始混淆。", "obf_limit")
                return

            url = img_seg.data.get("url", "")
            if not url:
                continue

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    image_data = resp.content
            except Exception as e:
                logger.error(f"下载图片失败: {e}")
                await _reply(bot, event, "图片下载失败，跳过该张。", "obf_error")
                continue

            fmt = PILImage.open(io.BytesIO(image_data)).format
            if fmt == "GIF":
                await _reply(bot, event, "暂不支持 GIF，已跳过。", "obf_gif")
                continue

            images.append(image_data)
            current += 1

        count = len(images)
        await _reply(bot, event, f"已接收 {count} 张图片。", "obf_count")
        return

    await _reply(
        bot, event,
        "发送图片进行混淆，发送「完成」开始混淆，发送「取消」退出。",
        "obf_prompt",
    )


# ── 超时扫描 ──

async def _check_obfuscate_timeout():
    expired = get_expired(OBFUSCATE_TYPE)
    if not expired:
        return
    try:
        bot_instance = nonebot.get_bot()
    except ValueError:
        return
    for user_id in expired:
        if should_reply(user_id, "obf_timeout"):
            try:
                await bot_instance.send_private_msg(
                    user_id=user_id,
                    message="⏰ 混淆模式已超时，已自动退出。",
                )
            except Exception as e:
                logger.error(f"超时通知发送失败 (user={user_id}): {e}")


driver = nonebot.get_driver()


@driver.on_startup
async def _start_timeout_check():
    from services.scheduler import add_interval_job
    add_interval_job(_check_obfuscate_timeout, seconds=SESSION_SCAN_INTERVAL, job_id="obfuscate_timeout")
