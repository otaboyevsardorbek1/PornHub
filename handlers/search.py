
"""
Content Bot - Qidiruv handler
SQLite bazadan inline va oddiy qidiruv
"""
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineQuery, 
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command

from config import config
from database import Database
from utils.helpers import escape_html, truncate_text, sanitize_query, create_video_caption

router = Router()
db = Database(config.DATABASE_PATH)


# ============ INLINE QIDIRUV ============

@router.inline_query()
async def inline_search(inline_query: InlineQuery):
    """Inline qidiruv - SQLite bazadan"""
    query = sanitize_query(inline_query.query)
    user_id = inline_query.from_user.id

    # Foydalanuvchini tekshirish
    if not db.check_terms_agreed(user_id):
        await inline_query.answer([], 
            switch_pm_text="Avval botda ro'yxatdan o'ting",
            switch_pm_parameter="start")
        return

    # Limit tekshirish
    is_premium = db.is_premium(user_id)
    limit = config.INLINE_SEARCH_LIMIT_PREMIUM if is_premium else config.INLINE_SEARCH_LIMIT_FREE

    if not query:
        # Eng mashhur videolarni ko'rsatish
        videos = db.get_top_videos(limit=min(limit, 10))
        results = []
        for i, video in enumerate(videos):
            results.append(create_inline_result(video, i))
        await inline_query.answer(results, cache_time=300, is_personal=True)
        return

    # Qidiruv
    videos, total = db.search_videos(query, limit=limit)

    # Qidiruvni loglash
    db.log_search(user_id, query, len(videos))

    if not videos:
        await inline_query.answer([], 
            switch_pm_text=f"'{query}' bo'yicha natija yo'q",
            switch_pm_parameter="search")
        return

    results = []
    for i, video in enumerate(videos[:50]):  # Telegram limit 50
        results.append(create_inline_result(video, i))

    await inline_query.answer(results, cache_time=300, is_personal=True)


def create_inline_result(video: dict, index: int) -> InlineQueryResultArticle:
    """Inline natija yaratish"""
    title = truncate_text(video.get("title", "Nomsiz"), 60)
    platform = video.get("platform", "N/A")
    duration = video.get("duration", "")
    views = video.get("views", "")
    is_premium = video.get("is_premium", 0)

    # Description
    desc_parts = [f"📺 {platform}"]
    if duration:
        desc_parts.append(f"⏱ {duration}")
    if views:
        desc_parts.append(f"👁 {views}")
    if is_premium:
        desc_parts.append("💎 Premium")

    description = " | ".join(desc_parts)

    # Message text
    caption = create_video_caption(video)

    # Callback data
    video_id = video.get("id", "")
    platform = video.get("platform", "")
    callback_data = f"video_{platform}_{video_id}"

    # Keyboard
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Batafsil", callback_data=callback_data)],
        [InlineKeyboardButton(text="🔍 Qayta qidirish", switch_inline_query_current_chat="")]
    ])

    return InlineQueryResultArticle(
        id=f"{platform}_{video_id}_{index}",
        title=title,
        description=description,
        thumbnail_url=video.get("thumbnail", ""),
        input_message_content=InputTextMessageContent(
            message_text=caption,
            parse_mode="HTML"
        ),
        reply_markup=kb
    )


# ============ ODDIY QIDIRUV ============

