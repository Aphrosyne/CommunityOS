"""
群成员查询服务 - 带缓存的成员判断

用于加群审核：判断用户是否在中转群。
缓存 TTL 5 分钟，过期后自动刷新。
"""
import time

from nonebot.adapters.onebot.v11 import Bot

from services.logger import get_logger

logger = get_logger("group_join")

# 缓存：group_id -> (缓存时间戳, 成员user_id集合)
_cache: dict[int, tuple[float, set[int]]] = {}

# 缓存 TTL（秒）
TTL_SECONDS = 300  # 5 分钟


async def is_member(
    bot: Bot, group_id: int, user_id: int, force_refresh: bool = False
) -> bool:
    """判断用户是否在指定群（带缓存）

    缓存过期时自动刷新。force_refresh=True 时强制刷新（供测试指令使用）。
    """
    now = time.time()

    # 缓存命中且未过期（且非强制刷新）
    if not force_refresh and group_id in _cache:
        cached_at, members = _cache[group_id]
        if now - cached_at < TTL_SECONDS:
            return user_id in members

    # 缓存过期/不存在/强制刷新，刷新后判断
    await _refresh(bot, group_id)
    _, members = _cache.get(group_id, (0, set()))
    return user_id in members


async def _refresh(bot: Bot, group_id: int) -> None:
    """刷新指定群的成员缓存"""
    try:
        member_list = await bot.get_group_member_list(group_id=group_id)
        members = {m["user_id"] for m in member_list}
        _cache[group_id] = (time.time(), members)
        logger.debug(f"群成员缓存已刷新: group={group_id} count={len(members)}")
    except Exception as e:
        logger.error(f"刷新群成员缓存失败 group={group_id}: {e}")
        # 失败时写入空集合+当前时间，避免反复重试
        _cache[group_id] = (time.time(), set())


def clear_cache() -> None:
    """清空所有缓存

    供 reload 指令调用：配置变更后清空旧缓存，下次查询时自动重建。
    """
    _cache.clear()
    logger.info("群成员缓存已清空")


def get_cache_info(group_id: int) -> dict:
    """获取指定群的缓存信息（供测试指令展示）

    Returns:
        {"cached": bool, "member_count": int}
    """
    if group_id not in _cache:
        return {"cached": False, "member_count": 0}
    _, members = _cache[group_id]
    return {"cached": True, "member_count": len(members)}
