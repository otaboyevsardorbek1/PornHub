# Bu qiymatlarni .env fayldan yoki to'g'ridan-to'g'ri o'zgartiring
BOT_TOKEN = "8546002257:AAHgtSFVq9owp6tGJHOtMSFAsGVQMT2RoNE"  # Bot tokeningizni kiriting
ADMIN_IDS = [6646928202]  # Admin IDlarini kiriting
CHANNEL_ID = "-1002120532575"  # Kanal ID
CHANNEL_URL = "https://t.me/otaboyev_sardorbek_blog_dev"  # Kanal havolasi
REDIS_URL = "redis://localhost:6379"
DATABASE_URL = "sqlite+aiosqlite:///konkurs.db"

import asyncio
import logging
import random
import json
import secrets
import time
from typing import Dict, List, Tuple, Optional, Union, Callable, Any, Awaitable
from datetime import datetime, timedelta

# Aiogram importlari
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import BaseMiddleware

# SQLAlchemy importlari
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, 
    DateTime, Float, ForeignKey, Text, func, select
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Style konstantalari
STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER = "danger"

# Bonus qutilar narxlari
BOX_PRICES = {
    "mystery": 50,
    "golden": 100,
    "platinum": 200
}

# O'yin sozlamalari
GAME_SETTINGS = {
    "min_number": 1,
    "max_number": 1000,
    "buttons_count": 8,
    "bonus_button_count": 1,
    "play_cost": 10,
    "win_multiplier": 5
}

# ==================== MA'LUMOTLAR BAZASI ====================

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    balance = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0)
    games_played = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    referrer_id = Column(BigInteger, nullable=True)
    is_banned = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    boxes = relationship("UserBox", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    referrals = relationship("Referral", back_populates="referrer", foreign_keys="[Referral.referrer_id]")
    achievements = relationship("UserAchievement", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")

class UserBox(Base):
    __tablename__ = "user_boxes"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    box_type = Column(String, nullable=False)
    is_opened = Column(Boolean, default=False)
    reward = Column(Float, default=0.0)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="boxes")

class Referral(Base):
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True)
    referrer_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    referred_id = Column(BigInteger, unique=True)
    bonus_received = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    referrer = relationship("User", back_populates="referrals", foreign_keys=[referrer_id])

class GameHistory(Base):
    __tablename__ = "game_history"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    selected_number = Column(Integer)
    winning_number = Column(Integer)
    is_winner = Column(Boolean, default=False)
    bet_amount = Column(Float, default=0.0)
    win_amount = Column(Float, default=0.0)
    played_at = Column(DateTime, default=datetime.utcnow)

class DailyBonus(Base):
    __tablename__ = "daily_bonuses"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    day_streak = Column(Integer, default=1)
    last_claimed = Column(DateTime)
    total_claimed = Column(Float, default=0)

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    icon = Column(String)
    reward = Column(Float, default=0)
    criteria_type = Column(String)
    criteria_value = Column(Integer)

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    achieved_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="achievements")

class Jackpot(Base):
    __tablename__ = "jackpot"
    
    id = Column(Integer, primary_key=True)
    total_amount = Column(Float, default=0.0)
    last_winner_id = Column(BigInteger, nullable=True)
    last_win_amount = Column(Float, default=0.0)
    total_contributions = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Tournament(Base):
    __tablename__ = "tournaments"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    prize_pool = Column(Float, default=0.0)
    entry_fee = Column(Float, default=0.0)
    max_participants = Column(Integer, default=100)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String, default="upcoming")
    winner_id = Column(BigInteger, nullable=True)

class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"
    
    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    score = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)

class GiftCode(Base):
    __tablename__ = "gift_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    amount = Column(Float)
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    created_by = Column(BigInteger)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)

# Ma'lumotlar bazasi
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ==================== ACHIEVEMENTLAR ====================

ACHIEVEMENTS_DATA = [
    {"name": "🎮 Yangi o'yinchi", "description": "Birinchi o'yin", "icon": "🎮", "reward": 10, "type": "games_played", "value": 1},
    {"name": "⭐ Tajribali", "description": "10 ta o'yin", "icon": "⭐", "reward": 50, "type": "games_played", "value": 10},
    {"name": "👑 Professional", "description": "100 ta o'yin", "icon": "👑", "reward": 200, "type": "games_played", "value": 100},
    {"name": "🏆 G'olib", "description": "5 ta yutuq", "icon": "🏆", "reward": 100, "type": "games_won", "value": 5},
    {"name": "💰 Boy", "description": "1000 ball yig'ish", "icon": "💰", "reward": 150, "type": "balance", "value": 1000},
    {"name": "🤝 Do'stlar", "description": "5 ta referal", "icon": "🤝", "reward": 75, "type": "referrals", "value": 5},
]

# ==================== KLAVIATURALAR ====================

