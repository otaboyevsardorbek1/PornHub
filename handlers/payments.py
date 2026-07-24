
"""
Content Bot - To'lov tizimi
Telegram Stars + Provider Payments (Click/Stripe)
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.filters import Command

from config import config
from database import Database
from utils.helpers import escape_html

router = Router()
db = Database(config.DATABASE_PATH)

# ============ NARXLAR ============

PREMIUM_PLANS = {
    "monthly": {
        "name": "Oylik Premium",
        "days": 30,
        "stars": 100,
        "uzs": 50000,
        "description": "30 kunlik Premium obuna"
    },
    "quarterly": {
        "name": "Chorak yillik Premium",
        "days": 90,
        "stars": 250,
        "uzs": 130000,
        "description": "90 kunlik Premium obuna (13% chegirma)"
    },
    "yearly": {
        "name": "Yillik Premium",
        "days": 365,
        "stars": 800,
        "uzs": 450000,
        "description": "365 kunlik Premium obuna (25% chegirma)"
    }
}


# ============ ASOSIY TO'LOV MENYUSI ============

@router.callback_query(F.data == "get_premium")
async def get_premium_menu(callback: CallbackQuery):
    """Premium tanlash menyusi"""
    await callback.answer()

    user_id = callback.from_user.id

    if db.is_premium(user_id):
        user = db.get_user(user_id)
        premium_until = user.get("premium_until", "")[:10] if user else "N/A"

        text = (
            f"💎 <b>Siz allaqachon Premium foydalanuvchisiz!</b>\n\n"
            f"📅 Obuna muddati: <code>{premium_until}</code>\n\n"
            f"Obunani uzaytirish uchun quyidagi tariflardan birini tanlang:"
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

    await callback.message.edit_text(text, reply_markup=kb)


# ============ TELEGRAM STARS TO'LOV ============

@router.callback_query(F.data == "pay_stars_menu")
async def pay_stars_menu(callback: CallbackQuery):
    """Stars bilan to'lov menyusi"""
    await callback.answer()

    text = "⭐ <b>Telegram Stars orqali to'lov</b>\n\nTarifni tanlang:"

    buttons = []
    for plan_id, plan in PREMIUM_PLANS.items():
        buttons.append([InlineKeyboardButton(
            text=f"📅 {plan['name']} - ⭐{plan['stars']}",
            callback_data=f"stars_{plan_id}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="get_premium")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("stars_"))
async def stars_payment(callback: CallbackQuery):
    """Stars to'lov invoice yuborish"""
    await callback.answer()

    plan_id = callback.data.replace("stars_", "")
    plan = PREMIUM_PLANS.get(plan_id)

    if not plan:
        await callback.answer("❌ Noto'g'ri tarif!", show_alert=True)
        return

    user_id = callback.from_user.id

    # Invoice yuborish - Stars uchun provider_token bo'sh
    try:
        await callback.bot.send_invoice(
            chat_id=user_id,
            title=plan["name"],
            description=plan["description"],
            payload=json.dumps({
                "plan": plan_id,
                "user_id": user_id,
                "type": "stars_premium",
                "timestamp": datetime.now().isoformat()
            }),
            provider_token="",  # Stars uchun bo'sh
            currency="XTR",     # Telegram Stars
            prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
            start_parameter=f"premium_{plan_id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"⭐ To'lash {plan['stars']} Stars", pay=True)]
            ])
        )

        await callback.message.edit_text(
            f"⭐ <b>{plan['name']}</b>\n\n"
            f"Tafsilotlar:\n"
            f"• Muddat: {plan['days']} kun\n"
            f"• Narx: {plan['stars']} Stars\n\n"
            f"Yuqoridagi invoice ni to'lang.\n"
            f"To'lov muvaffaqiyatli bo'lganda premium avtomatik faollashadi!"
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Xatolik: {e}\n\n"
            f"Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning."
        )


# ============ CLICK / PROVIDER TO'LOV ============

@router.callback_query(F.data == "pay_provider_menu")
async def pay_provider_menu(callback: CallbackQuery):
    """Click/Provider bilan to'lov menyusi"""
    await callback.answer()

    text = "💳 <b>Click/Card orqali to'lov</b>\n\nTarifni tanlang:"

    buttons = []
    for plan_id, plan in PREMIUM_PLANS.items():
        buttons.append([InlineKeyboardButton(
            text=f"📅 {plan['name']} - {plan['uzs']:,} so'm",
            callback_data=f"provider_{plan_id}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="get_premium")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("provider_"))
async def provider_payment(callback: CallbackQuery):
    """Click/Provider to'lov invoice yuborish"""
    await callback.answer()

    plan_id = callback.data.replace("provider_", "")
    plan = PREMIUM_PLANS.get(plan_id)

    if not plan:
        await callback.answer("❌ Noto'g'ri tarif!", show_alert=True)
        return

    user_id = callback.from_user.id

    # Provider token tekshirish
    provider_token = config.PAYMENT_PROVIDER_TOKEN
    if not provider_token:
        # Provider token yo'q - admin bilan bog'lanish
        text = (
            f"💳 <b>{plan['name']}</b>\n\n"
            f"Tafsilotlar:\n"
            f"• Muddat: {plan['days']} kun\n"
            f"• Narx: {plan['uzs']:,} so'm\n\n"
            f"⚠️ <b>To'lov tizimi vaqtinchalik ishlamayapti.</b>\n\n"
            f"Iltimos, admin bilan bog'laning:\n"
        )

        # Adminlarga havola tugmalari
        admin_buttons = []
        for admin_id in config.ADMIN_IDS[:3]:
            try:
                admin_user = await callback.bot.get_chat(admin_id)
                admin_username = admin_user.username
                if admin_username:
                    admin_buttons.append([InlineKeyboardButton(
                        text=f"👤 Admin: @{admin_username}",
                        url=f"https://t.me/{admin_username}"
                    )])
            except:
                pass

        admin_buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="pay_provider_menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=admin_buttons)

        await callback.message.edit_text(text, reply_markup=kb)
        return

    # Invoice yuborish (Provider token bilan)
    try:
        await callback.bot.send_invoice(
            chat_id=user_id,
            title=plan["name"],
            description=plan["description"],
            payload=json.dumps({
                "plan": plan_id,
                "user_id": user_id,
                "type": "provider_premium",
                "timestamp": datetime.now().isoformat()
            }),
            provider_token=provider_token,
            currency="UZS",
            prices=[LabeledPrice(label=plan["name"], amount=plan["uzs"] * 100)],  # Tiyinda
            start_parameter=f"premium_{plan_id}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 To'lash {plan['uzs']:,} so'm", pay=True)]
            ])
        )

        await callback.message.edit_text(
            f"💳 <b>{plan['name']}</b>\n\n"
            f"Tafsilotlar:\n"
            f"• Muddat: {plan['days']} kun\n"
            f"• Narx: {plan['uzs']:,} so'm\n\n"
            f"Yuqoridagi invoice ni to'lang.\n"
            f"To'lov muvaffaqiyatli bo'lganda premium avtomatik faollashadi!"
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Xatolik: {e}\n\n"
            f"Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning."
        )


