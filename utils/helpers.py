
"""
Content Bot - Yordamchi funksiyalar
"""
import re
import html
from typing import Optional
from datetime import datetime


def escape_html(text: Optional[str]) -> str:
    """HTML ni xavfsiz qilish"""
    if not text:
        return ""
    return html.escape(str(text))


def truncate_text(text: str, max_length: int = 100) -> str:
    """Matnni qisqartirish"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_duration(duration: str) -> str:
    """Davomiylikni formatlash"""
    if not duration:
        return "N/A"
    return duration


def format_views(views: str) -> str:
    """Ko'rishlar sonini formatlash"""
    if not views:
        return "0"
    # Bo'sh joylarni olib tashlash
    views = views.replace(" ", "").replace("\u2009", "").replace("\u00A0", "")
    try:
        num = int(views)
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)
    except:
        return views


def format_date(date_str: str) -> str:
    """Sana formatlash"""
    if not date_str:
        return "N/A"
    return date_str


def create_video_caption(video: dict, show_details: bool = True) -> str:
    """Video caption yaratish"""
    title = escape_html(video.get("title", "Nomsiz"))
    platform = video.get("platform", "N/A")
    duration = format_duration(video.get("duration", ""))
    views = format_views(video.get("views", ""))
    rating = video.get("rating", "N/A")
    category = escape_html(video.get("category", ""))
    is_premium = video.get("is_premium", 0)
    has_russian = video.get("has_russian_audio", 0)

    caption = f"🎬 <b>{title}</b>\n"
    caption += f"📺 Platforma: <code>{platform}</code>\n"

    if duration and duration != "N/A":
        caption += f"⏱ Davomiylik: <code>{duration}</code>\n"
    if views and views != "0":
        caption += f"👁 Ko'rishlar: <code>{views}</code>\n"
    if rating and rating != "N/A":
        caption += f"⭐ Reyting: <code>{rating}</code>\n"
    if category:
        caption += f"📂 Kategoriya: <code>{category}</code>\n"

    badges = []
    if is_premium:
        badges.append("💎 Premium")
    if has_russian:
        badges.append("🇷🇺 Rus tilida")

    if badges:
        caption += f"🏷 {', '.join(badges)}\n"

    if show_details:
        tags = video.get("tags", [])
        if tags and len(tags) > 0:
            tags_str = ", ".join([escape_html(t) for t in tags[:5]])
            caption += f"\n🏷 Teglar: <i>{tags_str}</i>"

        models = video.get("models", [])
        if models and len(models) > 0:
            models_str = ", ".join([escape_html(m) for m in models[:3]])
            caption += f"\n👤 Modellar: <i>{models_str}</i>"

    return caption


def is_valid_video_id(video_id: str) -> bool:
    """Video ID validatsiyasi"""
    if not video_id:
        return False
    # Faqat harflar, raqamlar, tire va pastki chiziq
    return bool(re.match(r"^[\w\-]+$", str(video_id)))


def sanitize_query(query: str) -> str:
    """Qidiruv so'rovini tozalash"""
    if not query:
        return ""
    # Maxsus belgilarni olib tashlash
    query = re.sub(r"[<>'\";]", "", query)
    return query.strip()[:100]  # Maksimal 100 ta belgi


def humanbytes(size: int | float) -> str:
    """Baytlarni inson o'qiydigan formatga"""
    if not size:
        return "0 B"
    power = 2 ** 10
    n = 0
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    while size > power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.1f} {units[n]}"


def get_greeting() -> str:
    """Kun vaqti bo'yicha salomlashish"""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "🌅 Xayrli tong"
    elif 12 <= hour < 17:
        return "☀️ Xayrli kun"
    elif 17 <= hour < 22:
        return "🌆 Xayrli kech"
    else:
        return "🌙 Xayrli tun"


def format_number(num: int) -> str:
    """Sonni formatlash"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)