def get_main_menu():
    """Asosiy menyu"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎮 O'yin o'ynash", callback_data="play_game"),
        InlineKeyboardButton(text="🎁 Qutilar", callback_data="boxes_menu")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Balans", callback_data="balance"),
        InlineKeyboardButton(text="👥 Referal", callback_data="referral")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Kunlik bonus", callback_data="daily_bonus"),
        InlineKeyboardButton(text="🏆 Turnirlar", callback_data="tournaments")
    )
    builder.row(
        InlineKeyboardButton(text="🏅 Yutuqlar", callback_data="achievements"),
        InlineKeyboardButton(text="🎫 Promokod", callback_data="gift_code")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="stats"),
        InlineKeyboardButton(text="ℹ️ Yordam", callback_data="help")
    )
    if ADMIN_IDS:
        builder.row(
            InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")
        )
    return builder.as_markup()

def get_boxes_menu():
    """Qutilar menyusi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔮 Maxfiy quti (50 ball)", callback_data="buy_box_mystery"),
        InlineKeyboardButton(text="👑 Oltin quti (100 ball)", callback_data="buy_box_golden")
    )
    builder.row(
        InlineKeyboardButton(text="💎 Platina quti (200 ball)", callback_data="buy_box_platinum")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Mening qutilarim", callback_data="my_boxes")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")
    )
    return builder.as_markup()

def generate_game_buttons(winning_number: int, bonus_button_index: int):
    """O'yin tugmalarini yaratish"""
    builder = InlineKeyboardBuilder()
    
    numbers = set()
    numbers.add(winning_number)
    
    while len(numbers) < 8:
        numbers.add(random.randint(1, 1000))
    
    numbers = list(numbers)
    random.shuffle(numbers)
    
    for i in range(0, 8, 2):
        row_buttons = []
        for j in range(2):
            if i + j < 8:
                index = i + j
                number = numbers[index]
                
                if index == bonus_button_index:
                    row_buttons.append(
                        InlineKeyboardButton(
                            text=f"💎 {number}",
                            callback_data=f"game_select_{number}_1"
                        )
                    )
                else:
                    row_buttons.append(
                        InlineKeyboardButton(
                            text=f"🎲 {number}",
                            callback_data=f"game_select_{number}_0"
                        )
                    )
        builder.row(*row_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔙 Chiqish", callback_data="main_menu")
    )
    return builder.as_markup()

def get_subscribe_keyboard():
    """Obuna tekshirish tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_URL)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")
    )
    return builder.as_markup()

def get_referral_keyboard(user_id: int):
    """Referral tizimi tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Do'stlarga ulashish", switch_inline_query=f"ref_{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")
    )
    return builder.as_markup()

def get_admin_panel():
    """Admin panel"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Bot statistikasi", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Ball berish", callback_data="admin_give_balance")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast")
    )
    builder.row(
        InlineKeyboardButton(text="🎫 Promokod yaratish", callback_data="admin_create_gift")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")
    )
    return builder.as_markup()

# ==================== YORDAMCHI FUNKSIYALAR ====================

def generate_game_state() -> Tuple[int, int, List[int]]:
    """O'yin holatini yaratish"""
    winning_number = random.randint(1, 1000)
    numbers = {winning_number}
    while len(numbers) < 8:
        numbers.add(random.randint(1, 1000))
    numbers_list = list(numbers)
    random.shuffle(numbers_list)
    bonus_index = random.randint(0, 7)
    return winning_number, bonus_index, numbers_list

async def check_subscription(bot, user_id: int, channel_id: str) -> bool:
    """Foydalanuvchi kanalga obuna bo'lganligini tekshirish"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logger.error(f"Obuna tekshirishda xato: {e}")
        return False

async def add_balance(session: AsyncSession, user: User, amount: float, description: str = "Bonus"):
    """Foydalanuvchi balansiga qo'shish"""
    user.balance += amount
    user.total_earned += amount
    transaction = Transaction(
        user_id=user.telegram_id,
        amount=amount,
        type="deposit" if amount > 0 else "withdrawal",
        description=description
    )
    session.add(transaction)
    await session.commit()

async def deduct_balance(session: AsyncSession, user: User, amount: float, description: str = "O'yin") -> bool:
    """Balansdan yechish"""
    if user.balance < amount:
        return False
    user.balance -= amount
    transaction = Transaction(
        user_id=user.telegram_id,
        amount=-amount,
        type="withdrawal",
        description=description
    )
    session.add(transaction)
    await session.commit()
    return True

async def open_box(session: AsyncSession, user: User, box: UserBox) -> float:
    """Qutini ochish"""
    box_types = {
        "mystery": {"min": 10, "max": 100, "multiplier": 1},
        "golden": {"min": 50, "max": 500, "multiplier": 2},
        "platinum": {"min": 100, "max": 1000, "multiplier": 3}
    }
    box_config = box_types.get(box.box_type)
    if not box_config:
        return 0
    base_reward = random.uniform(box_config['min'], box_config['max'])
    reward = base_reward * box_config['multiplier']
    box.is_opened = True
    box.reward = reward
    box.opened_at = datetime.utcnow()
    await add_balance(session, user, reward, f"{box.box_type} quti ochildi")
    return reward