# ============ PRE-CHECKOUT HANDLER ============

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    """To'lovni tasdiqlash"""
    try:
        payload = json.loads(pre_checkout.invoice_payload)
        plan_id = payload.get("plan", "")
        plan = PREMIUM_PLANS.get(plan_id)

        if not plan:
            await pre_checkout.answer(ok=False, error_message="Noto'g'ri tarif!")
            return

        # To'lovni tasdiqlash
        await pre_checkout.answer(ok=True)

    except Exception as e:
        await pre_checkout.answer(ok=False, error_message=f"Xatolik: {str(e)[:100]}")


# ============ SUCCESSFUL PAYMENT HANDLER ============

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Muvaffaqiyatli to'lovni qayta ishlash"""
    payment = message.successful_payment

    try:
        payload = json.loads(payment.invoice_payload)
        plan_id = payload.get("plan", "")
        user_id = payload.get("user_id", message.from_user.id)
        payment_type = payload.get("type", "")

        plan = PREMIUM_PLANS.get(plan_id)
        if not plan:
            await message.answer("❌ Noto'g'ri tarif ma'lumoti!")
            return

        # Premiumni faollashtirish
        if db.set_premium(user_id, plan["days"]):
            # Foydalanuvchiga xabar
            amount_display = payment.total_amount // 100 if payment.currency != "XTR" else payment.total_amount
            currency_display = "so'm" if payment.currency != "XTR" else "Stars"

            await message.answer(
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"💎 <b>{plan['name']}</b> muvaffaqiyatli faollashtirildi!\n\n"
                f"📅 Muddat: {plan['days']} kun\n"
                f"💰 To'langan: {amount_display:,} {currency_display}\n"
                f"🔑 Transaction ID: <code>{payment.telegram_payment_charge_id}</code>\n\n"
                f"Endi barcha premium imkoniyatlardan foydalanishingiz mumkin!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
                ])
            )

            # Adminlarga xabar
            for admin_id in config.ADMIN_IDS:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"💰 <b>Yangi to'lov!</b>\n\n"
                        f"👤 Foydalanuvchi: {user_id}\n"
                        f"📛 Ism: {escape_html(message.from_user.first_name)}\n"
                        f"📛 Username: @{escape_html(message.from_user.username or 'N/A')}\n"
                        f"💎 Tarif: {plan['name']}\n"
                        f"📅 Kunlar: {plan['days']}\n"
                        f"💰 Summa: {amount_display:,} {currency_display}\n"
                        f"🔑 Transaction: <code>{payment.telegram_payment_charge_id}</code>\n"
                        f"💳 Provider: <code>{payment.provider_payment_charge_id}</code>\n"
                        f"⏰ Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                except Exception:
                    pass

            # To'lovni bazaga saqlash
            db.log_payment(
                user_id=user_id,
                plan=plan_id,
                amount=amount_display,
                currency=payment.currency,
                transaction_id=payment.telegram_payment_charge_id,
                provider_id=payment.provider_payment_charge_id,
                status="completed",
                payment_type=payment_type
            )

        else:
            await message.answer(
                "❌ Premium faollashtirishda xatolik!\n\n"
                "Iltimos, admin bilan bog'laning.\n"
                f"Transaction ID: <code>{payment.telegram_payment_charge_id}</code>"
            )

    except Exception as e:
        await message.answer(f"❌ To'lovni qayta ishlashda xatolik: {e}")


