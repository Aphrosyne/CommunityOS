"""
解混淆插件 - 私聊图片解混淆

流程：
    用户发「解混淆」→ 进入解混淆模式 → 发送图片 → 发「完成」→ 回复解混淆图
"""
import asyncio
import io
import time

import httpx
import nonebot
from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from PIL import Image as PILImage

from services.command import register
from services.config import (
    IMAGE_DECODE_URL,
    IMAGE_DIR,
    PUBLISH_COOLDOWN_BASE,
    PUBLISH_COOLDOWN_MAX,
    PUBLISH_COOLDOWN_PER_IMAGE,
    PUBLISH_MAX_IMAGES,
    PUBLISH_TIMEOUT,
    SESSION_SCAN_INTERVAL,
)
from services.image_obfuscator import deobfuscate
from services.session import (
    create, get_active, complete, cancel, get_expired,
)
from services.throttle import should_reply
from services.logger import get_logger

logger = get_logger(__name__)

DECODE_TYPE = "decode"

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


async def handle_decode(bot: Bot, event: MessageEvent):
    if event.message_type != "private":
        await _reply(bot, event, "请私聊发送「解图」使用此功能。", "dec_private_only")
        return

    expires = _cd_expires.get(event.user_id, 0)
    if time.time() < expires:
        remaining = int(expires - time.time())
        await _reply(bot, event, f"解混淆冷却中，请等待 {remaining} 秒后再试。", "dec_cooldown")
        return

    create(
        event.user_id,
        DECODE_TYPE,
        timeout=PUBLISH_TIMEOUT,
        initial_data={"images": []},
    )
    await _reply(
        bot, event,
        f"📷 已进入解混淆模式（最多 {PUBLISH_MAX_IMAGES} 张）。\n"
        "请发送图片。发送「完成」开始解混淆，发送「取消」退出。",
        "dec_start",
    )


register("decode", handle_decode, description="私聊图片解混淆", aliases=["解图"])

# ── 会话消息拦截 ──


def _decode_rule(event: MessageEvent) -> bool:
    if event.message_type != "private":
        return False
    if get_active(event.user_id, DECODE_TYPE):
        return True
    msg = event.get_plaintext().strip()
    # 命令入口
    if msg in ("解图", "decode"):
        return True
    # 自动识别：转发 publish 消息（含 IMAGE_DECODE_URL + 图片）
    if IMAGE_DECODE_URL and IMAGE_DECODE_URL in msg:
        return any(seg.type == "image" for seg in event.message)
    return False


decode_session = on_message(rule=_decode_rule, priority=0, block=True)


@decode_session.handle()
async def handle_session(bot: Bot, event: MessageEvent):
    async with _get_lock(event.user_id):
        await _handle_session_locked(bot, event)


async def _handle_session_locked(bot: Bot, event: MessageEvent):
    msg_text = event.get_plaintext().strip()
    session = get_active(event.user_id, DECODE_TYPE)

    if session is None:
        # 自动识别 → 即时解混淆，不创建 session
        if IMAGE_DECODE_URL and IMAGE_DECODE_URL in msg_text:
            await _auto_decode(bot, event)
            return
        # 命令入口 → 进入 session 模式
        await handle_decode(bot, event)
        return

    # 取消
    if msg_text == "取消":
        cancel(session)
        await _reply(bot, event, "已取消解混淆。", "dec_cancel")
        return

    # 完成
    if msg_text == "完成":
        images = session.data.get("images", [])
        session.data["images"] = []  # 清空但保留 key，防止并发收图丢失引用
        if not images:
            await _reply(bot, event, "尚未收到任何图片，请先发送图片。", "dec_empty")
            return

        await _reply(bot, event, f"开始处理 {len(images)} 张图片……", "dec_process")

        tmp_paths = await _deobfuscate_batch(images, event.user_id, "decode")

        if not tmp_paths:
            await _reply(bot, event, "所有图片处理失败，请稍后重试。", "dec_failed")
            complete(session)
            return

        msg = MessageSegment.text("")
        for p in tmp_paths:
            msg += MessageSegment.image(file=str(p.resolve()))

        sent = 0
        try:
            await bot.send(event, msg)
            sent = len(tmp_paths)
        except Exception as e:
            logger.error(f"发送解混淆图失败: {e}")
        finally:
            _cleanup_tmp(tmp_paths)

        complete(session)
        cd = min(
            PUBLISH_COOLDOWN_BASE + PUBLISH_COOLDOWN_PER_IMAGE * sent,
            PUBLISH_COOLDOWN_MAX,
        )
        _cd_expires[event.user_id] = time.time() + cd

        await _reply(bot, event, f"✓ 已解混淆 {sent} 张图片。\n冷却 {cd} 秒后可再次使用。", "dec_done")
        return

    # 收集图片
    img_segs = [seg for seg in event.message if seg.type == "image"]
    if img_segs:
        images = session.data.setdefault("images", [])
        current = len(images)
        for img_seg in img_segs:
            if current >= PUBLISH_MAX_IMAGES:
                await _reply(bot, event, f"已达到上限 {PUBLISH_MAX_IMAGES} 张，发送「完成」开始解混淆。", "dec_limit")
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
                await _reply(bot, event, "图片下载失败，跳过该张。", "dec_error")
                continue

            fmt = PILImage.open(io.BytesIO(image_data)).format
            if fmt == "GIF":
                await _reply(bot, event, "暂不支持 GIF，已跳过。", "dec_gif")
                continue

            images.append(image_data)
            current += 1

        count = len(images)
        await _reply(bot, event, f"已接收 {count} 张图片。", "dec_count")
        return

    await _reply(
        bot, event,
        "发送图片进行解混淆，发送「完成」开始解混淆，发送「取消」退出。",
        "dec_prompt",
    )


