import sqlite3
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class Database:
    """SQLite ma'lumotlar bazasi - xxx_contend.py bilan mos"""

    def __init__(self, db_path: str = "data/content_database.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_tables()
        self._create_indexes()
        self._init_payment_tables()

    def _init_tables(self) -> None:
        """Jadvallarni yaratish (xxx_contend.py dan)"""
        with self.lock:
            c = self.conn.cursor()

            # Asosiy jadvallar (xxx_contend.py dan)
            c.execute("""CREATE TABLE IF NOT EXISTS videos (
                id TEXT, platform TEXT DEFAULT '', title TEXT DEFAULT '', 
                url TEXT DEFAULT '', thumbnail TEXT DEFAULT '', 
                duration TEXT DEFAULT '', views TEXT DEFAULT '',
                rating TEXT DEFAULT '', date_added TEXT DEFAULT '', 
                category TEXT DEFAULT '', tags TEXT DEFAULT '[]', 
                models TEXT DEFAULT '[]', video_urls TEXT DEFAULT '[]',
                is_premium INTEGER DEFAULT 0, 
                has_russian_audio INTEGER DEFAULT 0,
                description TEXT DEFAULT '', likes TEXT DEFAULT '', 
                dislikes TEXT DEFAULT '', download_links TEXT DEFAULT '[]', 
                comments_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
                PRIMARY KEY (id, platform))""")

            c.execute("""CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', title TEXT DEFAULT '', 
                url TEXT UNIQUE, video_count TEXT DEFAULT '0',
                image TEXT DEFAULT '', letter TEXT DEFAULT '', 
                group_name TEXT DEFAULT '', created_at TEXT DEFAULT '')""")

            c.execute("""CREATE TABLE IF NOT EXISTS photos (
                id TEXT, platform TEXT DEFAULT '', title TEXT DEFAULT '', 
                url TEXT DEFAULT '', thumbnail TEXT DEFAULT '', 
                date TEXT DEFAULT '', views TEXT DEFAULT '',
                photo_count TEXT DEFAULT '', rating TEXT DEFAULT '', 
                likes TEXT DEFAULT '', studio TEXT DEFAULT '', 
                models TEXT DEFAULT '[]', created_at TEXT DEFAULT '',
                PRIMARY KEY (id, platform))""")

            c.execute("""CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', name TEXT DEFAULT '', 
                url TEXT UNIQUE, image TEXT DEFAULT '',
                country TEXT DEFAULT '', video_count TEXT DEFAULT '',
                rating TEXT DEFAULT '', created_at TEXT DEFAULT '')""")

            c.execute("""CREATE TABLE IF NOT EXISTS studios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', name TEXT DEFAULT '', 
                url TEXT UNIQUE, image TEXT DEFAULT '',
                video_count TEXT DEFAULT '', created_at TEXT DEFAULT '')""")

            # Bot uchun qo'shimcha jadvallar
            c.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT DEFAULT '',
                daily_downloads INTEGER DEFAULT 0,
                last_download_date TEXT DEFAULT '',
                agreed_terms INTEGER DEFAULT 0,
                agreed_at TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                last_activity TEXT DEFAULT '')""")

            c.execute("""CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                video_id TEXT,
                platform TEXT,
                downloaded_at TEXT DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users(user_id))""")

            c.execute("""CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                results_count INTEGER DEFAULT 0,
                searched_at TEXT DEFAULT '')""")

            c.execute("""CREATE TABLE IF NOT EXISTS bot_stats (
                date TEXT PRIMARY KEY,
                total_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                total_searches INTEGER DEFAULT 0,
                premium_users INTEGER DEFAULT 0,
                revenue INTEGER DEFAULT 0)""")

            self.conn.commit()

    def _create_indexes(self) -> None:
        """Indekslarni yaratish"""
        with self.lock:
            c = self.conn.cursor()
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_v_platform ON videos(platform)',
                'CREATE INDEX IF NOT EXISTS idx_v_title ON videos(title)',
                'CREATE INDEX IF NOT EXISTS idx_v_category ON videos(category)',
                'CREATE INDEX IF NOT EXISTS idx_v_premium ON videos(is_premium)',
                'CREATE INDEX IF NOT EXISTS idx_v_created ON videos(created_at)',
                'CREATE INDEX IF NOT EXISTS idx_users_premium ON users(is_premium)',
                'CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id)',
                'CREATE INDEX IF NOT EXISTS idx_search_user ON search_history(user_id)',
            ]
            for idx in indexes:
                try:
                    c.execute(idx)
                except:
                    pass
            self.conn.commit()

    # ============ VIDEO METODLARI ============

    def search_videos(self, query: str, platform: Optional[str] = None,
                      category: Optional[str] = None,
                      is_premium: Optional[bool] = None,
                      limit: int = 50, offset: int = 0) -> Tuple[List[Dict], int]:
        """Video qidirish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                conditions = ["(title LIKE ? OR category LIKE ? OR tags LIKE ?)"]
                params = [f"%{query}%"] * 3

                if platform:
                    conditions.append("platform=?")
                    params.append(platform)
                if category:
                    conditions.append("category=?")
                    params.append(category)
                if is_premium is not None:
                    conditions.append("is_premium=?")
                    params.append(f"{1 if is_premium else 0}")

                where_clause = " AND ".join(conditions)

                # Umumiy soni
                c.execute(f"SELECT COUNT(*) FROM videos WHERE {where_clause}", params)
                total = c.fetchone()[0]

                # Natijalar
                sql = f"""SELECT * FROM videos 
                    WHERE {where_clause} 
                    ORDER BY 
                        CASE WHEN title LIKE ? THEN 0 ELSE 1 END,
                        CAST(REPLACE(views, " ", "") AS INTEGER) DESC
                    LIMIT ? OFFSET ?"""
                params.extend([f"%{query}%", f"{limit}", f"{offset}"])
                c.execute(sql, params)

                results = []
                for row in c.fetchall():
                    video = dict(row)
                    for field in ["tags", "models", "video_urls", "download_links"]:
                        try:
                            video[field] = json.loads(video.get(field, "[]"))
                        except:
                            video[field] = []
                    results.append(video)

                return results, total
        except Exception as e:
            print(f"Search error: {e}")
            return [], 0

    def get_video_by_id(self, video_id: str, platform: str) -> Optional[Dict]:
        """ID bo'yicha video olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute("SELECT * FROM videos WHERE id=? AND platform=?", (video_id, platform))
                row = c.fetchone()
                if row:
                    video = dict(row)
                    for field in ["tags", "models", "video_urls", "download_links"]:
                        try:
                            video[field] = json.loads(video.get(field, "[]"))
                        except:
                            video[field] = []
                    return video
                return None
        except Exception as e:
            print(f"Get video error: {e}")
            return None

    def get_top_videos(self, limit: int = 20, platform: Optional[str] = None) -> List[Dict]:
        """Top videolar"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute("""SELECT * FROM videos 
                        WHERE platform=? AND views!="" 
                        ORDER BY CAST(REPLACE(views, " ", "") AS INTEGER) DESC LIMIT ?""", 
                        (platform, limit))
                else:
                    c.execute("""SELECT * FROM videos 
                        WHERE views!="" 
                        ORDER BY CAST(REPLACE(views, " ", "") AS INTEGER) DESC LIMIT ?""", 
                        (limit,))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Top videos error: {e}")
            return []

    def get_categories(self, platform: Optional[str] = None) -> List[Dict]:
        """Kategoriyalarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute("SELECT * FROM categories WHERE platform=? ORDER BY title", (platform,))
                else:
                    c.execute("SELECT * FROM categories ORDER BY title")
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Categories error: {e}")
            return []

    def get_models(self, platform: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Modellarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute("SELECT * FROM models WHERE platform=? ORDER BY name LIMIT ?", (platform, limit))
                else:
                    c.execute("SELECT * FROM models ORDER BY name LIMIT ?", (limit,))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Models error: {e}")
            return []

    def get_studios(self, platform: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Studiyalarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute("SELECT * FROM studios WHERE platform=? ORDER BY name LIMIT ?", (platform, limit))
                else:
                    c.execute("SELECT * FROM studios ORDER BY name LIMIT ?", (limit,))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Studios error: {e}")
            return []

    def get_stats(self) -> Dict:
        """Umumiy statistika"""
        try:
            with self.lock:
                c = self.conn.cursor()
                stats = {}

                tables = ["videos", "categories", "photos", "models", "studios"]
                for t in tables:
                    c.execute(f"SELECT COUNT(*) FROM {t}")
                    stats[f"total_{t}"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM users")
                stats["total_users"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
                stats["premium_users"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM downloads")
                stats["total_downloads"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM search_history")
                stats["total_searches"] = c.fetchone()[0]

                c.execute("SELECT platform, COUNT(*) FROM videos GROUP BY platform")
                stats["by_platform"] = dict(c.fetchall())

                return stats
        except Exception as e:
            print(f"Stats error: {e}")
            return {}

    # ============ USER METODLARI ============

    def add_user(self, user_id: int, username: str = "", first_name: str = "", 
                 last_name: str = "") -> bool:
        """Foydalanuvchi qo'shish"""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                c = self.conn.cursor()
                c.execute("""INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, last_name, created_at, last_activity)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, username, first_name, last_name, now, now))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Add user error: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Foydalanuvchini olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
                row = c.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Get user error: {e}")
            return None

    def agree_terms(self, user_id: int) -> bool:
        """Foydalanuvchi shartlarga rozi bo'ldi"""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                c = self.conn.cursor()
                c.execute("""UPDATE users SET agreed_terms=1, agreed_at=? 
                    WHERE user_id=?""", (now, user_id))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Agree terms error: {e}")
            return False

    def check_terms_agreed(self, user_id: int) -> bool:
        """Foydalanuvchi shartlarga rozi bo'lganmi"""
        try:
            user = self.get_user(user_id)
            return user is not None and user.get("agreed_terms", 0) == 1
        except:
            return False

    def is_premium(self, user_id: int) -> bool:
        """Premium tekshirish"""
        try:
            user = self.get_user(user_id)
            if not user or not user.get("is_premium", 0):
                return False
            premium_until = user.get("premium_until", "")
            if premium_until:
                return datetime.now().isoformat() < premium_until
            return False
        except:
            return False

    def set_premium(self, user_id: int, days: int = 30) -> bool:
        """Premium o'rnatish"""
        try:
            with self.lock:
                premium_until = (datetime.now() + timedelta(days=days)).isoformat()
                c = self.conn.cursor()
                c.execute("""UPDATE users SET is_premium=1, premium_until=? 
                    WHERE user_id=?""", (premium_until, user_id))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Set premium error: {e}")
            return False

    def check_download_limit(self, user_id: int, free_limit: int = 5, 
                              premium_limit: int = 50) -> Tuple[bool, int, int]:
        """Yuklab olish limitini tekshirish (qolgan, limit)"""
        try:
            user = self.get_user(user_id)
            if not user:
                return False, 0, free_limit

            today = datetime.now().strftime("%Y-%m-%d")
            last_date = user.get("last_download_date", "")
            daily_downloads = user.get("daily_downloads", 0)

            # Yangi kun - limitni yangilash
            if last_date != today:
                with self.lock:
                    c = self.conn.cursor()
                    c.execute("""UPDATE users SET daily_downloads=0, last_download_date=? 
                        WHERE user_id=?""", (today, user_id))
                    self.conn.commit()
                daily_downloads = 0

            limit = premium_limit if self.is_premium(user_id) else free_limit
            remaining = limit - daily_downloads

            return remaining > 0, remaining, limit
        except Exception as e:
            print(f"Check limit error: {e}")
            return False, 0, free_limit

    def increment_download(self, user_id: int) -> bool:
        """Yuklab olish sonini oshirish"""
        try:
            with self.lock:
                today = datetime.now().strftime("%Y-%m-%d")
                c = self.conn.cursor()
                c.execute("""UPDATE users SET daily_downloads=daily_downloads+1, 
                    last_download_date=? WHERE user_id=?""", (today, user_id))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Increment download error: {e}")
            return False

    def log_download(self, user_id: int, video_id: str, platform: str) -> bool:
        """Yuklab olishni loglash"""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                c = self.conn.cursor()
                c.execute("""INSERT INTO downloads (user_id, video_id, platform, downloaded_at)
                    VALUES (?, ?, ?, ?)""", (user_id, video_id, platform, now))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Log download error: {e}")
            return False

    def log_search(self, user_id: int, query: str, results_count: int = 0) -> bool:
        """Qidiruvni loglash"""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                c = self.conn.cursor()
                c.execute("""INSERT INTO search_history (user_id, query, results_count, searched_at)
                    VALUES (?, ?, ?, ?)""", (user_id, query, results_count, now))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Log search error: {e}")
            return False

    def get_all_users(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """Barcha foydalanuvchilar"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                         (limit, offset))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Get users error: {e}")
            return []

    def get_user_stats(self, user_id: int) -> Dict:
        """Foydalanuvchi statistikasi"""
        try:
            with self.lock:
                c = self.conn.cursor()

                c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=?", (user_id,))
                total_downloads = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM search_history WHERE user_id=?", (user_id,))
                total_searches = c.fetchone()[0]

                c.execute("""SELECT COUNT(*) FROM downloads 
                    WHERE user_id=? AND downloaded_at >= date("now", "start of month")""", (user_id,))
                monthly_downloads = c.fetchone()[0]

                return {
                    "total_downloads": total_downloads,
                    "total_searches": total_searches,
                    "monthly_downloads": monthly_downloads
                }
        except Exception as e:
            print(f"User stats error: {e}")
            return {}

    def get_recent_downloads(self, user_id: int, limit: int = 10) -> List[Dict]:
        """So'nggi yuklab olishlar"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute("""SELECT d.*, v.title, v.thumbnail, v.platform 
                    FROM downloads d
                    LEFT JOIN videos v ON d.video_id = v.id AND d.platform = v.platform
                    WHERE d.user_id=? ORDER BY d.downloaded_at DESC LIMIT ?""",
                    (user_id, limit))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Recent downloads error: {e}")
            return []



    # ============ TO'LOV METODLARI (payments.py uchun) ============

    def _init_payment_tables(self) -> None:
        """To'lov jadvallarini yaratish"""
        with self.lock:
            c = self.conn.cursor()

            c.execute("""CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan TEXT DEFAULT '',
                days INTEGER DEFAULT 0,
                amount INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'UZS',
                transaction_id TEXT DEFAULT '',
                provider_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                payment_type TEXT DEFAULT 'provider',
                created_at TEXT DEFAULT '',
                completed_at TEXT DEFAULT '')""")

            c.execute("""CREATE TABLE IF NOT EXISTS premium_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT DEFAULT '',
                plan TEXT DEFAULT '',
                days INTEGER DEFAULT 0,
                admin_id INTEGER DEFAULT 0,
                created_at TEXT DEFAULT '')""")

            self.conn.commit()

    def log_payment(self, user_id: int, plan: str, amount: int, 
                    currency: str, transaction_id: str, 
                    provider_id: str = "", status: str = "completed",
                    payment_type: str = "provider") -> bool:
        """To'lovni loglash"""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                c = self.conn.cursor()

                # Plan kunlarini olish
                plan_days = {
                    "monthly": 30,
                    "quarterly": 90,
                    "yearly": 365
                }
                days = plan_days.get(plan, 30)

                c.execute("""INSERT INTO payments 
                    (user_id, plan, days, amount, currency, transaction_id, 
                     provider_id, status, payment_type, created_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, plan, days, amount, currency, transaction_id,
                     provider_id, status, payment_type, now, now))

                # Premium log
                c.execute("""INSERT INTO premium_logs 
                    (user_id, action, plan, days, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (user_id, "purchase", plan, days, now))

                self.conn.commit()
                return True
        except Exception as e:
            print(f"Log payment error: {e}")
            return False

    def get_user_payments(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Foydalanuvchi to'lovlari"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute("""SELECT * FROM payments 
                    WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
                    (user_id, limit))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            print(f"Get user payments error: {e}")
            return []

    def get_payment_stats(self) -> Dict:
        """To'lov statistikasi"""
        try:
            with self.lock:
                c = self.conn.cursor()
                stats = {}

                c.execute("SELECT COUNT(*) FROM payments")
                stats["total_payments"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM payments WHERE status='completed'")
                stats["completed"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM payments WHERE status='cancelled'")
                stats["cancelled"] = c.fetchone()[0]

                c.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE currency='XTR' AND status='completed'")
                stats["total_stars"] = c.fetchone()[0]

                c.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE currency='UZS' AND status='completed'")
                stats["total_uzs"] = c.fetchone()[0]

                c.execute("SELECT COUNT(DISTINCT user_id) FROM payments WHERE status='completed'")
                stats["unique_users"] = c.fetchone()[0]

                c.execute("""SELECT COUNT(*) FROM payments 
                    WHERE created_at >= date('now', '-7 days') AND status='completed'""")
                stats["last_7_days"] = c.fetchone()[0]

                c.execute("""SELECT COUNT(*) FROM payments 
                    WHERE created_at >= date('now', '-30 days') AND status='completed'""")
                stats["last_30_days"] = c.fetchone()[0]

                return stats
        except Exception as e:
            print(f"Payment stats error: {e}")
            return {}

    def refund_payment(self, transaction_id: str) -> bool:
        """To'lovni qaytarish (statusni yangilash)"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute("""UPDATE payments SET status='refunded' 
                    WHERE transaction_id=?""", (transaction_id,))
                self.conn.commit()
                return c.rowcount > 0
        except Exception as e:
            print(f"Refund error: {e}")
            return False

    def close(self):
        """Bazani yopish"""
        self.conn.close()
