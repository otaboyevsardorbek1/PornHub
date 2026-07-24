
"""
Content Bot - Admin handler
Admin panel, statistika, broadcast, foydalanuvchi boshqaruvi, to'lov boshqaruvi
"""
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import config
from database import Database
from utils.helpers import escape_html, format_number

router = Router()
db = Database(config.DATABASE_PATH)


def is_admin(user_id: int) -> bool:
    """Admin tekshiruvi"""
    return user_id in config.ADMIN_IDS


def get_admin_kb() -> InlineKeyboardMarkup:
    """Admin panel keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 To'lovlar", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💎 Premium berish", callback_data="admin_premium")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])


# ============ ADMIN KOMANDALARI ============

@router.message(Command("admin"), F.chat.type == "private")
async def admin_command(message: Message):
    """Admin panel"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return

    text = (
        "⚙️ <b>Admin Panel</b>\n\n"
        "Quyidagi funksiyalardan foydalanishingiz mumkin:\n"
        "• 📊 Bot statistikasi\n"
        "• 👥 Foydalanuvchilar ro'yxati\n"
        "• 💰 To'lovlar va daromad\n"
        "• 📢 Xabar tarqatish\n"
        "• 💎 Premium obuna berish\n\n"
        "Kerakli tugmani bosing."
    )

    await message.answer(text, reply_markup=get_admin_kb())


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    """Admin panel callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    text = (
        "⚙️ <b>Admin Panel</b>\n\n"
        "Quyidagi funksiyalardan foydalanishingiz mumkin:\n"
        "• 📊 Bot statistikasi\n"
        "• 👥 Foydalanuvchilar ro'yxati\n"
        "• 💰 To'lovlar va daromad\n"
        "• 📢 Xabar tarqatish\n"
        "• 💎 Premium obuna berish\n\n"
        "Kerakli tugmani bosing."
    )

    await callback.message.edit_text(text, reply_markup=get_admin_kb())


# ============ STATISTIKA ============

@router.message(Command("stats"), F.chat.type == "private")
async def stats_command(message: Message):
    """Statistika komandasi"""
    if not is_admin(message.from_user.id):
        return

    stats = db.get_stats()
    pay_stats = db.get_payment_stats()

    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"📹 Videolar: <code>{format_number(stats.get('total_videos', 0))}</code>\n"
        f"📂 Kategoriyalar: <code>{format_number(stats.get('total_categories', 0))}</code>\n"
        f"📷 Fotosuratlar: <code>{format_number(stats.get('total_photos', 0))}</code>\n"
        f"👤 Modellar: <code>{format_number(stats.get('total_models', 0))}</code>\n"
        f"🏢 Studiyalar: <code>{format_number(stats.get('total_studios', 0))}</code>\n"
        f"\n"
        f"👥 Foydalanuvchilar: <code>{format_number(stats.get('total_users', 0))}</code>\n"
        f"💎 Premium: <code>{format_number(stats.get('premium_users', 0))}</code>\n"
        f"📥 Yuklab olishlar: <code>{format_number(stats.get('total_downloads', 0))}</code>\n"
        f"🔍 Qidiruvlar: <code>{format_number(stats.get('total_searches', 0))}</code>\n"
        f"\n"
        f"💰 <b>To'lovlar:</b>\n"
        f"📊 Jami: <code>{pay_stats.get('total_payments', 0)}</code>\n"
        f"✅ Muvaffaqiyatli: <code>{pay_stats.get('completed', 0)}</code>\n"
        f"⭐ Stars: <code>{pay_stats.get('total_stars', 0)}</code>\n"
        f"💳 So'm: <code>{pay_stats.get('total_uzs', 0):,}</code>\n"
        f"👥 To'lov qilganlar: <code>{pay_stats.get('unique_users', 0)}</code>\n"
        f"\n"
        f"📺 Platformalar:\n"
    )

    by_platform = stats.get("by_platform", {})
    for platform, count in by_platform.items():
        text += f"  • {platform}: <code>{format_number(count)}</code>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    """Statistika callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    stats = db.get_stats()
    pay_stats = db.get_payment_stats()

    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"📹 Videolar: <code>{format_number(stats.get('total_videos', 0))}</code>\n"
        f"📂 Kategoriyalar: <code>{format_number(stats.get('total_categories', 0))}</code>\n"
        f"📷 Fotosuratlar: <code>{format_number(stats.get('total_photos', 0))}</code>\n"
        f"👤 Modellar: <code>{format_number(stats.get('total_models', 0))}</code>\n"
        f"🏢 Studiyalar: <code>{format_number(stats.get('total_studios', 0))}</code>\n"
        f"\n"
        f"👥 Foydalanuvchilar: <code>{format_number(stats.get('total_users', 0))}</code>\n"
        f"💎 Premium: <code>{format_number(stats.get('premium_users', 0))}</code>\n"
        f"📥 Yuklab olishlar: <code>{format_number(stats.get('total_downloads', 0))}</code>\n"
        f"🔍 Qidiruvlar: <code>{format_number(stats.get('total_searches', 0))}</code>\n"
        f"\n"
        f"💰 <b>To'lovlar:</b>\n"
        f"📊 Jami: <code>{pay_stats.get('total_payments', 0)}</code>\n"
        f"✅ Muvaffaqiyatli: <code>{pay_stats.get('completed', 0)}</code>\n"
        f"⭐ Stars: <code>{pay_stats.get('total_stars', 0)}</code>\n"
        f"💳 So'm: <code>{pay_stats.get('total_uzs', 0):,}</code>\n"
        f"👥 To'lov qilganlar: <code>{pay_stats.get('unique_users', 0)}</code>\n"
        f"\n"
        f"📺 Platformalar:\n"
    )

    by_platform = stats.get("by_platform", {})
    for platform, count in by_platform.items():
        text += f"  • {platform}: <code>{format_number(count)}</code>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# ============ FOYDALANUVCHILAR ============