# ── 图片处理公共函数 ──


async def _download_images(img_segs) -> list[bytes]:
    """从 MessageSegment 列表下载图片，GIF 过滤，返回 bytes 列表"""
    results = []
    for img_seg in img_segs[:PUBLISH_MAX_IMAGES]:
        url = img_seg.data.get("url", "")
        if not url:
            continue
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            continue

        fmt = PILImage.open(io.BytesIO(data)).format
        if fmt == "GIF":
            continue

        results.append(data)
    return results


async def _deobfuscate_batch(images: list[bytes], user_id: int, prefix: str) -> list[Path]:
    """批量解混淆 + 写临时文件，返回路径列表"""
    paths = []
    for i, data in enumerate(images):
        try:
            result = await deobfuscate(data)
        except Exception as e:
            logger.error(f"解混淆失败: {e}")
            continue

        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        tmp = IMAGE_DIR / f"_{prefix}_{timestamp}_{user_id}_{i}.jpg"
        try:
            tmp.write_bytes(result)
            paths.append(tmp)
        except Exception as e:
            logger.error(f"写入临时文件失败: {e}")
    return paths


def _cleanup_tmp(paths: list) -> None:
    """清理临时文件"""
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.error(f"清理临时文件失败 ({p}): {e}")


# ── 群聊引用解图 ──


def _group_reply_rule(event: MessageEvent) -> bool:
    """群聊 @bot + 引用消息 + 「解图」"""
    if event.message_type != "group":
        return False
    if event.reply is None:
        return False
    return event.get_plaintext().strip() in ("解图", "decode")


group_decode = on_message(rule=to_me() & _group_reply_rule, priority=0, block=True)


@group_decode.handle()
async def handle_group_decode(bot: Bot, event: MessageEvent):
    async with _get_lock(event.user_id):
        await _handle_group_decode_locked(bot, event)


async def _handle_group_decode_locked(bot: Bot, event: MessageEvent):
    user_id = event.user_id

    # 冷却检查（与解图插件共用）
    expires = _cd_expires.get(user_id, 0)
    if time.time() < expires:
        return  # 静默

    # 提取被引用消息中的图片
    if event.reply is None:
        return

    img_segs = [seg for seg in event.reply.message if seg.type == "image"]
    if not img_segs:
        return

    images = await _download_images(img_segs)
    if not images:
        return

    tmp_paths = await _deobfuscate_batch(images, user_id, "grpdec")
    if not tmp_paths:
        return

    cd = min(
        PUBLISH_COOLDOWN_BASE + PUBLISH_COOLDOWN_PER_IMAGE * len(tmp_paths),
        PUBLISH_COOLDOWN_MAX,
    )
    _cd_expires[user_id] = time.time() + cd

    msg = MessageSegment.text(f"🔓 群聊引用解图 ({len(tmp_paths)} 张)\n冷却 {cd} 秒后可再次使用。\n")
    for p in tmp_paths:
        msg += MessageSegment.image(file=str(p.resolve()))

    try:
        await bot.send_private_msg(user_id=user_id, message=msg)
    except Exception as e:
        logger.error(f"群聊引用解图私信发送失败: {e}")
    finally:
        _cleanup_tmp(tmp_paths)


# ── 自动解混淆（转发 publish 消息）──

async def _auto_decode(bot: Bot, event: MessageEvent):
    """私聊中检测到 IMAGE_DECODE_URL + 图片 → 即时解混淆"""
    # 冷却检查
    expires = _cd_expires.get(event.user_id, 0)
    if time.time() < expires:
        return  # 静默

    img_segs = [seg for seg in event.message if seg.type == "image"]
    if not img_segs:
        return

    images = await _download_images(img_segs)
    if not images:
        return

    tmp_paths = await _deobfuscate_batch(images, event.user_id, "autodec")
    if not tmp_paths:
        return

    cd = min(
        PUBLISH_COOLDOWN_BASE + PUBLISH_COOLDOWN_PER_IMAGE * len(tmp_paths),
        PUBLISH_COOLDOWN_MAX,
    )
    _cd_expires[event.user_id] = time.time() + cd

    msg = MessageSegment.text(f"🔓 自动解混淆 ({len(tmp_paths)} 张)\n冷却 {cd} 秒后可再次使用。\n")
    for p in tmp_paths:
        msg += MessageSegment.image(file=str(p.resolve()))

    try:
        await bot.send(event, msg)
    except Exception as e:
        logger.error(f"自动解混淆发送失败: {e}")
    finally:
        _cleanup_tmp(tmp_paths)


# ── 超时扫描 ──

async def _check_decode_timeout():
    expired = get_expired(DECODE_TYPE)
    if not expired:
        return
    try:
        bot_instance = nonebot.get_bot()
    except ValueError:
        return
    for user_id in expired:
        if should_reply(user_id, "dec_timeout"):
            try:
                await bot_instance.send_private_msg(
                    user_id=user_id,
                    message="⏰ 解混淆模式已超时，已自动退出。",
                )
            except Exception as e:
                logger.error(f"超时通知发送失败 (user={user_id}): {e}")


driver = nonebot.get_driver()


@driver.on_startup
async def _start_timeout_check():
    from services.scheduler import add_interval_job
    add_interval_job(_check_decode_timeout, seconds=SESSION_SCAN_INTERVAL, job_id="decode_timeout")