@router.message(Command("search"), F.chat.type == "private")
async def search_command(message: Message):
    """/search komandasi"""
    user_id = message.from_user.id

    # Rozilik tekshiruvi
    if not db.check_terms_agreed(user_id):
        await message.answer(
            "❌ Avval botda ro'yxatdan o'ting va shartlarga rozi bo'ling.\n"
            "/start ni bosing."
        )
        return

    # So'rovni olish
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "🔍 <b>Qidirish</b>\n\n"
            "Video nomini kiriting:\n"
            "<code>/search video nomi</code>\n\n"
            "Yoki inline rejimda qidiring: @botname qidiruv"
        )
        return

    query = sanitize_query(args[1])

    # Qidiruv
    await message.answer("🔍 Qidirilmoqda...")

    videos, total = db.search_videos(query, limit=10)
    db.log_search(user_id, query, len(videos))

    if not videos:
        await message.answer(
            f"❌ <b>'{escape_html(query)}' bo'yicha natija topilmadi.</b>\n\n"
            f"Boshqa so'rov bilan urinib ko'ring."
        )
        return

    # Natijalarni ko'rsatish
    text = f"🔍 <b>'{escape_html(query)}' bo'yicha {total} ta natija:</b>\n\n"

    for i, video in enumerate(videos[:10], 1):
        title = truncate_text(video.get("title", "Nomsiz"), 50)
        platform = video.get("platform", "N/A")
        duration = video.get("duration", "")
        views = video.get("views", "")
        is_premium = video.get("is_premium", 0)

        premium_icon = "💎 " if is_premium else ""
        text += f"{i}. {premium_icon}<b>{escape_html(title)}</b>\n"
        text += f"   📺 {platform}"
        if duration:
            text += f" | ⏱ {duration}"
        if views:
            text += f" | 👁 {views}"
        text += "\n\n"

    # Pagination keyboard
    kb_buttons = []
    if total > 10:
        kb_buttons.append([InlineKeyboardButton(
            text="⬇️ Ko'proq ko'rish", 
            callback_data=f"search_more_{query}_10"
        )])

    kb_buttons.append([InlineKeyboardButton(
        text="🔍 Inline qidiruv", 
        switch_inline_query_current_chat=query
    )])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("search_more_"))
async def search_more_callback(callback: CallbackQuery):
    """Ko'proq natijalar"""
    await callback.answer()

    data = callback.data.split("_", 3)
    if len(data) < 4:
        return

    query = data[2]
    offset = int(data[3])

    videos, total = db.search_videos(query, limit=10, offset=offset)

    if not videos:
        await callback.answer("Boshqa natija yo'q", show_alert=True)
        return

    text = f"🔍 <b>'{escape_html(query)}' bo'yicha natijalar (sahifa {offset//10 + 1}):</b>\n\n"

    for i, video in enumerate(videos, offset + 1):
        title = truncate_text(video.get("title", "Nomsiz"), 50)
        platform = video.get("platform", "N/A")
        duration = video.get("duration", "")
        views = video.get("views", "")
        is_premium = video.get("is_premium", 0)

        premium_icon = "💎 " if is_premium else ""
        text += f"{i}. {premium_icon}<b>{escape_html(title)}</b>\n"
        text += f"   📺 {platform}"
        if duration:
            text += f" | ⏱ {duration}"
        if views:
            text += f" | 👁 {views}"
        text += "\n\n"

    # Pagination
    kb_buttons = []
    nav_buttons = []

    if offset >= 10:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Oldingi", 
            callback_data=f"search_more_{query}_{offset - 10}"
        ))

    if offset + 10 < total:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️ Keyingi", 
            callback_data=f"search_more_{query}_{offset + 10}"
        ))

    if nav_buttons:
        kb_buttons.append(nav_buttons)

    kb_buttons.append([InlineKeyboardButton(
        text="🏠 Bosh sahifa", callback_data="home"
    )])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await callback.message.edit_text(text, reply_markup=kb)


# ============ KATEGORIYA BO'YICHA QIDIRUV ============