@router.message(Command("users"), F.chat.type == "private")
async def users_command(message: Message):
    """Foydalanuvchilar ro'yxati"""
    if not is_admin(message.from_user.id):
        return

    users = db.get_all_users(limit=20)

    if not users:
        await message.answer("❌ Foydalanuvchilar topilmadi.")
        return

    text = f"👥 <b>Foydalanuvchilar</b> (so'nggi 20 ta)\n\n"

    for i, user in enumerate(users, 1):
        uid = user.get("user_id", 0)
        name = escape_html(user.get("first_name", "Nomsiz"))
        username = user.get("username", "")
        is_premium = "💎" if user.get("is_premium", 0) else ""
        created = user.get("created_at", "")[:10]

        text += f"{i}. {is_premium} <b>{name}</b>\n"
        text += f"   🆔 <code>{uid}</code>"
        if username:
            text += f" | 📛 @{escape_html(username)}"
        text += f" | 📅 {created}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: CallbackQuery):
    """Foydalanuvchilar callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    users = db.get_all_users(limit=20)

    if not users:
        await callback.message.edit_text(
            "❌ Foydalanuvchilar topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
            ])
        )
        return

    text = f"👥 <b>Foydalanuvchilar</b> (so'nggi 20 ta)\n\n"

    for i, user in enumerate(users, 1):
        uid = user.get("user_id", 0)
        name = escape_html(user.get("first_name", "Nomsiz"))
        username = user.get("username", "")
        is_premium = "💎" if user.get("is_premium", 0) else ""
        created = user.get("created_at", "")[:10]

        text += f"{i}. {is_premium} <b>{name}</b>\n"
        text += f"   🆔 <code>{uid}</code>"
        if username:
            text += f" | 📛 @{escape_html(username)}"
        text += f" | 📅 {created}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# ============ TO'LOVLAR BOSHQARUVI ============

@router.callback_query(F.data == "admin_payments")
async def admin_payments_callback(callback: CallbackQuery):
    """To'lovlar boshqaruvi"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    pay_stats = db.get_payment_stats()

    text = (
        "💰 <b>To'lovlar Boshqaruvi</b>\n\n"
        f"📊 Jami to'lovlar: <code>{pay_stats.get('total_payments', 0)}</code>\n"
        f"✅ Muvaffaqiyatli: <code>{pay_stats.get('completed', 0)}</code>\n"
        f"❌ Bekor qilingan: <code>{pay_stats.get('cancelled', 0)}</code>\n"
        f"⭐ Stars daromad: <code>{pay_stats.get('total_stars', 0)}</code>\n"
        f"💳 So'm daromad: <code>{pay_stats.get('total_uzs', 0):,}</code>\n"
        f"👥 To'lov qilganlar: <code>{pay_stats.get('unique_users', 0)}</code>\n\n"
        f"📅 Oxirgi 7 kun: <code>{pay_stats.get('last_7_days', 0)}</code> ta\n"
        f"📅 Oxirgi 30 kun: <code>{pay_stats.get('last_30_days', 0)}</code> ta"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Batafsil statistika", callback_data="paystats_detail")],
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "paystats_detail")
async def paystats_detail_callback(callback: CallbackQuery):
    """Batafsil to'lov statistikasi"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    pay_stats = db.get_payment_stats()

    text = (
        "📊 <b>Batafsil To'lov Statistikasi</b>\n\n"
        f"💰 <b>Umumiy:</b>\n"
        f"  📊 Jami: <code>{pay_stats.get('total_payments', 0)}</code>\n"
        f"  ✅ Muvaffaqiyatli: <code>{pay_stats.get('completed', 0)}</code>\n"
        f"  ❌ Bekor: <code>{pay_stats.get('cancelled', 0)}</code>\n\n"
        f"💰 <b>Daromad:</b>\n"
        f"  ⭐ Stars: <code>{pay_stats.get('total_stars', 0)}</code>\n"
        f"  💳 So'm: <code>{pay_stats.get('total_uzs', 0):,}</code>\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"  👤 To'lov qilganlar: <code>{pay_stats.get('unique_users', 0)}</code>\n\n"
        f"📅 <b>Vaqt bo'yicha:</b>\n"
        f"  📆 Oxirgi 7 kun: <code>{pay_stats.get('last_7_days', 0)}</code>\n"
        f"  📆 Oxirgi 30 kun: <code>{pay_stats.get('last_30_days', 0)}</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="paystats_detail")],
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# ============ BROADCAST ============

@router.message(Command("broadcast"), F.chat.type == "private")
async def broadcast_command(message: Message):
    """Xabar tarqatish"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "📢 <b>Xabar tarqatish</b>\n\n"
        "Xabar yuborish uchun reply qiling:\n"
        "1. Xabarni yozing\n"
        "2. /broadcast komandasiga reply qiling\n\n"
        "Yoki xabarni yozib, /broadcast komandasiga reply qiling."
    )


