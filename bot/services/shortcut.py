"""
指令快捷映射 — 全句 → 完整指令

配置文件：bot/config/shortcuts.json（gitignored）

格式：{"原文": "完整指令", ...}
其中 {at} 会被替换为消息中第一个 @ 的 QQ 号。
"""
import json
from pathlib import Path

from services.logger import get_logger

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "shortcuts.json"
_map: dict[str, str] = {}


def reload() -> None:
    """重新加载映射文件"""
    global _map
    try:
        if CONFIG_PATH.exists():
            _map = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        else:
            _map = {}
    except Exception as e:
        logger.error(f"加载 shortcuts.json 失败: {e}")
        _map = {}


def match(text: str) -> str | None:
    """全句匹配，返回映射后的指令；未命中返回 None"""
    return _map.get(text)


# 模块加载时读取
reload()
