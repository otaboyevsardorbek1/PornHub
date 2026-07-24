
"""
Content Bot - Start handler
Foydalanuvchi roziligi, kanal tekshiruvi, boshlang'ich menyu, to'lov integratsiyasi
"""
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from database import Database
from utils.helpers import escape_html, get_greeting

router = Router()
db = Database(config.DATABASE_PATH)


class StartStates(StatesGroup):
    waiting_terms = State()


# ============ INLINE KEYBOARDS ============

def get_channel_kb() -> InlineKeyboardMarkup:
    """Kanalga obuna keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", 
                             url=f"https://t.me/{config.REQUIRED_CHANNEL}")],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_channel")]
    ])


def get_terms_kb() -> InlineKeyboardMarkup:
    """Shartlar keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Roziman va davom etish", callback_data="agree_terms")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_terms")]
    ])


def get_main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Asosiy menyu keyboard"""
    is_admin = user_id in config.ADMIN_IDS

    buttons = [
        [InlineKeyboardButton(text="🔍 Qidirish", switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="categories")],
        [InlineKeyboardButton(text="⭐ Top videolar", callback_data="top_videos")],
        [InlineKeyboardButton(text="👤 Mening profilim", callback_data="my_profile")],
    ]

    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============ KANAL TEKSHIRUVI ============

async def check_channel_membership(bot, user_id: int) -> bool:
    """Foydalanuvchi kanalga obuna bo'lganmi"""
    if not config.REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(f"@{config.REQUIRED_CHANNEL}", user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


# ============ START HANDLER ============

@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext):
    """Boshlang'ich komanda"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""

    # Foydalanuvchini bazaga qo'shish
    db.add_user(user_id, username, first_name, last_name)

    # Kanal tekshiruvi
    is_member = await check_channel_membership(message.bot, user_id)
    if not is_member:
        text = (
            f"{get_greeting()} {escape_html(first_name)}!\n\n"
            f"📢 Botdan foydalanish uchun avval kanalimizga obuna bo'ling:\n"
            f"👉 @{config.REQUIRED_CHANNEL}\n\n"
            f"Obuna bo'lgach, 'Tekshirish' tugmasini bosing."
        )
        await message.answer(text, reply_markup=get_channel_kb())
        return

    # Rozilik tekshiruvi
    if not db.check_terms_agreed(user_id):
        text = (
            f"{get_greeting()} {escape_html(first_name)}!\n\n"
            f"🎬 <b>Content Search Bot</b> ga xush kelibsiz!\n\n"
            f"Bu bot orqali siz video kontentlarni qidirishingiz va "
            f"ma'lumotlarini ko'rishingiz mumkin.\n\n"
            f"⚠️ <b>OGOHLANTIRISH:</b>\n"
            f"Bu bot 18+ kontentni o'z ichiga oladi. "
            f"Faqat yetarli yoshdagi foydalanuvchilar foydalanishi mumkin.\n\n"
            f"🔐 <b>Maxfiylik siyosati:</b>\n"
            f"- Qidiruv ma'lumotlaringiz xavfsiz saqlanadi\n"
            f"- Ma'lumotlaringiz uchinchi tomonga tarqatilmaydi\n"
            f"- Foydalanuvchi faoliyati faqat statistika uchun ishlatiladi\n\n"
            f"Davom etish uchun 'Roziman' tugmasini bosing."
        )
        await message.answer(text, reply_markup=get_terms_kb())
        return

    # Asosiy menyu
    await show_main_menu(message)


async def show_main_menu(message: Message):
    """Asosiy menyuni ko'rsatish"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Foydalanuvchi"

    is_premium = db.is_premium(user_id)
    premium_badge = "💎 " if is_premium else ""

    text = (
        f"{get_greeting()} {escape_html(first_name)}!\n\n"
        f"{premium_badge}<b>Content Search Bot</b> ga xush kelibsiz!\n\n"
        f"📌 <b>Mavjud funksiyalar:</b>\n"
        f"• 🔍 <b>Qidirish</b> - Video nomi bo'yicha qidirish\n"
        f"• 📂 <b>Kategoriyalar</b> - Kategoriya bo'yicha ko'rish\n"
        f"• ⭐ <b>Top videolar</b> - Eng mashhur videolar\n"
        f"• 👤 <b>Profil</b> - Shaxsiy statistika\n"
        f"• 💎 <b>Premium</b> - Premium obuna olish\n\n"
        f"💡 <i>Qidirishni boshlash uchun quyidagi tugmani bosing yoki "
        f"inline rejimda (@botname qidiruv) qidiring.</i>"
    )

    await message.answer(text, reply_markup=get_main_menu_kb(user_id))


# ============ CALLBACK HANDLERS ============

