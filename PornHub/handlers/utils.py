# handlers/utils.py
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime

router = Router()

@router.message(Command("ping"), F.chat.type == "private")
async def ping_handler(message: Message):
    first = datetime.now()
    sent = await message.reply("<b>pinging...</b>")
    second = datetime.now()
    
    await sent.edit_text(
        f"🏓 <b>PONG !</b>\n⏱ <code>{(second - first).microseconds / 1000}</code> ms"
    )

@router.message(Command("help"), F.chat.type == "private")
async def help_handler(message: Message, from_user):
    from config import config
    
    if from_user.id in config.SUDOERS:
        text = """
🛠 Command list:
» /start - start this bot
» /help  - showing this message
» /ping  - check bot status
» /stats - show bot statistic
» /gcast - broadcast message
        """
    else:
        text = """
🛠 Command list:
» /start - start this bot
» /help  - showing this message
» /ping  - check bot status
        """
    
    await message.reply(text)