# ============ TO'LOV TARIXI ============

@router.message(Command("payments"), F.chat.type == "private")
async def payments_history(message: Message):
    """To'lov tarixi"""
    user_id = message.from_user.id

    payments = db.get_user_payments(user_id)

    if not payments:
        await message.answer(
            "📭 <b>To'lov tarixi bo'sh.</b>\n\n"
            "Premium obuna sotib olish uchun /premium ni bosing."
        )
        return

    text = "💳 <b>To'lov tarixi</b>\n\n"

    for i, payment in enumerate(payments[:10], 1):
        plan_name = PREMIUM_PLANS.get(payment.get("plan", ""), {}).get("name", "Nomsiz")
        amount = payment.get("amount", 0)
        currency = payment.get("currency", "UZS")
        status = payment.get("status", "pending")
        date = payment.get("created_at", "")[:10]

        status_icon = "✅" if status == "completed" else "❌"
        text += f"{i}. {status_icon} <b>{plan_name}</b>\n"
        text += f"   💰 {amount:,} {currency}\n"
        text += f"   📅 {date}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Premium olish", callback_data="get_premium")],
        [InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="home")]
    ])

    await message.answer(text, reply_markup=kb)


# ============ ADMIN: STARS BALANS ============

@router.message(Command("balance"), F.chat.type == "private")
async def stars_balance(message: Message):
    """Stars balansini ko'rish (faqat admin)"""
    if message.from_user.id not in config.ADMIN_IDS:
        return

    await message.answer(
        "⭐ <b>Telegram Stars Balansi</b>\n\n"
        "Balansni ko'rish uchun:\n"
        "@BotFather → Bot Settings → Payments → Balance\n\n"
        "Yoki Telegram bot sozlamalaridan 'Balance' bo'limiga o'ting."
    )


# ============ ADMIN: TO'LOVLAR STATISTIKASI ============

@router.message(Command("paystats"), F.chat.type == "private")
async def payment_stats(message: Message):
    """To'lov statistikasi (faqat admin)"""
    if message.from_user.id not in config.ADMIN_IDS:
        return

    stats = db.get_payment_stats()

    text = (
        "💰 <b>To'lov Statistikasi</b>\n\n"
        f"📊 Jami to'lovlar: <code>{stats.get('total_payments', 0)}</code>\n"
        f"✅ Muvaffaqiyatli: <code>{stats.get('completed', 0)}</code>\n"
        f"❌ Bekor qilingan: <code>{stats.get('cancelled', 0)}</code>\n"
        f"💰 Jami daromad (Stars): <code>{stats.get('total_stars', 0)}</code>\n"
        f"💰 Jami daromad (UZS): <code>{stats.get('total_uzs', 0):,}</code> so'm\n"
        f"👥 To'lov qilganlar: <code>{stats.get('unique_users', 0)}</code>\n\n"
        f"📅 Oxirgi 7 kun: <code>{stats.get('last_7_days', 0)}</code> ta\n"
        f"📅 Oxirgi 30 kun: <code>{stats.get('last_30_days', 0)}</code> ta"
    )

    await message.answer(text)
