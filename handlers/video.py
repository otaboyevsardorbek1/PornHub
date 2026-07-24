
"""
Content Bot - Video handler
Video ma'lumotlarini ko'rsatish, yuklab olish limiti, to'lov integratsiyasi
"""
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import config
from database import Database
from utils.helpers import escape_html, truncate_text, create_video_caption

router = Router()
db = Database(config.DATABASE_PATH)


@router.callback_query(F.data.startswith("video_"))
async def video_detail_callback(callback: CallbackQuery):
    """Video batafsil ma'lumot"""
    await callback.answer()

    data = callback.data.split("_", 2)
    if len(data) < 3:
        return

    platform = data[1]
    video_id = data[2]

    video = db.get_video_by_id(video_id, platform)

    if not video:
        await callback.answer("❌ Video topilmadi!", show_alert=True)
        return

    user_id = callback.from_user.id
    is_premium = db.is_premium(user_id)
    video_premium = video.get("is_premium", 0)

    # Premium tekshiruvi
    if video_premium and not is_premium:
        text = create_video_caption(video, show_details=True)
        text += "\n\n💎 <b>Bu premium kontent!</b>\n"
        text += "Premium obuna sotib olish uchun quyidagi tugmani bosing."

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
            [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
        ])

        await callback.message.edit_text(text, reply_markup=kb)
        return

    # Limit tekshiruvi
    can_download, remaining, limit = db.check_download_limit(
        user_id,
        config.DAILY_DOWNLOAD_LIMIT_FREE,
        config.DAILY_DOWNLOAD_LIMIT_PREMIUM
    )

    if not can_download:
        text = create_video_caption(video, show_details=True)
        text += f"\n\n❌ <b>Bugungi yuklab olish limiti tugadi!</b>\n"
        text += f"Limit: {limit} ta/kun\n"
        text += f"💎 Premium obuna bilan cheksiz yuklab olish"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
            [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
        ])

        await callback.message.edit_text(text, reply_markup=kb)
        return

    # Video ma'lumotlarini ko'rsatish
    caption = create_video_caption(video, show_details=True)
    caption += f"\n\n📥 <b>Yuklab olish:</b> {remaining}/{limit} qoldi"

    # URL ni olish
    video_urls = video.get("video_urls", [])
    download_links = video.get("download_links", [])
    url = video.get("url", "")

    buttons = []

    # Asosiy URL
    if url:
        buttons.append([InlineKeyboardButton(text="🌐 Webda ko'rish", url=url)])

    # Video URL lar
    for i, vurl in enumerate(video_urls[:3]):
        if isinstance(vurl, dict):
            quality = vurl.get("quality", f"Link {i+1}")
            vurl_link = vurl.get("url", "")
            if vurl_link:
                buttons.append([InlineKeyboardButton(
                    text=f"📥 {quality}", 
                    url=vurl_link
                )])
        elif isinstance(vurl, str) and vurl:
            buttons.append([InlineKeyboardButton(
                text=f"📥 Link {i+1}", 
                url=vurl
            )])

    # Download links
    for i, dl in enumerate(download_links[:3]):
        if isinstance(dl, dict):
            quality = dl.get("quality", f"Download {i+1}")
            dl_url = dl.get("url", "")
            if dl_url:
                buttons.append([InlineKeyboardButton(
                    text=f"⬇️ {quality}", 
                    url=dl_url
                )])

    buttons.append([InlineKeyboardButton(text="🔍 Qayta qidirish", switch_inline_query_current_chat="")])
    buttons.append([InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Yuklab olishni loglash
    db.increment_download(user_id)
    db.log_download(user_id, video_id, platform)

    # Thumbnail bilan yuborish
    thumbnail = video.get("thumbnail", "")

    try:
        if thumbnail:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=thumbnail,
                caption=caption,
                reply_markup=kb
            )
        else:
            await callback.message.edit_text(caption, reply_markup=kb)
    except Exception:
        await callback.message.edit_text(caption, reply_markup=kb)


@router.callback_query(F.data == "my_profile")
async def my_profile_callback(callback: CallbackQuery):
    """Profil callback"""
    await callback.answer()

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user:
        await callback.message.edit_text(
            "❌ Foydalanuvchi topilmadi. /start ni bosing.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
            ])
        )
        return

    is_premium = db.is_premium(user_id)
    user_stats = db.get_user_stats(user_id)

    can_download, remaining, limit = db.check_download_limit(
        user_id,
        config.DAILY_DOWNLOAD_LIMIT_FREE,
        config.DAILY_DOWNLOAD_LIMIT_PREMIUM
    )

    status = "💎 Premium" if is_premium else "🆓 Bepul"
    premium_until = user.get("premium_until", "")
    if premium_until:
        status += f" (gacha: {premium_until[:10]})"

    text = (
        f"👤 <b>Shaxsiy Profil</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Ism: {escape_html(user.get('first_name', ''))}\n"
        f"📛 Username: @{escape_html(user.get('username', 'N/A'))}\n"
        f"📊 Status: {status}\n\n"
        f"📥 Bugungi yuklab olish: {limit - remaining}/{limit}\n"
        f"🔍 Jami qidiruvlar: {user_stats.get('total_searches', 0)}\n"
        f"📥 Jami yuklab olishlar: {user_stats.get('total_downloads', 0)}\n"
        f"📅 Oylik yuklab olishlar: {user_stats.get('monthly_downloads', 0)}\n\n"
        f"📅 Ro'yxatdan o'tgan: {user.get('created_at', 'N/A')[:10]}"
    )

    # So'nggi yuklab olishlar
    recent = db.get_recent_downloads(user_id, limit=5)
    if recent:
        text += "\n\n📥 <b>So'nggi yuklab olishlar:</b>\n"
        for i, dl in enumerate(recent, 1):
            title = truncate_text(dl.get("title", "Nomsiz"), 40)
            platform = dl.get("platform", "N/A")
            date = dl.get("downloaded_at", "")[:10]
            text += f"{i}. {escape_html(title)} ({platform}) - {date}\n"

    # To'lov tarixi
    payments = db.get_user_payments(user_id, limit=3)
    if payments:
        text += "\n\n💳 <b>So'nggi to'lovlar:</b>\n"
        for i, payment in enumerate(payments, 1):
            plan = payment.get("plan", "Nomsiz")
            amount = payment.get("amount", 0)
            currency = payment.get("currency", "UZS")
            date = payment.get("created_at", "")[:10]
            text += f"{i}. {plan} - {amount:,} {currency} ({date})\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
        [InlineKeyboardButton(text="💳 To'lov tarixi", callback_data="payments_history")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "payments_history")
async def payments_history_callback(callback: CallbackQuery):
    """To'lov tarixi callback"""
    await callback.answer()

    user_id = callback.from_user.id
    payments = db.get_user_payments(user_id, limit=10)

    if not payments:
        await callback.message.edit_text(
            "📭 <b>To'lov tarixi bo'sh.</b>\n\n"
            "Premium obuna sotib olish uchun quyidagi tugmani bosing.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
                [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
            ])
        )
        return

    text = "💳 <b>To'lov tarixi</b>\n\n"

    for i, payment in enumerate(payments, 1):
        plan = payment.get("plan", "Nomsiz")
        amount = payment.get("amount", 0)
        currency = payment.get("currency", "UZS")
        status = payment.get("status", "pending")
        date = payment.get("created_at", "")[:10]
        tx_id = payment.get("transaction_id", "")[:20]

        status_icon = "✅" if status == "completed" else "❌"
        text += f"{i}. {status_icon} <b>{plan}</b>\n"
        text += f"   💰 {amount:,} {currency}\n"
        text += f"   📅 {date}\n"
        text += f"   🔑 {tx_id}...\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
