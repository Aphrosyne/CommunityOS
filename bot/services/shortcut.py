"""
指令快捷映射 — 全句 → 完整指令，支持分群配置

配置文件：bot/config/shortcuts.json（gitignored）

格式：
{
  "*": {"key": "value", ...},          # 所有群默认
  "群号": {"key": "value", ...}        # 群专属（覆盖默认）
}
"""
import json
from pathlib import Path

from services.logger import get_logger

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "shortcuts.json"
_map: dict[str, dict[str, str]] = {}


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


def match(text: str, group_id: int = 0) -> str | None:
    """全句匹配。先查群专属映射，再查全局 * 映射"""
    gid = str(group_id)
    if gid in _map and not gid.startswith("*"):
        val = _map[gid].get(text)
        if val is not None:
            return val
    # 全局默认
    global_map = _map.get("*", {})
    return global_map.get(text)


def list(group_id: int = 0) -> dict[str, str]:
    """返回该群的映射（群专属 + 全局合并）"""
    result = dict(_map.get("*", {}))
    gid = str(group_id)
    if gid in _map and not gid.startswith("*"):
        result.update(_map[gid])
    return result


# 模块加载时读取
reload()