async def process_referral(session: AsyncSession, referrer_id: int, referred_id: int):
    """Referral bonusini hisoblash"""
    referral = Referral(referrer_id=referrer_id, referred_id=referred_id)
    session.add(referral)
    result = await session.execute(select(User).where(User.telegram_id == referrer_id))
    referrer = result.scalar_one_or_none()
    if referrer:
        await add_balance(session, referrer, 5, "Referral bonus")
    await session.commit()

async def check_achievements(session: AsyncSession, user: User):
    """Yutuqlarni tekshirish"""
    new_achievements = []
    
    for ach_data in ACHIEVEMENTS_DATA:
        result = await session.execute(
            select(Achievement).where(Achievement.name == ach_data['name'])
        )
        if not result.scalar_one_or_none():
            achievement = Achievement(
                name=ach_data['name'],
                description=ach_data['description'],
                icon=ach_data['icon'],
                reward=ach_data['reward'],
                criteria_type=ach_data['type'],
                criteria_value=ach_data['value']
            )
            session.add(achievement)
    await session.commit()
    
    result = await session.execute(select(Achievement))
    all_achievements = result.scalars().all()
    
    for achievement in all_achievements:
        result = await session.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == user.telegram_id,
                UserAchievement.achievement_id == achievement.id
            )
        )
        if result.scalar_one_or_none():
            continue
        
        achieved = False
        if achievement.criteria_type == 'games_played' and user.games_played >= achievement.criteria_value:
            achieved = True
        elif achievement.criteria_type == 'games_won' and user.games_won >= achievement.criteria_value:
            achieved = True
        elif achievement.criteria_type == 'balance' and user.total_earned >= achievement.criteria_value:
            achieved = True
        elif achievement.criteria_type == 'referrals':
            result = await session.execute(
                select(func.count(Referral.id)).where(Referral.referrer_id == user.telegram_id)
            )
            if result.scalar() >= achievement.criteria_value:
                achieved = True
        
        if achieved:
            user_achievement = UserAchievement(
                user_id=user.telegram_id,
                achievement_id=achievement.id
            )
            session.add(user_achievement)
            await add_balance(session, user, achievement.reward, f"Yutuq: {achievement.name}")
            new_achievements.append(achievement)
    
    await session.commit()
    return new_achievements

async def claim_daily_bonus(session: AsyncSession, user: User) -> dict:
    """Kunlik bonus olish"""
    today = datetime.utcnow().date()
    
    result = await session.execute(
        select(DailyBonus).where(
            DailyBonus.user_id == user.telegram_id,
            func.date(DailyBonus.last_claimed) == today
        )
    )
    today_bonus = result.scalar_one_or_none()
    
    if today_bonus:
        return {"success": False, "message": "Bugun bonus olingan!"}
    
    result = await session.execute(
        select(DailyBonus).where(DailyBonus.user_id == user.telegram_id)
        .order_by(DailyBonus.last_claimed.desc())
    )
    last_bonus = result.scalar_one_or_none()
    
    streak = 1
    if last_bonus:
        yesterday = datetime.utcnow() - timedelta(days=1)
        if last_bonus.last_claimed.date() == yesterday.date():
            streak = last_bonus.day_streak + 1
    
    base_bonus = 10
    streak_bonus = min(streak - 1, 7) * 5
    total_bonus = base_bonus + streak_bonus
    
    daily_bonus = DailyBonus(
        user_id=user.telegram_id,
        day_streak=streak,
        last_claimed=datetime.utcnow(),
        total_claimed=total_bonus
    )
    session.add(daily_bonus)
    await add_balance(session, user, total_bonus, f"Kunlik bonus ({streak}-kun)")
    
    return {
        "success": True,
        "bonus": total_bonus,
        "streak": streak,
        "message": f"✅ {total_bonus} ball olindi! ({streak}-kunlik streak)"
    }

async def create_gift_code(session: AsyncSession, creator_id: int, amount: float, max_uses: int = 1) -> str:
    """Sovg'a kodini yaratish"""
    code = f"GIFT-{secrets.token_hex(4).upper()}"
    gift = GiftCode(
        code=code,
        amount=amount,
        max_uses=max_uses,
        created_by=creator_id
    )
    session.add(gift)
    await session.commit()
    return code

