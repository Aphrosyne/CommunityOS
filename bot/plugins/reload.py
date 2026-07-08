"""
重载指令 - 热更新配置文件

支持热更新的配置文件：
- runtime.json：运行时配置（GREETING_REPLY、IMAGE_DECODE_URL 等）
- keywords.json：违禁词列表
- shortcuts.json：快捷映射
"""
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from services.command import register
from services.logger import get_logger
from services import runtime_config
from services import message_rule
from services import shortcut

logger = get_logger("system")


async def handle_reload(bot: Bot, event: MessageEvent):
    lines = ["配置重载完成："]

    # 1. runtime.json
    success, marker, err = runtime_config.reload()
    if success:
        lines.append(f"✓ runtime.json（marker: {marker}）")
    else:
        lines.append(f"✗ runtime.json（{err}）")

    # 2. keywords.json
    success, err = message_rule.reload_keywords()
    if success:
        lines.append("✓ keywords.json")
    else:
        lines.append(f"✗ keywords.json（{err}）")

    # 3. shortcuts.json
    success, err = shortcut.reload()
    if success:
        lines.append("✓ shortcuts.json")
    else:
        lines.append(f"✗ shortcuts.json（{err}）")

    await bot.send(event, "\n".join(lines))


register(
    "reload", handle_reload,
    description="重载配置",
    aliases=["重载"],
    permission=2,
    cooldown_level=2,
    hidden=True,
    accepts_args=False,
)