@router.callback_query(F.data == "check_channel")
async def check_channel_callback(callback: CallbackQuery):
    """Kanal obunasini tekshirish"""
    is_member = await check_channel_membership(callback.bot, callback.from_user.id)
    if is_member:
        await callback.answer("✅ Obuna tasdiqlandi!")
        await callback.message.delete()
        # Qayta start
        await cmd_start(callback.message, None)
    else:
        await callback.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)


@router.callback_query(F.data == "agree_terms")
async def agree_terms_callback(callback: CallbackQuery):
    """Shartlarga rozi bo'lish"""
    user_id = callback.from_user.id
    db.agree_terms(user_id)

    await callback.answer("✅ Shartlar qabul qilindi!")
    await callback.message.delete()
    await show_main_menu(callback.message)


@router.callback_query(F.data == "cancel_terms")
async def cancel_terms_callback(callback: CallbackQuery):
    """Shartlarni rad etish"""
    await callback.answer("❌ Shartlar rad etildi. Botdan foydalana olmaysiz.", show_alert=True)
    await callback.message.edit_text(
        "❌ <b>Botdan foydalanish rad etildi.</b>\n\n"
        "Shartlarga rozi bo'lish uchun /start buyrug'ini qayta yuboring."
    )


@router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):
    """Bosh sahifaga qaytish"""
    await callback.answer()
    await callback.message.delete()
    await show_main_menu(callback.message)


@router.message(Command("help"), F.chat.type == "private")
async def help_handler(message: Message):
    """Yordam komandasi"""
    is_admin = message.from_user.id in config.ADMIN_IDS

    text = (
        "📖 <b>Yordam</b>\n\n"
        "<b>Asosiy buyruqlar:</b>\n"
        "• /start - Botni ishga tushirish\n"
        "• /help - Bu xabar\n"
        "• /search [so'rov] - Video qidirish\n"
        "• /top - Top videolar\n"
        "• /profile - Shaxsiy profil\n"
        "• /premium - Premium obuna\n"
        "• /payments - To'lov tarixi\n\n"
        "<b>Qanday qidirish:</b>\n"
        "1. Inline rejim: @botname qidiruv so'rovi\n"
        "2. /search komandasi\n"
        "3. Menyudan 'Qidirish' tugmasi\n\n"
        "<b>Premium imkoniyatlar:</b>\n"
        "• Cheksiz qidiruv\n"
        "• Kunlik 50 ta yuklab olish\n"
        "• Premium kontentga kirish\n"
        "• Reklamasiz foydalanish\n\n"
        "<b>To'lov usullari:</b>\n"
        "• ⭐ Telegram Stars\n"
        "• 💳 Click / Bank kartasi"
    )

    if is_admin:
        text += (
            "\n\n<b>Admin buyruqlari:</b>\n"
            "• /admin - Admin panel\n"
            "• /stats - Bot statistikasi\n"
            "• /users - Foydalanuvchilar ro'yxati\n"
            "• /gcast - Xabar tarqatish\n"
            "• /addpremium [id] [kun] - Premium berish\n"
            "• /paystats - To'lov statistikasi"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await message.answer(text, reply_markup=kb)


@router.message(Command("profile"), F.chat.type == "private")
async def profile_handler(message: Message):
    """Profil komandasi"""
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi. /start ni bosing.")
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
        f"📥 Jami yuklab olishlar: {user_stats.get('total_downloads', 0)}\n\n"
        f"📅 Ro'yxatdan o'tgan: {user.get('created_at', 'N/A')[:10]}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
        [InlineKeyboardButton(text="💳 To'lov tarixi", callback_data="payments_history")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await message.answer(text, reply_markup=kb)


@router.message(Command("premium"), F.chat.type == "private")
async def premium_command(message: Message):
    """Premium komandasi"""
    user_id = message.from_user.id

    if db.is_premium(user_id):
        user = db.get_user(user_id)
        premium_until = user.get("premium_until", "")[:10] if user else "N/A"

        text = (
            f"💎 <b>Siz allaqachon Premium foydalanuvchisiz!</b>\n\n"
            f"📅 Obuna muddati: <code>{premium_until}</code>\n\n"
            f"Obunani uzaytirish uchun quyidagi tugmani bosing:"
        )
    else:
        text = (
            "💎 <b>Premium Obuna</b>\n\n"
            "Premium obuna bilan quyidagi imkoniyatlarga ega bo'lasiz:\n\n"
            "✅ Cheksiz qidiruv\n"
            "✅ Kunlik 50 ta yuklab olish\n"
            "✅ Premium kontentga kirish\n"
            "✅ Reklamasiz foydalanish\n"
            "✅ Birinchi bo'lib yangi kontent\n\n"
            "To'lov usulini tanlang:"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars orqali", callback_data="pay_stars_menu")],
        [InlineKeyboardButton(text="💳 Click/Card orqali", callback_data="pay_provider_menu")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await message.answer(text, reply_markup=kb)