@router.message(Command("gcast"), F.chat.type == "private")
async def gcast_command(message: Message):
    """Global broadcast"""
    if not is_admin(message.from_user.id):
        return

    if not message.reply_to_message:
        await message.answer("❌ Reply qilingan xabar yo'q!")
        return

    users = db.get_all_users(limit=10000)
    total = len(users)

    if total == 0:
        await message.answer("❌ Foydalanuvchilar topilmadi.")
        return

    status_msg = await message.answer(f"📢 Xabar yuborilmoqda... 0/{total}")

    success = 0
    failed = 0

    for i, user in enumerate(users):
        try:
            await message.reply_to_message.copy(user["user_id"])
            success += 1
        except Exception:
            failed += 1

        # Har 50 ta foydalanuvchidan keyin status yangilash
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 Xabar yuborilmoqda... {i+1}/{total}\n"
                    f"✅ Muvaffaqiyatli: {success}\n"
                    f"❌ Xato: {failed}"
                )
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"📊 Jami: {total}\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Xato: {failed}"
    )


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery):
    """Broadcast callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    text = (
        "📢 <b>Xabar tarqatish</b>\n\n"
        "Xabar yuborish uchun:\n"
        "1. Xabarni yozing\n"
        "2. /gcast komandasiga reply qiling\n\n"
        "Yoki /broadcast komandasini ishlating."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# ============ PREMIUM BERISH ============

@router.message(Command("addpremium"), F.chat.type == "private")
async def addpremium_command(message: Message):
    """Premium berish"""
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "<code>/addpremium user_id kunlar</code>\n\n"
            "Misol: <code>/addpremium 123456789 30</code>"
        )
        return

    try:
        user_id = int(args[1])
        days = int(args[2])
    except ValueError:
        await message.answer("❌ Noto'g'ri ID yoki kunlar soni!")
        return

    if db.set_premium(user_id, days):
        # Foydalanuvchiga xabar
        try:
            await message.bot.send_message(
                user_id,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Sizga <b>{days} kunlik</b> premium obuna berildi!\n\n"
                f"💎 Endi siz barcha premium imkoniyatlardan foydalanishingiz mumkin."
            )
        except Exception:
            pass

        await message.answer(
            f"✅ <b>Premium berildi!</b>\n\n"
            f"👤 Foydalanuvchi: <code>{user_id}</code>\n"
            f"📅 Kunlar: <code>{days}</code>"
        )
    else:
        await message.answer("❌ Premium berishda xatolik!")


@router.callback_query(F.data == "admin_premium")
async def admin_premium_callback(callback: CallbackQuery):
    """Premium berish callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    text = (
        "💎 <b>Premium berish</b>\n\n"
        "Premium berish uchun:\n"
        "<code>/addpremium user_id kunlar</code>\n\n"
        "Misol: <code>/addpremium 123456789 30</code>\n\n"
        "Foydalanuvchi avval botda /start bosgan bo'lishi kerak."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# ============ LOG ============

@router.message(Command("log"), F.chat.type == "private")
async def log_command(message: Message):
    """Log chat ga xabar yuborish"""
    if not is_admin(message.from_user.id):
        return

    if not message.reply_to_message:
        await message.answer("❌ Reply qilingan xabar yo'q!")
        return

    try:
        await message.reply_to_message.copy(config.LOG_CHAT_ID)
        await message.answer("✅ Log chat ga yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