async def redeem_gift_code(session: AsyncSession, user: User, code: str) -> dict:
    """Sovg'a kodini ishlatish"""
    result = await session.execute(
        select(GiftCode).where(
            GiftCode.code == code,
            GiftCode.is_active == True
        )
    )
    gift = result.scalar_one_or_none()
    
    if not gift:
        return {"success": False, "message": "❌ Kod topilmadi!"}
    if gift.current_uses >= gift.max_uses:
        return {"success": False, "message": "❌ Kod eskirgan!"}
    if gift.expires_at and gift.expires_at < datetime.utcnow():
        return {"success": False, "message": "❌ Kod muddati tugagan!"}
    
    gift.current_uses += 1
    if gift.current_uses >= gift.max_uses:
        gift.is_active = False
    
    await add_balance(session, user, gift.amount, f"Sovg'a kodi: {code}")
    return {"success": True, "amount": gift.amount, "message": f"✅ {gift.amount} ball qo'shildi!"}

async def get_bot_statistics(session: AsyncSession) -> dict:
    """Bot statistikasi"""
    result = await session.execute(select(func.count(User.id)))
    total_users = result.scalar()
    today = datetime.utcnow().date()
    result = await session.execute(
        select(func.count(GameHistory.id)).where(
            func.date(GameHistory.played_at) == today
        )
    )
    today_games = result.scalar()
    return {
        "total_users": total_users,
        "today_games": today_games,
        "active_users": total_users
    }

# ==================== MIDDLEWARE'LAR ====================

class DatabaseMiddleware(BaseMiddleware):
    """Ma'lumotlar bazasi middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data['session'] = session
            if isinstance(event, Message):
                user_id = event.from_user.id
            elif isinstance(event, CallbackQuery):
                user_id = event.from_user.id
            else:
                user_id = None
            
            if user_id:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    user = User(
                        telegram_id=user_id,
                        username=event.from_user.username,
                        full_name=event.from_user.full_name
                    )
                    session.add(user)
                    await session.commit()
                data['user'] = user
            return await handler(event, data)

# ==================== BOT HANDLERLARI ====================

# Event loop yaratish
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Middleware'larni qo'shish
dp.message.middleware(DatabaseMiddleware())
dp.callback_query.middleware(DatabaseMiddleware())

# O'yin holatlari
active_games: Dict[int, dict] = {}

# FSM States
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_gift_amount = State()
    waiting_for_gift_uses = State()
    waiting_for_promo_code = State()

# ==================== KOMANDALAR ====================

@dp.message(Command("start"))
async def start_command(message: Message, user: User, session: AsyncSession):
    """Start komandasi"""
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user.telegram_id:
                result = await session.execute(
                    select(Referral).where(Referral.referred_id == user.telegram_id)
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    await process_referral(session, referrer_id, user.telegram_id)
                    await message.answer("🎉 Siz referral orqali qo'shildingiz!")
        except Exception as e:
            logger.error(f"Referral xato: {e}")
    
    await message.answer(
        f"👋 Salom, {user.full_name}!\n\n"
        "🎰 <b>Mukammal Konkurs Platformasiga</b> xush kelibsiz!\n\n"
        "📌 <b>Imkoniyatlar:</b>\n"
        "• 🎮 8 ta tugmali o'yin\n"
        "• 🎁 Maxfiy va Oltin qutilar\n"
        "• 💎 Bonusli tugmalar\n"
        "• 👥 Referral tizimi\n"
        "• 💰 Ball yig'ish\n"
        "• 🏆 Turnirlar\n"
        "• 🏅 Yutuqlar tizimi\n"
        "• 🎫 Promokodlar\n\n"
        "🎯 Omadli bo'ling!",
        reply_markup=get_main_menu()
    )

@dp.message(Command("play"))
async def play_command(message: Message, user: User, session: AsyncSession):
    """Tez o'yin boshlash"""
    await start_game_logic(message, user, session)

@dp.message(Command("balance"))
async def balance_command(message: Message, user: User):
    """Balans ko'rish"""
    await message.answer(
        f"💰 <b>Balansingiz</b>\n\n"
        f"💵 Joriy balans: <b>{user.balance:.0f} ball</b>\n"
        f"📊 Jami yig'ilgan: <b>{user.total_earned:.0f} ball</b>\n"
        f"🎮 O'yinlar: <b>{user.games_played}</b>\n"
        f"🏆 Yutuqlar: <b>{user.games_won}</b>",
        reply_markup=get_main_menu()
    )

