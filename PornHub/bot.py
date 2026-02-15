# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config

logger = logging.getLogger(__name__)

class PornHubBot:
    def __init__(self):
        self.bot = Bot(token=config.TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.start_time = None
    
    async def start(self):
        self.start_time = asyncio.get_event_loop().time()
        logger.info("PornHub bot started!")
        
        start_message = (
            "<b>PornHub started!</b>\n\n"
        )
        try:
            await self.bot.send_message(config.LOG_CHAT, start_message)
        except Exception as e:
            logger.warning(f"Unable to send message to log_chat: {e}")
    
    async def stop(self):
        await self.bot.session.close()
        logger.warning("PornHub bot stopped!")
    
    async def run(self):
        try:
            await self.start()
            await self.dp.start_polling(self.bot)
        finally:
            await self.stop()
