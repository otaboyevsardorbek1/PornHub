# handlers/admin.py
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from config import config

def is_sudo(user_id: int) -> bool:
    return user_id in config.SUDOERS

router = Router()

@router.message(Command("stats"), F.chat.type == "private")
async def stats_handler(message: Message):
    if not is_sudo(message.from_user.id):
        return
    
    try:
        with open("users.txt", "r") as f:
            users = f.readlines()
        total = len(users)
        await message.answer_document(
            document="users.txt",
            caption=f"Total: {total} users"
        )
    except Exception as e:
        await message.answer("Error reading users file")

@router.message(Command("gcast", "broadcast"), F.chat.type == "private")
async def broadcast_handler(message: Message):
    if not is_sudo(message.from_user.id):
        return
    
    if not message.reply_to_message:
        await message.reply("Reply to message for broadcast!")
        return
    
    if message.reply_to_message.text:
        await message.reply("✅ Broadcast started!")
        
        try:
            with open("users.txt", "r") as f:
                users = f.readlines()
            
            success = 0
            for user_id in users:
                try:
                    await message.reply_to_message.copy(int(user_id.strip()))
                    success += 1
                except:
                    continue
            
            await message.reply(f"✅ Broadcast completed! Sent to {success}/{len(users)} users")
        except Exception as e:
            await message.reply(f"❌ Broadcast failed: {e}")
    else:
        await message.reply("Only text messages are supported for broadcast!")