@router.callback_query(F.data == "categories")
async def categories_callback(callback: CallbackQuery):
    """Kategoriyalar ro'yxati"""
    await callback.answer()

    categories = db.get_categories()

    if not categories:
        await callback.message.edit_text(
            "❌ Kategoriyalar topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
            ])
        )
        return

    # Kategoriyalarni platforma bo'yicha guruhlash
    by_platform = {}
    for cat in categories:
        pl = cat.get("platform", "N/A")
        if pl not in by_platform:
            by_platform[pl] = []
        by_platform[pl].append(cat)

    text = "📂 <b>Kategoriyalar</b>\n\n"

    buttons = []
    for platform, cats in by_platform.items():
        text += f"📺 <b>{platform.upper()}</b>\n"
        for cat in cats[:10]:  # Har bir platformadan 10 ta
            title = cat.get("title", "Nomsiz")
            video_count = cat.get("video_count", "0")
            text += f"  • {escape_html(title)} ({video_count})\n"
        text += "\n"

        # Tugmalar
        for cat in cats[:5]:
            buttons.append([InlineKeyboardButton(
                text=f"{cat.get('title', 'Nomsiz')} ({cat.get('video_count', '0')})",
                callback_data=f"cat_{cat.get('platform', '')}_{cat.get('id', '')}"
            )])

    buttons.append([InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("cat_"))
async def category_videos_callback(callback: CallbackQuery):
    """Kategoriya bo'yicha videolar"""
    await callback.answer()

    data = callback.data.split("_", 2)
    if len(data) < 3:
        return

    platform = data[1]
    cat_id = data[2]

    # Kategoriya nomini olish
    categories = db.get_categories(platform=platform)
    cat_name = "Nomsiz"
    for cat in categories:
        if str(cat.get("id")) == cat_id:
            cat_name = cat.get("title", "Nomsiz")
            break

    # Bu yerda kategoriya bo'yicha qidiruv (category maydoni bo'yicha)
    videos, total = db.search_videos("", platform=platform, category=cat_name, limit=10)

    if not videos:
        await callback.message.edit_text(
            f"❌ <b>{escape_html(cat_name)}</b> kategoriyasida video topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="categories")],
                [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
            ])
        )
        return

    text = f"📂 <b>{escape_html(cat_name)}</b> ({total} ta)\n\n"

    for i, video in enumerate(videos[:10], 1):
        title = truncate_text(video.get("title", "Nomsiz"), 50)
        duration = video.get("duration", "")
        views = video.get("views", "")
        is_premium = video.get("is_premium", 0)

        premium_icon = "💎 " if is_premium else ""
        text += f"{i}. {premium_icon}<b>{escape_html(title)}</b>\n"
        if duration:
            text += f"   ⏱ {duration}"
        if views:
            text += f" | 👁 {views}"
        text += "\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="categories")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# ============ TOP VIDEOLAR ============

@router.callback_query(F.data == "top_videos")
async def top_videos_callback(callback: CallbackQuery):
    """Top videolar"""
    await callback.answer()

    videos = db.get_top_videos(limit=20)

    if not videos:
        await callback.message.edit_text(
            "❌ Video topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
            ])
        )
        return

    text = "⭐ <b>Eng mashhur videolar</b>\n\n"

    for i, video in enumerate(videos[:20], 1):
        title = truncate_text(video.get("title", "Nomsiz"), 50)
        platform = video.get("platform", "N/A")
        views = video.get("views", "")
        rating = video.get("rating", "")
        is_premium = video.get("is_premium", 0)

        premium_icon = "💎 " if is_premium else ""
        text += f"{i}. {premium_icon}<b>{escape_html(title)}</b>\n"
        text += f"   📺 {platform}"
        if views:
            text += f" | 👁 {views}"
        if rating:
            text += f" | ⭐ {rating}"
        text += "\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Qidirish", switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


@router.message(Command("top"), F.chat.type == "private")
async def top_command(message: Message):
    """/top komandasi"""
    videos = db.get_top_videos(limit=20)

    if not videos:
        await message.answer("❌ Video topilmadi.")
        return

    text = "⭐ <b>Eng mashhur videolar</b>\n\n"

    for i, video in enumerate(videos[:20], 1):
        title = truncate_text(video.get("title", "Nomsiz"), 50)
        platform = video.get("platform", "N/A")
        views = video.get("views", "")
        is_premium = video.get("is_premium", 0)

        premium_icon = "💎 " if is_premium else ""
        text += f"{i}. {premium_icon}<b>{escape_html(title)}</b>\n"
        text += f"   📺 {platform}"
        if views:
            text += f" | 👁 {views}"
        text += "\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Qidirish", switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await message.answer(text, reply_markup=kb)