@dp.message(Command("promo"))
async def promo_command(message: Message, user: User, state: FSMContext):
    """Promokod kiritish"""
    await message.answer(
        "🎫 <b>Promokod kiritish</b>\n\n"
        "Iltimos, promokodingizni yozing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="main_menu")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_promo_code)

@dp.message(AdminStates.waiting_for_promo_code)
async def process_promo_code(message: Message, user: User, session: AsyncSession, state: FSMContext):
    """Promokodni qayta ishlash"""
    code = message.text.strip().upper()
    result = await redeem_gift_code(session, user, code)
    
    if result['success']:
        await message.answer(
            f"🎉 {result['message']}\n\n"
            f"💰 Qo'shilgan: {result['amount']} ball\n"
            f"💵 Yangi balans: {user.balance:.0f} ball",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            f"❌ {result['message']}\n\n"
            "Qayta urinib ko'ring yoki /promo buyrug'ini bering.",
            reply_markup=get_main_menu()
        )
    
    await state.clear()

@dp.message(Command("admin"))
async def admin_command(message: Message, user: User):
    """Admin panel"""
    if user.telegram_id not in ADMIN_IDS and not user.is_admin:
        await message.answer("❌ Ruxsat yo'q!")
        return
    
    await message.answer(
        "👑 <b>Admin Panel</b>\n\n"
        "Kerakli amalni tanlang:",
        reply_markup=get_admin_panel()
    )

# ==================== CALLBACK HANDLERLARI ====================

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Asosiy menyuga qaytish"""
    await callback.message.edit_text(
        "🎰 <b>Asosiy menyu</b>\n\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def balance_callback(callback: CallbackQuery, user: User):
    """Balans ko'rish"""
    await callback.message.edit_text(
        f"💰 <b>Balansingiz</b>\n\n"
        f"💵 Joriy balans: <b>{user.balance:.0f} ball</b>\n"
        f"📊 Jami yig'ilgan: <b>{user.total_earned:.0f} ball</b>\n"
        f"🎮 O'yinlar: <b>{user.games_played}</b>\n"
        f"🏆 Yutuqlar: <b>{user.games_won}</b>\n\n"
        f"🎁 Ball yig'ish uchun o'yin o'ynang yoki qutilar oching!",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "play_game")
async def play_game_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    """O'yin boshlash"""
    await start_game_logic(callback.message, user, session, is_callback=True)
    await callback.answer()

async def start_game_logic(target, user: User, session: AsyncSession, is_callback: bool = False):
    """O'yin boshlash logikasi"""
    if CHANNEL_ID:
        is_subscribed = await check_subscription(bot, user.telegram_id, CHANNEL_ID)
        if not is_subscribed:
            text = "⚠️ <b>O'yin uchun kanalga obuna bo'lishingiz kerak!</b>\n\nIltimos, kanalga obuna bo'ling va tekshirish tugmasini bosing."
            if is_callback:
                await target.edit_text(text, reply_markup=get_subscribe_keyboard())
            else:
                await target.answer(text, reply_markup=get_subscribe_keyboard())
            return
    
    play_cost = GAME_SETTINGS['play_cost']
    if user.balance < play_cost:
        if is_callback:
            await target.answer(f"❌ Balansingiz yetarli emas! Kerak: {play_cost} ball", show_alert=True)
        else:
            await target.answer(f"❌ Balansingiz yetarli emas! Kerak: {play_cost} ball")
        return
    
    success = await deduct_balance(session, user, play_cost, "O'yin boshlash")
    if not success:
        return
    
    winning_number, bonus_index, numbers = generate_game_state()
    active_games[user.telegram_id] = {
        'winning_number': winning_number,
        'bonus_index': bonus_index,
        'numbers': numbers,
        'bet_amount': play_cost
    }
    
    text = (
        f"🎲 <b>O'yin boshlandi!</b>\n\n"
        f"💎 Bonusli tugma maxsus belgilangan!\n"
        f"🎯 1-1000 oralig'idagi sonni tanlang:\n"
        f"💰 Tikish: {play_cost} ball"
    )
    
    if is_callback:
        await target.edit_text(text, reply_markup=generate_game_buttons(winning_number, bonus_index))
    else:
        await target.answer(text, reply_markup=generate_game_buttons(winning_number, bonus_index))

@dp.callback_query(F.data.startswith("game_select_"))
async def game_selected(callback: CallbackQuery, user: User, session: AsyncSession):
    """O'yin tanlovi"""
    parts = callback.data.split("_")
    selected_number = int(parts[2])
    is_bonus = int(parts[3]) == 1
    
    game_data = active_games.get(user.telegram_id)
    if not game_data:
        await callback.answer("❌ O'yin topilmadi! Qayta boshlang.", show_alert=True)
        return
    
    winning_number = game_data['winning_number']
    bet_amount = game_data['bet_amount']
    user.games_played += 1
    is_winner = selected_number == winning_number
    win_amount = 0
    
    if is_winner:
        multiplier = GAME_SETTINGS['win_multiplier']
        if is_bonus:
            multiplier *= 2
        win_amount = bet_amount * multiplier
        await add_balance(session, user, win_amount, f"O'yin yutug'i (x{multiplier})")
        user.games_won += 1
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ {winning_number} YUTUQ! +{win_amount} ball", callback_data="game_won")],
            [InlineKeyboardButton(text="🎮 Yana o'ynash", callback_data="play_game")],
            [InlineKeyboardButton(text="🔙 Menyu", callback_data="main_menu")]
        ])
        
        result_text = (
            f"🎉 <b>TABRIKLAYMAN!</b>\n\n"
            f"🎯 Siz yutuqli sonni topdingiz!\n"
            f"💎 Bonus tugma: {'Ha' if is_bonus else 'Yoq'}\n"
            f"💰 Yutuq: <b>{win_amount} ball</b>\n"
            f"📊 Multiplier: x{multiplier}\n\n"
            f"🎮 Yana o'ynashni xohlaysizmi?"
        )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {selected_number} Noto'g'ri", callback_data="game_lost")],
            [InlineKeyboardButton(text=f"🎯 To'g'ri: {winning_number}", callback_data="show_correct")],
            [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="play_game")],
            [InlineKeyboardButton(text="🔙 Menyu", callback_data="main_menu")]
        ])
        
        result_text = (
            f"😔 <b>AFSUS!</b>\n\n"
            f"❌ Tanlagan soningiz: {selected_number}\n"
            f"🎯 Yutuqli son: {winning_number}\n"
            f"💎 Bonus tugma: {'Ha' if is_bonus else 'Yoq'}\n\n"
            f"🔄 Qayta urinib ko'ring!"
        )
    
    game_history = GameHistory(
        user_id=user.telegram_id,
        selected_number=selected_number,
        winning_number=winning_number,
        is_winner=is_winner,
        bet_amount=bet_amount,
        win_amount=win_amount if is_winner else 0
    )
    session.add(game_history)
    await session.commit()
    
    await check_achievements(session, user)
    
    del active_games[user.telegram_id]
    await callback.message.edit_text(result_text, reply_markup=keyboard)
    await callback.answer()

