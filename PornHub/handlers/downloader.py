# handlers/downloader.py - TO'LIQ TUZATILGAN
import os
import asyncio
import json
import random
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
import yt_dlp
import sqlite3
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, 
    InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, Location
)
from aiogram.filters import BaseFilter, Command
from config import config

router = Router()

# Global o'zgaruvchilar
active_downloads = []
user_downloads = defaultdict(int)
download_history = deque(maxlen=1000)

# User Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

class UrlFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return "pornhub" in message.text.lower()

url_filter = UrlFilter()

def init_dataset():
    conn = sqlite3.connect('dataset.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS videos 
                 (id INTEGER PRIMARY KEY, title TEXT, url TEXT, quality TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (user_id INTEGER, downloads INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_recommendation():
    conn = sqlite3.connect('dataset.db')
    c = conn.cursor()
    c.execute("SELECT title, url FROM videos ORDER BY RANDOM() LIMIT 3")
    recs = c.fetchall()
    conn.close()
    return recs

def humanbytes(size):
    power = 2**10
    n = 0
    while size > power:
        size /= power
        n += 1
    units = ['B', 'KiB', 'MiB', 'GiB']
    try:
        return f"{size:.1f} {units[n]}"
    except:
        return "N/A"

def get_safe_ydl_opts(quality="720"):
    return {
        'user_agent': random.choice(USER_AGENTS),
        'referer': 'https://www.pornhub.com/',
        'ratelimit': '400K',
        'sleep_interval': 2,
        'retries': 3,
        'format': f'best[height<={quality}][ext=mp4]',
        'merge_output_format': 'mp4',
        'outtmpl': 'downloads/%(title)50s.%(ext)s'
    }

async def anti_ban_delay():
    await asyncio.sleep(random.uniform(2, 4))

async def check_user_limit(user_id):
    if user_downloads[user_id] >= 8:
        return False
    user_downloads[user_id] += 1
    return True

@router.message(Command("start"))
async def start_cmd(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Pornhub URL", switch_inline_query_current_chat="test")
        ],
        [
            InlineKeyboardButton(text="⭐ Tavsiyalar", callback_data="recommend"),
            InlineKeyboardButton(text="📊 Stat", callback_data="stats")
        ]
    ])
    await message.reply("🚀 PornHub Downloader Bot\n\nPornhub URL yuboring!", reply_markup=kb)

@router.message(url_filter)
async def handle_pornhub_url(message: Message):
    if not await check_user_limit(message.from_user.id):
        await message.reply("❌ Kunlik limit (8 ta) tugadi!")
        return
    
    # ✅ TO'G'RI InlineKeyboardButton sintaksisi
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 360p", callback_data=f"dl_360_{message.text}")],
        [InlineKeyboardButton(text="🖥 720p", callback_data=f"dl_720_{message.text}")],
        [InlineKeyboardButton(text="📺 1080p", callback_data=f"dl_1080_{message.text}")]
    ])
    await message.reply("🎬 Sifatni tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("dl_"))
async def safe_download(callback: CallbackQuery):
    data = callback.data.split("_", 2)
    if len(data) < 3:
        await callback.answer("❌ Noto'g'ri URL")
        return
        
    quality, url = data[1], data[2]
    user_id = callback.from_user.id
    
    if user_id in active_downloads:
        await callback.answer("⏳ Yuklash bor!")
        return
    
    active_downloads.append(user_id)
    msg = await callback.message.edit_text("🛡️ Anti-ban tekshiruvi...")
    
    await anti_ban_delay()
    msg = await msg.edit_text("📥 Yuklanmoqda...")
    
    try:
        os.makedirs("downloads", exist_ok=True)
        ydl_opts = get_safe_ydl_opts(quality)
        
        def download_func():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_func)
        
        # Video topish
        files = [f for f in os.listdir('downloads') if f.endswith('.mp4')]
        if not files:
            await msg.edit_text("❌ Video topilmadi!")
            return
        
        file_path = os.path.join('downloads', max(files, key=os.path.getctime))
        file_size = os.path.getsize(file_path)
        
        if file_size > 50 * 1024 * 1024:
            await msg.edit_text("❌ 50MB+ cheklov!")
            os.remove(file_path)
            return
        
        # ✅ VIDEO YUBORISH
        kb_success = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Yana", callback_data="recommend"),
                InlineKeyboardButton(text="📊 Stat", callback_data="stats")
            ]
        ])
        
        with open(file_path, 'rb') as video_file:
            await callback.message.reply_video(
                video=video_file,
                caption=f"✅ {quality}p yuklandi!\n📊 {humanbytes(file_size)}",
                reply_markup=kb_success,
                width=1280,
                height=720
            )
        
        download_history.append({"user": user_id, "quality": quality, "size": file_size})
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"❌ Xato: {str(e)[:80]}")
    finally:
        if user_id in active_downloads:
            active_downloads.remove(user_id)
        # Tozalash
        for f in os.listdir('downloads'):
            try:
                os.remove(os.path.join('downloads', f))
            except:
                pass

def progress_hook(d, message_obj):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '?')
        speed = d.get('_speed_str', '?')
        eta = d.get('_eta_str', '?')
        text = f"📥 Yuklanmoqda\n⚡ {speed} | {percent} | ⏳ {eta}"
        try:
            asyncio.create_task(message_obj.edit_text(text))
        except:
            pass

@router.callback_query(F.data == "recommend")
async def recommendation(callback: CallbackQuery):
    recs = get_recommendation()
    if not recs:
        await callback.answer("📭 Tavsiya yo'q")
        return
    
    # ✅ TO'G'RI list comprehension
    buttons = []
    for rec in recs:
        buttons.append([InlineKeyboardButton(text=rec[0][:30], url=rec[1])])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("⭐ Tavsiyalar:", reply_markup=kb)

@router.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    downloads = user_downloads[callback.from_user.id]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Reset", callback_data="reset_limit")]
    ])
    await callback.message.edit_text(
        f"📊 Stat:\n"
        f"📥 Bugun: {downloads}/8\n"
        f"🔥 Faol: {len(active_downloads)}",
        reply_markup=kb
    )

@router.callback_query(F.data == "reset_limit")
async def reset_limit(callback: CallbackQuery):
    user_downloads[callback.from_user.id] = 0
    await callback.answer("✅ Limit yangilandi!")

# ✅ XATOSIZ INLINE QUERY
@router.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.strip()
    if not query:
        await inline_query.answer([])
        return
    
    # ✅ TO'G'RI InlineKeyboardButton sintaksisi
    search_url = f"https://www.pornhub.com/video/search?search={query}"
    kb_inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Qidirish", url=search_url)]
    ])
    
    results = [
        InlineQueryResultArticle(
            id="search_1",
            title=f"🔍 Pornhub: {query}",
            description=f"'{query}' qidirish",
            input_message_content=InputTextMessageContent(message_text=search_url),
            reply_markup=kb_inline
        )
    ]
    await inline_query.answer(results, cache_time=300)

@router.message(Command("dataset"))
async def dataset_cmd(message: Message):
    await message.reply(f"💾 Dataset: {len(download_history)} yuklama")

# Inicializatsiya
try:
    init_dataset()
    os.makedirs("downloads", exist_ok=True)
    print("🚀 Downloader 100% TAYYOR!")
except Exception as e:
    print(f"❌ Init xatosi: {e}")
