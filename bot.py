
"""
Content Bot - Asosiy bot klassi
"""
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import Database

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    handlers=[
        RotatingFileHandler("bot_logs.txt", maxBytes=50*1024*1024, backupCount=10),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


class ContentBot:
    """Asosiy bot klassi"""

    def __init__(self):
        self.bot = Bot(token=config.BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = Database(config.DATABASE_PATH)
        self.start_time = None

    async def start(self):
        """Botni ishga tushirish"""
        self.start_time = datetime.now()
        logger.info("Content Bot ishga tushdi!")

        # Log chat ga xabar
        start_message = (
            "🚀 <b>Content Bot ishga tushdi!</b>\n\n"
            f"📅 Sana: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚙️ Versiya: 2.0.0"
        )

        try:
            if config.LOG_CHAT_ID:
                await self.bot.send_message(config.LOG_CHAT_ID, start_message, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Log chat ga xabar yuborib bo'lmadi: {e}")

    async def stop(self):
        """Botni to'xtatish"""
        await self.bot.session.close()
        self.db.close()
        logger.warning("Content Bot to'xtatildi!")

    async def run(self):
        """Botni ishga tushirish"""
        try:
            await self.start()
            await self.dp.start_polling(self.bot)
        finally:
            await self.stop()