# Qutilar
@dp.callback_query(F.data == "boxes_menu")
async def boxes_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>Bonus qutilar</b>\n\n"
        "🔮 <b>Maxfiy quti</b> - 50 ball\n"
        "• 10-100 ballgacha yutuq\n\n"
        "👑 <b>Oltin quti</b> - 100 ball\n"
        "• 50-500 ballgacha yutuq\n"
        "• 2x multiplikator\n\n"
        "💎 <b>Platina quti</b> - 200 ball\n"
        "• 100-1000 ballgacha yutuq\n"
        "• 3x multiplikator",
        reply_markup=get_boxes_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_box_"))
async def buy_box_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    box_type = callback.data.replace("buy_box_", "")
    price = BOX_PRICES.get(box_type, 0)
    
    if user.balance < price:
        await callback.answer(f"❌ Balansingiz yetarli emas! Kerak: {price} ball", show_alert=True)
        return
    
    success = await deduct_balance(session, user, price, f"{box_type} quti sotib olish")
    if not success:
        await callback.answer("❌ Xatolik!", show_alert=True)
        return
    
    box = UserBox(user_id=user.telegram_id, box_type=box_type)
    session.add(box)
    await session.commit()
    
    await callback.answer(f"✅ {box_type} quti sotib olindi!", show_alert=True)
    await boxes_menu_callback(callback)

@dp.callback_query(F.data == "my_boxes")
async def my_boxes_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    result = await session.execute(
        select(UserBox).where(
            UserBox.user_id == user.telegram_id,
            UserBox.is_opened == False
        )
    )
    boxes = result.scalars().all()
    
    if not boxes:
        await callback.message.edit_text(
            "📦 <b>Qutilaringiz</b>\n\n"
            "Sizda hozircha qutilar yo'q!\n"
            "🎁 Quti sotib olish uchun menyudan foydalaning.",
            reply_markup=get_boxes_menu()
        )
        return
    
    builder = InlineKeyboardBuilder()
    text = f"📦 <b>Qutilaringiz ({len(boxes)} ta)</b>\n\n"
    box_names = {"mystery": "🔮 Maxfiy", "golden": "👑 Oltin", "platinum": "💎 Platina"}
    
    for i, box in enumerate(boxes):
        text += f"{i+1}. {box_names.get(box.box_type)} quti\n"
        builder.row(
            InlineKeyboardButton(
                text=f"🎁 {box_names.get(box.box_type)} qutini ochish",
                callback_data=f"open_box_{box.id}"
            )
        )
    
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="boxes_menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("open_box_"))
async def open_user_box_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    box_id = int(callback.data.replace("open_box_", ""))
    result = await session.execute(
        select(UserBox).where(
            UserBox.id == box_id,
            UserBox.user_id == user.telegram_id,
            UserBox.is_opened == False
        )
    )
    box = result.scalar_one_or_none()
    
    if not box:
        await callback.answer("❌ Quti topilmadi!", show_alert=True)
        return
    
    reward = await open_box(session, user, box)
    box_names = {"mystery": "🔮 Maxfiy", "golden": "👑 Oltin", "platinum": "💎 Platina"}
    
    await callback.message.edit_text(
        f"🎉 <b>Quti ochildi!</b>\n\n"
        f"📦 Quti: {box_names.get(box.box_type)}\n"
        f"💰 Yutuq: <b>{reward:.0f} ball</b>\n\n"
        f"🎉 Tabriklaymiz!",
        reply_markup=get_boxes_menu()
    )
    await callback.answer(f"🎉 {reward:.0f} ball yutdingiz!", show_alert=True)

