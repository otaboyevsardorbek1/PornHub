# handlers/start.py
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import config
router = Router()

class StartStates(StatesGroup):
    waiting_terms = State()

@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext):
    user_id = str(message.chat.id)
    
    # Check if user exists
    try:
        with open("users.txt", "r") as f:
            users = f.read().splitlines()
        if user_id not in users:
            with open("users.txt", "a") as f:
                f.write(user_id + "\n")
    except:
        with open("users.txt", "w") as f:
            f.write(user_id + "\n")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="• Channel •", url=f"https://t.me/{config.SUB_CHAT}")],
        [InlineKeyboardButton(text="Terms of use & Privacy", callback_data="terms")]
    ])
    
    text = f"👋🏻 Hi {message.from_user.first_name}!\n\nUse this bot to download videos from the pornhub.com site by providing the name of the video you want to download or you can also search for the video you want to download via inline mode.\n\n💭 Join the redirected channel in order to use this bot!"
    
    await message.reply(text, reply_markup=kb)

@router.callback_query(F.data == "terms")
async def terms_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Read the terms of use & user privacy!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Agree & Continue", callback_data="final_page")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="home_intro")]
    ])
    
    text = """
🧸 <u><b>PornHub bot</b></u>
⚠️ <b>WARNING !</b>
This bot contains 18+ content, make sure you are an adult user to be able to use this bot!. Reporting this bot will get it blocked by Telegram, so if you're considering sticking with bots, don't do it!
🔐 <b>Privacy Policy</b>
We ensure that your search data in this bot is protected safely.  Whoever you are, whenever and wherever you use this bot to download videos from pornhub, you don't have to be afraid of spreading it to the public.
<i>You don't have to worry, because our bot staff will make sure that your data is well protected and safe.</i>
👉🏻 Press the <b>green button</b> to declare that you have <b>read and accepted these conditions</b> to use the bot, otherwise cancel.
    """
    
    await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "final_page")
async def final_page(callback: CallbackQuery):
    await callback.answer("Thanks for agreeing to the bot policy!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Search here", switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text="Search in chat", switch_inline_query="")]
    ])
    
    await callback.message.edit_text(
        f"Hi {callback.from_user.first_name}!\n\nYou can browse this bot now, just tap one of the button below and enter any name of the video you want to download.",
        reply_markup=kb
    )
