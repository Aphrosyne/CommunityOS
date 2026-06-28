"""
插件模块 - 所有业务功能以插件形式存在

插件开发示例：

    from nonebot import on_command
    from nonebot.rule import to_me
    from nonebot.adapters.onebot.v11 import MessageEvent

    help_cmd = on_command("help", rule=to_me())

    @help_cmd.handle()
    async def handle_help(event: MessageEvent):
        await help_cmd.finish("CommunityOS 帮助信息...")

目录结构：
    plugins/
    ├── welcome/      # 欢迎消息
    ├── keyword/      # 关键词监控
    ├── image/        # 图片处理
    ├── backup/       # 备份
    ├── statistics/   # 数据统计
    ├── risk/         # 风险控制
    └── scheduler/    # 定时任务
"""
