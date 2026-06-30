"""
CommunityOS Bot 入口
"""
import sys
from pathlib import Path

# 确保项目根目录在 bot/，NoneBot 会从这里找 .env
PROJECT_ROOT = Path(__file__).resolve().parent

# 将 bot/ 加入 Python 搜索路径，使 plugins/services/core 可被导入
sys.path.insert(0, str(PROJECT_ROOT))

# 显式加载 .env（NoneBot2 初始化前必须完成）
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init(
    project_root=PROJECT_ROOT,
)

driver = nonebot.get_driver()

# --- 注册平台适配器 ---
driver.register_adapter(OneBotV11Adapter)

# --- 导入 core 模块，注册启动/关闭钩子 ---
import core  # noqa: E402

# --- 加载插件 ---
# nonebot.load_plugin("plugins.greet")
nonebot.load_plugin("plugins.command_dispatcher")
nonebot.load_plugin("plugins.help")
nonebot.load_plugin("plugins.status")
nonebot.load_plugin("plugins.publish")# TODO: 后续改为 load_plugins("plugins") 自动扫描所有插件

# --- 启动时打印已加载插件 ---
@driver.on_startup
async def _list_plugins():
    plugins = nonebot.get_loaded_plugins()
    nonebot.logger.info(f"已加载插件: {[p.name for p in plugins]}")

if __name__ == "__main__":
    nonebot.run()
