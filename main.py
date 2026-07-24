import asyncio
import logging

from bot import ContentBot
from handlers import start, search, video, admin, payments

# Logging
logger = logging.getLogger(__name__)


async def main():
    """Asosiy funksiya"""
    bot = ContentBot()

    # Routerlarni qo'shish
    bot.dp.include_router(start.router)
    bot.dp.include_router(search.router)
    bot.dp.include_router(video.router)
    bot.dp.include_router(payments.router)
    bot.dp.include_router(admin.router)

    logger.info("Barcha routerlar qo'shildi (Payments bilan)")

    # Botni ishga tushirish
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Kutilmagan xatolik: {e}", exc_info=True)
