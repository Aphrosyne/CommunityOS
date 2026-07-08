"""
好友申请自动处理 - 验证答案匹配则同意
"""
from nonebot import on_request
from nonebot.adapters.onebot.v11 import Bot, FriendRequestEvent

from services.runtime_config import get as get_runtime_config
from services.logger import get_logger

logger = get_logger("relationship")

friend_req = on_request(priority=5)


@friend_req.handle()
async def handle_friend_request(bot: Bot, event: FriendRequestEvent):
    verify_answer = get_runtime_config("FRIEND_VERIFY_ANSWER", "")
    if not verify_answer:
        return

    user_id = event.user_id
    # 提取答案：取最后一行，去掉「回答:」前缀
    raw = event.comment.strip()
    last_line = raw.split("\n")[-1].strip() if raw else ""
    answer = last_line.removeprefix("回答:").removeprefix("答案:").strip()
    flag = event.flag

    if answer == verify_answer:
        await bot.set_friend_add_request(flag=flag, approve=True)
        logger.info(f"好友申请 同意: user={user_id}")
    else:
        logger.info(f"好友申请 忽略: user={user_id} answer={answer}")