# Kunlik bonus
@dp.callback_query(F.data == "daily_bonus")
async def daily_bonus_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    result = await claim_daily_bonus(session, user)
    
    if result['success']:
        await callback.message.edit_text(
            f"🎁 <b>Kunlik Bonus</b>\n\n"
            f"✅ {result['message']}\n"
            f"💰 Bonus: {result['bonus']} ball\n"
            f"🔥 Streak: {result['streak']} kun\n"
            f"💵 Yangi balans: {user.balance:.0f} ball",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer(result['message'], show_alert=True)

# Referral
@dp.callback_query(F.data == "referral")
async def referral_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    result = await session.execute(
        select(func.count(Referral.id)).where(Referral.referrer_id == user.telegram_id)
    )
    referral_count = result.scalar()
    bot_info = await bot.me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user.telegram_id}"
    
    await callback.message.edit_text(
        f"👥 <b>Referral tizimi</b>\n\n"
        f"📎 Sizning havolangiz:\n"
        f"<code>{referral_link}</code>\n\n"
        f"👥 Referallar: <b>{referral_count} ta</b>\n"
        f"🎁 Har bir do'st uchun: <b>+5 ball</b>\n\n"
        f"📤 Do'stlaringizga ulashing va bonus oling!",
        reply_markup=get_referral_keyboard(user.telegram_id)
    )
    await callback.answer()

# Statistika
@dp.callback_query(F.data == "stats")
async def stats_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    result = await session.execute(
        select(func.count(GameHistory.id)).where(GameHistory.user_id == user.telegram_id)
    )
    total_games = result.scalar()
    
    result = await session.execute(
        select(func.count(GameHistory.id)).where(
            GameHistory.user_id == user.telegram_id,
            GameHistory.is_winner == True
        )
    )
    wins = result.scalar()
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    await callback.message.edit_text(
        f"📊 <b>Statistikangiz</b>\n\n"
        f"🎮 Jami o'yinlar: <b>{total_games}</b>\n"
        f"🏆 Yutuqlar: <b>{wins}</b>\n"
        f"📈 Yutuq foizi: <b>{win_rate:.1f}%</b>\n"
        f"💰 Joriy balans: <b>{user.balance:.0f} ball</b>\n"
        f"💵 Jami yig'ilgan: <b>{user.total_earned:.0f} ball</b>\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at.strftime('%d.%m.%Y')}",
        reply_markup=get_main_menu()
    )
    await callback.answer()

# Yutuqlar
@dp.callback_query(F.data == "achievements")
async def achievements_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    await check_achievements(session, user)
    
    result = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.telegram_id)
    )
    user_achievements = result.scalars().all()
    
    result = await session.execute(select(Achievement))
    all_achievements = result.scalars().all()
    
    achieved_ids = [ua.achievement_id for ua in user_achievements]
    
    text = "🏅 <b>Yutuqlaringiz</b>\n\n"
    for ach in all_achievements:
        status = "✅" if ach.id in achieved_ids else "🔒"
        text += f"{status} {ach.icon} <b>{ach.name}</b>\n"
        text += f"   {ach.description}\n"
        text += f"   Mukofot: {ach.reward} ball\n\n"
    
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()

# Promokod
@dp.callback_query(F.data == "gift_code")
async def gift_code_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎫 <b>Promokod kiritish</b>\n\n"
        "Iltimos, promokodingizni yozing yoki /promo buyrug'ini bering.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_promo_code)
    await callback.answer()

# Turnirlar
@dp.callback_query(F.data == "tournaments")
async def tournaments_callback(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(
        select(Tournament).where(Tournament.status == "upcoming")
    )
    tournaments = result.scalars().all()
    
    if not tournaments:
        await callback.message.edit_text(
            "🏆 <b>Turnirlar</b>\n\n"
            "Hozircha faol turnirlar yo'q.\n"
            "Tez orada yangi turnirlar qo'shiladi!",
            reply_markup=get_main_menu()
        )
        return
    
    builder = InlineKeyboardBuilder()
    text = "🏆 <b>Turnirlar</b>\n\n"
    
    for t in tournaments:
        text += f"📌 <b>{t.name}</b>\n"
        text += f"💰 Mukofot: {t.prize_pool} ball\n"
        text += f"🎫 Kirish: {t.entry_fee} ball\n"
        text += f"👥 Ishtirokchilar: {t.max_participants}\n\n"
        builder.row(
            InlineKeyboardButton(
                text=f"🏆 {t.name} - Qo'shilish",
                callback_data=f"join_tournament_{t.id}"
            )
        )
    
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

# Obuna tekshirish
@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery, user: User):
    is_subscribed = await check_subscription(bot, user.telegram_id, CHANNEL_ID)
    
    if is_subscribed:
        await callback.message.edit_text(
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            "Endi o'yin o'ynashingiz mumkin!",
            reply_markup=get_main_menu()
        )
        await callback.answer("✅ Muvaffaqiyatli!", show_alert=True)
    else:
        await callback.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)

