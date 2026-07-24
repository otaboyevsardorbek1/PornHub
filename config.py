
"""
Content Bot - Konfiguratsiya
Xavfsizlik uchun .env fayldan o'qiydi
"""
import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# .env faylni yuklash
load_dotenv()


@dataclass
class Config:
    """Bot konfiguratsiyasi - barcha maxfiy ma'lumotlar .env dan"""

    # Telegram
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    API_ID: int = field(default_factory=lambda: int(os.getenv("API_ID", "0")))
    API_HASH: str = field(default_factory=lambda: os.getenv("API_HASH", ""))

    # Admin
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ])
    LOG_CHAT_ID: int = field(default_factory=lambda: int(os.getenv("LOG_CHAT_ID", "0")))

    # Kanal
    REQUIRED_CHANNEL: str = field(default_factory=lambda: os.getenv("REQUIRED_CHANNEL", ""))

    # Database
    DATABASE_PATH: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "data/content_database.db"))

    # Xavfsizlik
    ENCRYPTION_KEY: str = field(default_factory=lambda: os.getenv("ENCRYPTION_KEY", ""))

    # Limitlar
    DAILY_DOWNLOAD_LIMIT_FREE: int = field(default_factory=lambda: int(os.getenv("DAILY_DOWNLOAD_LIMIT_FREE", "5")))
    DAILY_DOWNLOAD_LIMIT_PREMIUM: int = field(default_factory=lambda: int(os.getenv("DAILY_DOWNLOAD_LIMIT_PREMIUM", "50")))
    INLINE_SEARCH_LIMIT_FREE: int = field(default_factory=lambda: int(os.getenv("INLINE_SEARCH_LIMIT_FREE", "20")))
    INLINE_SEARCH_LIMIT_PREMIUM: int = field(default_factory=lambda: int(os.getenv("INLINE_SEARCH_LIMIT_PREMIUM", "100")))

    # To'lov - Provider (Click/Stripe)
    PAYMENT_PROVIDER_TOKEN: str = field(default_factory=lambda: os.getenv("PAYMENT_PROVIDER_TOKEN", ""))

    # Premium narxlari (so'm)
    PREMIUM_PRICE_MONTHLY: int = field(default_factory=lambda: int(os.getenv("PREMIUM_PRICE_MONTHLY", "50000")))
    PREMIUM_PRICE_QUARTERLY: int = field(default_factory=lambda: int(os.getenv("PREMIUM_PRICE_QUARTERLY", "130000")))
    PREMIUM_PRICE_YEARLY: int = field(default_factory=lambda: int(os.getenv("PREMIUM_PRICE_YEARLY", "450000")))

    # Bot sozlamalari
    PREFIXES: List[str] = field(default_factory=lambda: ["/", "!", ".", "$", "-"])

    def validate(self) -> bool:
        """Konfiguratsiyani tekshirish"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN ko'rsatilmagan!")
        if not self.ADMIN_IDS:
            raise ValueError("ADMIN_IDS ko'rsatilmagan!")
        return True


# Global konfiguratsiya obyekti
config = Config()
