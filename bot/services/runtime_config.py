"""
运行时配置服务 - 支持热更新的配置项

与 services/config.py（启动时读取 .env，不变）不同，本模块管理的配置项
可在运行期通过 reload 指令重新加载，立即生效。

配置文件：bot/config/runtime.json（gitignored）
示例文件：bot/config/runtime.example.json
"""
import json
from pathlib import Path

from services.logger import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "runtime.json"
_EXAMPLE_PATH = _CONFIG_PATH.parent / "runtime.example.json"

# 运行时配置字典（reload 时整体替换）
_config: dict = {}


def _read_file(path: Path) -> dict:
    """读取 JSON 配置文件，返回字典。失败返回空字典并记日志"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"配置文件不存在: {path}")
        return {}
    except Exception as e:
        logger.error(f"加载配置文件失败 {path}: {e}")
        return {}


def reload() -> tuple[bool, str, str]:
    """重新加载 runtime.json

    Returns:
        (success, marker, error_msg)
        - success: 是否加载成功
        - marker: reload_marker 字段值（用于人工确认重载生效）
        - error_msg: 失败原因（成功时为空字符串）
    """
    global _config
    if not _CONFIG_PATH.exists():
        return False, "", f"配置文件不存在: {_CONFIG_PATH.name}"

    new_config = _read_file(_CONFIG_PATH)
    if not new_config:
        return False, "", f"配置文件为空或解析失败: {_CONFIG_PATH.name}"

    _config = new_config
    marker = _config.get("reload_marker", "")
    logger.info(f"运行时配置已重载，marker={marker}")
    return True, marker, ""


def get(key: str, default=None):
    """获取配置值。若 key 不存在返回 default"""
    return _config.get(key, default)


# 模块加载时初始化：优先读 runtime.json，不存在则读 example
if _CONFIG_PATH.exists():
    _config = _read_file(_CONFIG_PATH)
else:
    _config = _read_file(_EXAMPLE_PATH)
    if _config:
        logger.info("runtime.json 不存在，使用 runtime.example.json 作为初始配置")
