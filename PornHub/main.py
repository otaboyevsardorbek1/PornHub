# main.py
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import pytz
from datetime import datetime

from bot import PornHubBot
from handlers import start, admin, utils, downloader

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    handlers=[
        RotatingFileHandler("xxx_logs.txt", maxBytes=50*1024*1024, backupCount=10),
        logging.StreamHandler(),
    ]
)

async def main():
    bot = PornHubBot()
    
    # Include all routers
    bot.dp.include_router(start.router)
    bot.dp.include_router(admin.router)
    bot.dp.include_router(utils.router)
    bot.dp.include_router(downloader.router)
    
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