# Yordam
@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "🎮 <b>O'yin:</b> 8 ta tugmadan birini tanlang, yutuqli sonni toping!\n"
        "🎁 <b>Qutilar:</b> Maxfiy, Oltin va Platina qutilar\n"
        "💰 <b>Balans:</b> /balance orqali ko'ring\n"
        "👥 <b>Referal:</b> Do'stlaringizni taklif qiling\n"
        "🎁 <b>Bonus:</b> Har kuni kunlik bonus oling\n"
        "🏆 <b>Turnirlar:</b> Musobaqalarda qatnashing\n"
        "🎫 <b>Promokod:</b> /promo orqali kod kiriting\n\n"
        "📞 Yordam uchun: @admin",
        reply_markup=get_main_menu()
    )
    await callback.answer()

# ==================== ADMIN HANDLERLARI ====================

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery, user: User):
    if user.telegram_id not in ADMIN_IDS and not user.is_admin:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await callback.message.edit_text(
        "👑 <b>Admin Panel</b>\n\n"
        "Kerakli amalni tanlang:",
        reply_markup=get_admin_panel()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.telegram_id not in ADMIN_IDS and not user.is_admin:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    
    stats = await get_bot_statistics(session)
    
    await callback.message.edit_text(
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"🎮 Bugungi o'yinlar: <b>{stats['today_games']}</b>\n"
        f"✅ Faol foydalanuvchilar: <b>{stats['active_users']}</b>",
        reply_markup=get_admin_panel()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_give_balance")
async def admin_give_balance_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💰 <b>Ball berish</b>\n\n"
        "Iltimos, foydalanuvchi ID sini kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.answer()

@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer(
            "💰 Ball miqdorini kiriting:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel")]
            ])
        )
        await state.set_state(AdminStates.waiting_for_amount)
    except:
        await message.answer("❌ Iltimos, to'g'ri ID kiriting!")

@dp.message(AdminStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        amount = float(message.text)
        data = await state.get_data()
        user_id = data['user_id']
        
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Foydalanuvchi topilmadi!")
        else:
            await add_balance(session, user, amount, "Admin tomonidan berildi")
            await message.answer(f"✅ {user.full_name} ga {amount} ball berildi!")
        
        await state.clear()
    except:
        await message.answer("❌ Iltimos, to'g'ri miqdor kiriting!")

@dp.callback_query(F.data == "admin_create_gift")
async def admin_create_gift_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎫 <b>Promokod yaratish</b>\n\n"
        "Kod miqdorini kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_gift_amount)
    await callback.answer()

@dp.message(AdminStates.waiting_for_gift_amount)
async def process_gift_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        await state.update_data(gift_amount=amount)
        await message.answer(
            "Foydalanish sonini kiriting:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel")]
            ])
        )
        await state.set_state(AdminStates.waiting_for_gift_uses)
    except:
        await message.answer("❌ Iltimos, to'g'ri miqdor kiriting!")

@dp.message(AdminStates.waiting_for_gift_uses)
async def process_gift_uses(message: Message, state: FSMContext, session: AsyncSession):
    try:
        max_uses = int(message.text)
        data = await state.get_data()
        amount = data['gift_amount']
        user_id = message.from_user.id
        
        code = await create_gift_code(session, user_id, amount, max_uses)
        
        await message.answer(
            f"✅ <b>Promokod yaratildi!</b>\n\n"
            f"🎫 Kod: <code>{code}</code>\n"
            f"💰 Miqdor: {amount} ball\n"
            f"👥 Foydalanish: {max_uses} marta\n\n"
            f"📤 Ushbu kodni foydalanuvchilarga tarqating!",
            reply_markup=get_admin_panel()
        )
        await state.clear()
    except:
        await message.answer("❌ Iltimos, to'g'ri son kiriting!")

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📢 <b>Xabar yuborish</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    result = await session.execute(select(User.telegram_id))
    users = result.scalars().all()
    
    sent = 0
    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    
    await message.answer(
        f"✅ Xabar {sent}/{len(users)} foydalanuvchiga yuborildi!",
        reply_markup=get_admin_panel()
    )
    await state.clear()

# ==================== ASOSIY FUNKSIYA ====================

async def main():
    """Botni ishga tushirish"""
    logger.info("🔧 Ma'lumotlar bazasi yaratilmoqda...")
    await init_db()
    logger.info("✅ Ma'lumotlar bazasi tayyor!")
    logger.info("🤖 Bot ishga tushmoqda...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot xatosi: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi!")
    except Exception as e:
        logger.error(f"Kutilmagan xato: {e}")