# config.py
import os
from typing import List
from dataclasses import dataclass
from aiogram.fsm.storage.memory import MemoryStorage

@dataclass
class Config:
    API_ID: int = 27101576
    API_HASH: str = "3ac0f0d7295febcfd5391149930e43c0"
    TOKEN: str = "6848099784:AAHGpAKp_ddCRSVk9XNxTXlcwf1d52pVEjg"
    
    LOG_CHAT: int = 6646928202
    SUB_CHAT: str = "@prodevuzoff"
    SUDOERS: List[int] = [6646928202]
    PREFIXES: List[str] = ["/", "!", ".", "$", "-"]

config = Config()
