"""
发布插件 - 多步交互批量图片投稿

流程：
    用户发「发布」→ 进入发布模式 → 发送图片 → 发「完成」→ 批量混淆发布
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
    IMAGE_SUBMIT_GROUP,
    IMAGE_DECODE_URL,
    PUBLISH_COOLDOWN_BASE,
    PUBLISH_COOLDOWN_MAX,
    PUBLISH_COOLDOWN_PER_IMAGE,
    PUBLISH_MAX_IMAGES,
    PUBLISH_TIMEOUT,
    SESSION_SCAN_INTERVAL,
)
from services.image_obfuscator import obfuscate
from services.session import (
    Session, create, get_active, append_data, complete, cancel, get_expired,
)
from services.throttle import should_reply
from services.logger import get_logger

logger = get_logger("image")

PUBLISH_TYPE = "publish"

_user_locks: dict[int, asyncio.Lock] = {}


def _get_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = _user_locks[user_id] = asyncio.Lock()
    return lock


async def _reply(bot: Bot, event: MessageEvent, msg: str, reply_type: str) -> None:
    """带节流的回复"""
    if should_reply(event.user_id, reply_type):
        await bot.send(event, msg)

# 发布冷却: {user_id: cooldown_expires_at}
_cd_expires: dict[int, float] = {}


# ── 命令入口 ──


async def handle_publish(bot: Bot, event: MessageEvent):
    if IMAGE_SUBMIT_GROUP == 0:
        await _reply(bot, event, "发布功能尚未配置，请联系管理员。", "publish_config")
        return

    if event.message_type != "private":
        await _reply(bot, event, "请私聊发送「发布」进行图片投稿。", "publish_private_only")
        return

    # 冷却检查
    expires = _cd_expires.get(event.user_id, 0)
    if time.time() < expires:
        remaining = int(expires - time.time())
        await _reply(bot, event, f"发布冷却中，请等待 {remaining} 秒后再试。", "publish_cooldown")
        return

    session = create(
        event.user_id,
        PUBLISH_TYPE,
        timeout=PUBLISH_TIMEOUT,
        initial_data={"images": []},
    )
    logger.info(f"[发布] 用户 {event.user_id} 进入发布模式")
    await _reply(
        bot, event,
        f"📷 已进入发布模式（最多 {PUBLISH_MAX_IMAGES} 张）。\n"
        "请发送图片。发送「完成」开始发布，发送「取消」退出。",
        "publish_start",
    )


register(
    "publish", handle_publish,
    description="批量图片投稿",
    aliases=["发布"],
    help_text="📷 发布 (publish | 发布)\n"
    "私聊发送「发布」→ 进入发布模式 → 发送图片 → 发送「完成」开始发布。\n"
    "最多 10 张，3 分钟超时，发布后动态冷却。\n"
    "所有图片混淆后合并为一条消息发到指定群。",
)

# ── 会话消息拦截 ──


def _publish_rule(event: MessageEvent) -> bool:
    """仅在私聊匹配：session 激活时所有消息，未激活时仅「发布」/「publish」"""
    if event.message_type != "private":
        return False
    if get_active(event.user_id, PUBLISH_TYPE):
        return True
    return event.get_plaintext().strip() in ("发布", "publish")


publish_session = on_message(rule=_publish_rule, priority=0, block=True)


@publish_session.handle()
async def handle_session(bot: Bot, event: MessageEvent):
    async with _get_lock(event.user_id):
        await _handle_session_locked(bot, event)


async def _handle_session_locked(bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    session = get_active(event.user_id, PUBLISH_TYPE)

    # 未激活 → 必然是「发布」/「publish」（由 rule 保证），创建会话
    if session is None:
        await handle_publish(bot, event)
        return

    # 取消
    if msg == "取消":
        cancel(session)
        logger.info(f"[发布] 用户 {event.user_id} 取消发布")
        await _reply(bot, event, "已取消发布。", "publish_cancel")
        return

    # 完成
    if msg == "完成":
        # 取出并清空图片列表（防止并发「完成」重复处理）
        images = session.data.get("images", [])
        session.data["images"] = []  # 清空但保留 key，防止并发收图丢失引用
        if not images:
            await _reply(bot, event, "尚未收到任何图片，请先发送图片。", "publish_empty")
            return

        await _reply(bot, event, f"开始处理 {len(images)} 张图片……", "publish_process")

        # 混淆 + 写入临时文件
        tmp_paths = []
        for i, image_data in enumerate(images):
            try:
                obfuscated_data = await obfuscate(image_data)
            except Exception as e:
                logger.error(f"混淆失败: {e}")
                continue

            timestamp = time.strftime("%Y-%m-%d_%H%M%S")
            tmp_path = IMAGE_DIR / f"_publish_{timestamp}_{event.user_id}_{i}.jpg"
            try:
                tmp_path.write_bytes(obfuscated_data)
                tmp_paths.append(tmp_path)
            except Exception as e:
                logger.error(f"写入临时文件失败: {e}")

        if not tmp_paths:
            await _reply(bot, event, "所有图片处理失败，请稍后重试。", "publish_failed")
            complete(session)
            return

        # 合并为一条群消息
        sent = False
        try:
            msg = MessageSegment.at(event.user_id)
            for p in tmp_paths:
                msg += MessageSegment.image(file=str(p.resolve()))
            msg += MessageSegment.text(f" {IMAGE_DECODE_URL}")

            await bot.send_group_msg(
                group_id=IMAGE_SUBMIT_GROUP,
                message=msg,
            )
            sent = True
        except Exception as e:
            logger.error(f"发布到群失败: {e}")
        finally:
            for p in tmp_paths:
                try:
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    logger.error(f"清理临时文件失败 ({p}): {e}")

        if not sent:
            await _reply(bot, event, "发布失败，请稍后重试。", "publish_failed")
            return

        complete(session)

        # 动态冷却：cooldown = min(base + per_image * count, max)
        cd = min(PUBLISH_COOLDOWN_BASE + PUBLISH_COOLDOWN_PER_IMAGE * len(tmp_paths), PUBLISH_COOLDOWN_MAX)
        _cd_expires[event.user_id] = time.time() + cd

        logger.info(f"[发布] 用户 {event.user_id} 完成 {len(tmp_paths)} 张，冷却 {cd}s")
        await _reply(bot, event, f"✓ 已发布 {len(tmp_paths)} 张图片。\n冷却 {cd} 秒后可再次发布。", "publish_done")
        return

    # 收集图片
    img_segs = [seg for seg in event.message if seg.type == "image"]
    if img_segs:
        images = session.data.setdefault("images", [])
        current = len(images)

        for img_seg in img_segs:
            # 上限检查
            if current >= PUBLISH_MAX_IMAGES:
                await _reply(bot, event, f"已达到上限 {PUBLISH_MAX_IMAGES} 张，发送「完成」开始发布。", "publish_limit")
                return

            url = img_seg.data.get("url", "")
            if not url:
                continue

            # 下载
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    image_data = resp.content
            except Exception as e:
                logger.error(f"下载图片失败: {e}")
                await _reply(bot, event, "图片下载失败，跳过该张。", "publish_error")
                continue

            # GIF 过滤
            fmt = PILImage.open(io.BytesIO(image_data)).format
            if fmt == "GIF":
                await _reply(bot, event, "暂不支持 GIF，已跳过。", "publish_gif")
                continue

            images.append(image_data)
            current += 1

        count = len(images)
        logger.info(f"[发布] 用户 {event.user_id} 已接收 {count} 张")
        await _reply(bot, event, f"已接收 {count} 张图片。", "publish_count")
        return

    # 其他文本：提示
    await _reply(
        bot, event,
        "发送图片进行投稿，发送「完成」开始发布，发送「取消」退出。",
        "publish_prompt",
    )


# ── 超时扫描 ──

async def _check_publish_timeout():
    """定时检查超时的发布会话，通知用户"""
    expired = get_expired(PUBLISH_TYPE)
    if not expired:
        return
    try:
        bot_instance = nonebot.get_bot()
    except ValueError:
        return  # bot 尚未连接，下次扫描再通知
    for user_id in expired:
        if should_reply(user_id, "publish_timeout"):
            try:
                logger.info(f"[发布] 用户 {user_id} 超时退出")
                await bot_instance.send_private_msg(
                    user_id=user_id,
                    message="⏰ 发布模式已超时，已自动退出。",
                )
            except Exception as e:
                logger.error(f"超时通知发送失败 (user={user_id}): {e}")

# 启动时注册定时检查（每 10 秒扫描一次）
driver = nonebot.get_driver()

@driver.on_startup
async def _start_timeout_check():
    from services.scheduler import add_interval_job
    add_interval_job(_check_publish_timeout, seconds=SESSION_SCAN_INTERVAL, job_id="publish_timeout")
