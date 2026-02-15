# handlers/downloader.py
import os
import asyncio
import youtube_dl
from pornhub_api import PornhubApi
from pornhub_api.backends.aiohttp import AioHttpBackend
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from config import config

router = Router()

def url_filter(message: Message):
    return "www.pornhub" in message.text or "pornhub" in message.text.lower()

@router.message(url_filter, F.chat.type == "private")
async def handle_pornhub_url(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Download", callback_data=f"d_{message.text}")],
        [InlineKeyboardButton(text="Watch in web", url=message.text)]
    ])
    
    await message.reply("Tap the button to continue action!", reply_markup=kb)

@router.callback_query(F.data.startswith("d_"))
async def download_video(callback: CallbackQuery):
    url = callback.data.split("_", 1)[1]
    await callback.message.edit("Downloading...")
    
    # Simple download logic (implement your download function here)
    await callback.answer("Download started!")
    await callback.message.edit("Video download completed! Check your downloads folder.")
