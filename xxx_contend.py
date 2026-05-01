#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  XXX CONTENT COLLECTOR - Ultimate Pro v9.0 - FINAL EDITION         ║
║  3 platforma • SQLite • To'liq tafsilotlar • Eksport • CLI         ║
╚══════════════════════════════════════════════════════════════════════╝
"""
#1-app=[
import requests
from bs4 import BeautifulSoup
import json
import time
import csv
import sqlite3
import hashlib
import logging
import threading
import argparse
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Union 
from pathlib import Path
from abc import ABC, abstractmethod

# ==================== GLOBAL LOGGER ====================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Logging tizimini sozlash"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger('XXXCollector')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    
    # Fayl handler
    fh = logging.FileHandler(
        log_dir / f'collector_{datetime.now():%Y%m%d}.log', 
        encoding='utf-8'
    )
    fh.setLevel(logging.DEBUG)
    
    # Konsol handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', 
        datefmt='%H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

# ==================== KONFIGURATSIYA ====================

@dataclass
class Config:
    """Dastur konfiguratsiyasi"""
    db_path: str = 'data/xxx_collector.db'
    max_workers: int = 5
    request_delay: float = 0.5
    max_retries: int = 3
    timeout: int = 30
    platforms: List[str] = field(default_factory=lambda: ['lat', 'best', '5ru'])
    export_dir: str = 'exports'
    backup_dir: str = 'backups'
    auto_backup: bool = False
    log_level: str = 'INFO'
    collect_details: bool = True
    collect_photos: bool = True
    collect_models: bool = True
    collect_studios: bool = True
    max_detail_videos: int = 10
    
    @classmethod
    def from_file(cls, path: str = 'config.json') -> 'Config':
        """JSON fayldan konfiguratsiyani yuklash"""
        if Path(path).exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()
    
    def save(self, path: str = 'config.json') -> None:
        """Konfiguratsiyani JSON faylga saqlash"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._asdict(), f, indent=2, ensure_ascii=False)
    
    def _asdict(self) -> dict:
        """Dataclass ni dict ga o'girish"""
        result = {}
        for k in self.__dataclass_fields__:
            result[k] = getattr(self, k)
        return result

# ==================== MA'LUMOTLAR BAZASI (KENGAYTIRILGAN) ====================

class Database:
    """SQLite ma'lumotlar bazasi boshqaruvi - KENGAYTIRILGAN VERSIYA"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_tables()
        self._create_indexes()
        self._check_database_status()
        logger.info(f"Database: {db_path}")
    
    # ============ BAZA HOLATI VA INIT ============
    
    def _check_database_status(self) -> None:
        """Baza holatini tekshirish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                tables = {
                    'videos': 0, 'categories': 0, 'photos': 0,
                    'models': 0, 'studios': 0, 'video_details': 0
                }
                for table in tables:
                    try:
                        c.execute(f'SELECT COUNT(*) FROM {table}')
                        tables[table] = c.fetchone()[0]
                    except:
                        pass
                
                status_msg = "📊 Baza holati: " + ", ".join(f"{k}={v}" for k, v in tables.items())
                logger.info(status_msg)
                
                if tables['videos'] == 0:
                    logger.warning("⚠️  Videolar jadvali BO'SH! Ma'lumot yig'ish kerak.")
                    print("\n⚠️  DIQQAT: Ma'lumotlar bazasi bo'sh!")
                    print("   Eksport qilishdan oldin ma'lumot yig'ing:")
                    print("   python collector.py --collect all --pages 3")
                    print("   yoki interaktiv menyuda 1-4 tanlang.\n")
        except Exception as e:
            logger.error(f"Baza holatini tekshirishda xatolik: {e}")
    
    def _init_tables(self) -> None:
        """Jadvallarni yaratish"""
        with self.lock:
            c = self.conn.cursor()
            
            c.execute('''CREATE TABLE IF NOT EXISTS videos (
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
                PRIMARY KEY (id, platform))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', title TEXT DEFAULT '', 
                url TEXT UNIQUE, video_count TEXT DEFAULT '0',
                image TEXT DEFAULT '', letter TEXT DEFAULT '', 
                group_name TEXT DEFAULT '', created_at TEXT DEFAULT '')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS photos (
                id TEXT, platform TEXT DEFAULT '', title TEXT DEFAULT '', 
                url TEXT DEFAULT '', thumbnail TEXT DEFAULT '', 
                date TEXT DEFAULT '', views TEXT DEFAULT '',
                photo_count TEXT DEFAULT '', rating TEXT DEFAULT '', 
                likes TEXT DEFAULT '', studio TEXT DEFAULT '', 
                models TEXT DEFAULT '[]', created_at TEXT DEFAULT '',
                PRIMARY KEY (id, platform))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', name TEXT DEFAULT '', 
                url TEXT UNIQUE, image TEXT DEFAULT '',
                country TEXT DEFAULT '', video_count TEXT DEFAULT '',
                rating TEXT DEFAULT '', created_at TEXT DEFAULT '')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS studios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', name TEXT DEFAULT '', 
                url TEXT UNIQUE, image TEXT DEFAULT '',
                video_count TEXT DEFAULT '', created_at TEXT DEFAULT '')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS video_details (
                video_id TEXT, platform TEXT DEFAULT '',
                description TEXT DEFAULT '', likes TEXT DEFAULT '', 
                dislikes TEXT DEFAULT '', download_links TEXT DEFAULT '[]', 
                comments TEXT DEFAULT '[]', related_videos TEXT DEFAULT '[]', 
                tags TEXT DEFAULT '[]', models TEXT DEFAULT '[]', 
                full_views TEXT DEFAULT '',
                created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
                PRIMARY KEY (video_id, platform))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS parse_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                platform TEXT DEFAULT '', action TEXT DEFAULT '', 
                items_count INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0, 
                duration_seconds REAL DEFAULT 0,
                created_at TEXT DEFAULT '')''')
            
            self.conn.commit()
    
    def _create_indexes(self) -> None:
        """Indekslarni yaratish"""
        with self.lock:
            c = self.conn.cursor()
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_v_platform ON videos(platform)',
                'CREATE INDEX IF NOT EXISTS idx_v_created ON videos(created_at)',
                'CREATE INDEX IF NOT EXISTS idx_v_views ON videos(views)',
                'CREATE INDEX IF NOT EXISTS idx_v_category ON videos(category)',
                'CREATE INDEX IF NOT EXISTS idx_v_rating ON videos(rating)',
                'CREATE INDEX IF NOT EXISTS idx_cat_url ON categories(url)',
                'CREATE INDEX IF NOT EXISTS idx_models_url ON models(url)',
                'CREATE INDEX IF NOT EXISTS idx_studios_url ON studios(url)',
                'CREATE INDEX IF NOT EXISTS idx_vd_video_id ON video_details(video_id)',
            ]
            for idx in indexes:
                try:
                    c.execute(idx)
                except:
                    pass
            self.conn.commit()
    
    # ============ INSERT METODLARI (o'zgarishsiz) ============
    
    def insert_video(self, video: dict) -> bool:
        """Video qo'shish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                now = datetime.now().isoformat()
                
                vid = video.get('id') or hashlib.md5(
                    (str(video.get('url', '')) + str(video.get('platform', ''))).encode()
                ).hexdigest()[:16]
                
                c.execute('SELECT id FROM videos WHERE id=? AND platform=?',
                         (str(vid), str(video.get('platform', ''))))
                if c.fetchone():
                    return True
                
                c.execute('''INSERT OR REPLACE INTO videos VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    str(vid), str(video.get('platform', '')),
                    str(video.get('title', '')), str(video.get('url', '')),
                    str(video.get('thumbnail', '')), str(video.get('duration', '')),
                    str(video.get('views', '')), str(video.get('rating', '')),
                    str(video.get('date_added', '')), str(video.get('category', '')),
                    json.dumps(video.get('tags', []), ensure_ascii=False),
                    json.dumps(video.get('models', []), ensure_ascii=False),
                    json.dumps(video.get('video_urls', []), ensure_ascii=False),
                    1 if video.get('is_premium') else 0,
                    1 if video.get('has_russian_audio') else 0,
                    str(video.get('description', '')),
                    str(video.get('likes', '')),
                    str(video.get('dislikes', '')),
                    json.dumps(video.get('download_links', []), ensure_ascii=False),
                    int(video.get('comments_count', 0)),
                    now, now
                ))
                self.conn.commit()
                logger.debug(f"Video saqlandi: {vid[:8]}... - {str(video.get('title', ''))[:40]}")
                return True
        except Exception as e:
            logger.error(f"Video insert xatosi: {e}")
            return False
    
    def insert_video_details(self, details: dict) -> bool:
        """Video tafsilotlarini qo'shish"""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                self.conn.execute('''INSERT OR REPLACE INTO video_details VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    str(details.get('video_id', '')),
                    str(details.get('platform', '')),
                    str(details.get('description', '')),
                    str(details.get('likes', '')),
                    str(details.get('dislikes', '')),
                    json.dumps(details.get('download_links', []), ensure_ascii=False),
                    json.dumps(details.get('comments', []), ensure_ascii=False),
                    json.dumps(details.get('related_videos', []), ensure_ascii=False),
                    json.dumps(details.get('tags', []), ensure_ascii=False),
                    json.dumps(details.get('models', []), ensure_ascii=False),
                    str(details.get('full_views', '')),
                    now, now
                ))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Details insert xatosi: {e}")
            return False
    
    def insert_category(self, cat: dict) -> bool:
        """Kategoriya qo'shish"""
        try:
            with self.lock:
                self.conn.execute('''INSERT OR IGNORE INTO categories 
                    (platform,title,url,video_count,image,letter,group_name,created_at)
                    VALUES (?,?,?,?,?,?,?,?)''', (
                    str(cat.get('platform', '')), str(cat.get('title', '')),
                    str(cat.get('url', '')), str(cat.get('video_count', '0')),
                    str(cat.get('image', '')), str(cat.get('letter', '')),
                    str(cat.get('group', '')), datetime.now().isoformat()
                ))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Category insert xatosi: {e}")
            return False
    
    def insert_photo(self, photo: dict) -> bool:
        """Fotosurat qo'shish"""
        try:
            with self.lock:
                pid = photo.get('id') or hashlib.md5(
                    (str(photo.get('url', '')) + str(photo.get('platform', ''))).encode()
                ).hexdigest()[:16]
                self.conn.execute('''INSERT OR REPLACE INTO photos VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    str(pid), str(photo.get('platform', '')),
                    str(photo.get('title', '')), str(photo.get('url', '')),
                    str(photo.get('thumbnail', '')), str(photo.get('date', '')),
                    str(photo.get('views', '')), str(photo.get('photo_count', '')),
                    str(photo.get('rating', '')), str(photo.get('likes', '')),
                    str(photo.get('studio', '')),
                    json.dumps(photo.get('models', []), ensure_ascii=False),
                    datetime.now().isoformat()
                ))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Photo insert xatosi: {e}")
            return False
    
    def insert_model(self, model: dict) -> bool:
        """Model qo'shish"""
        try:
            with self.lock:
                self.conn.execute('''INSERT OR IGNORE INTO models 
                    (platform,name,url,image,country,video_count,rating,created_at)
                    VALUES (?,?,?,?,?,?,?,?)''', (
                    str(model.get('platform', '')), str(model.get('name', '')),
                    str(model.get('url', '')), str(model.get('image', '')),
                    str(model.get('country', '')), str(model.get('video_count', '')),
                    str(model.get('rating', '')), datetime.now().isoformat()
                ))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Model insert xatosi: {e}")
            return False
    
    def insert_studio(self, studio: dict) -> bool:
        """Studiya qo'shish"""
        try:
            with self.lock:
                self.conn.execute('''INSERT OR IGNORE INTO studios 
                    (platform,name,url,image,video_count,created_at) 
                    VALUES (?,?,?,?,?,?)''', (
                    str(studio.get('platform', '')), str(studio.get('name', '')),
                    str(studio.get('url', '')), str(studio.get('image', '')),
                    str(studio.get('video_count', '')), datetime.now().isoformat()
                ))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Studio insert xatosi: {e}")
            return False
    
    def log_parse(self, platform: str, action: str, items: int, 
                  errors: int, duration: float) -> None:
        """Parse jarayonini loglash"""
        try:
            with self.lock:
                self.conn.execute('''INSERT INTO parse_logs VALUES (NULL,?,?,?,?,?,?)''',
                    (str(platform), str(action), items, errors, duration,
                     datetime.now().isoformat()))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Log parse xatosi: {e}")
    
    # ============ ASOSIY SO'ROV METODLARI ============
    
    def get_table_count(self, table_name: str) -> int:
        """Jadvaldagi yozuvlar soni"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute(f'SELECT COUNT(*) FROM {table_name}')
                return c.fetchone()[0]
        except:
            return 0
    
    def get_stats(self) -> dict:
        """Umumiy statistika"""
        try:
            with self.lock:
                c = self.conn.cursor()
                stats: dict = {}
                tables = ['videos', 'categories', 'photos', 'models', 'studios', 'video_details']
                for t in tables:
                    c.execute(f'SELECT COUNT(*) FROM {t}')
                    stats[f'total_{t}'] = c.fetchone()[0]
                
                c.execute('SELECT platform, COUNT(*) FROM videos GROUP BY platform')
                stats['by_platform'] = dict(c.fetchall())
                
                c.execute('SELECT COUNT(DISTINCT category) FROM videos WHERE category != ""')
                stats['unique_categories'] = c.fetchone()[0]
                
                c.execute('''SELECT AVG(CAST(REPLACE(views," ","") AS INTEGER)) 
                    FROM videos WHERE views != ""''')
                avg = c.fetchone()[0]
                stats['avg_views'] = int(avg) if avg else 0
                
                c.execute('SELECT MAX(created_at) FROM videos')
                stats['last_update'] = c.fetchone()[0] or 'Never'
                
                return stats
        except Exception as e:
            logger.error(f"Get stats xatosi: {e}")
            return {}
    
    def search(self, query: str, platform: Optional[str] = None,
               category: Optional[str] = None,
               limit: int = 50, offset: int = 0) -> List[dict]:
        """Video qidirish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                conditions = ['(title LIKE ? OR category LIKE ? OR tags LIKE ? OR description LIKE ?)']
                params: List[Any] = [f'%{query}%'] * 4
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if category:
                    conditions.append('category=?')
                    params.append(category)
                
                sql = f'''SELECT * FROM videos 
                    WHERE {" AND ".join(conditions)} 
                    ORDER BY created_at DESC LIMIT ? OFFSET ?'''
                params.extend([limit, offset])
                c.execute(sql, params)
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Search xatosi: {e}")
            return []
    
    def get_top_videos(self, limit: int = 20, platform: Optional[str] = None) -> List[dict]:
        """Eng ko'p ko'rilgan videolar"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('''SELECT * FROM videos 
                        WHERE platform=? AND views!="" 
                        ORDER BY CAST(REPLACE(views," ","") AS INTEGER) DESC 
                        LIMIT ?''', (platform, limit))
                else:
                    c.execute('''SELECT * FROM videos 
                        WHERE views!="" 
                        ORDER BY CAST(REPLACE(views," ","") AS INTEGER) DESC 
                        LIMIT ?''', (limit,))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Top videos xatosi: {e}")
            return []
    
    # ============ YANGI KENGAYTIRILGAN SO'ROV METODLARI ============
    
    def get_videos(self, platform: Optional[str] = None, 
                   category: Optional[str] = None,
                   date_from: Optional[str] = None,
                   date_to: Optional[str] = None,
                   min_views: Optional[int] = None,
                   max_views: Optional[int] = None,
                   is_premium: Optional[bool] = None,
                   has_russian_audio: Optional[bool] = None,
                   sort_by: str = 'created_at',
                   sort_order: str = 'DESC',
                   limit: int = 100, 
                   offset: int = 0) -> Tuple[List[dict], int]:
        """Kengaytirilgan video olish metodi - 11 xil filtr bilan"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if category:
                    conditions.append('category=?')
                    params.append(category)
                if date_from:
                    conditions.append('date_added >= ?')
                    params.append(date_from)
                if date_to:
                    conditions.append('date_added <= ?')
                    params.append(date_to)
                if min_views is not None:
                    conditions.append('CAST(REPLACE(views," ","") AS INTEGER) >= ?')
                    params.append(min_views)
                if max_views is not None:
                    conditions.append('CAST(REPLACE(views," ","") AS INTEGER) <= ?')
                    params.append(max_views)
                if is_premium is not None:
                    conditions.append('is_premium=?')
                    params.append(1 if is_premium else 0)
                if has_russian_audio is not None:
                    conditions.append('has_russian_audio=?')
                    params.append(1 if has_russian_audio else 0)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                # Saralash
                allowed_sort = {
                    'created_at': 'created_at',
                    'views': 'CAST(REPLACE(views," ","") AS INTEGER)',
                    'title': 'title',
                    'rating': 'CAST(rating AS REAL)',
                    'duration': 'duration',
                    'date_added': 'date_added'
                }
                
                sort_field = allowed_sort.get(sort_by, 'created_at')
                order = sort_order.upper() if sort_order.upper() in ['ASC', 'DESC'] else 'DESC'
                
                # Umumiy son
                count_sql = f'SELECT COUNT(*) FROM videos {where_clause}'
                c.execute(count_sql, params)
                total = c.fetchone()[0]
                
                # Ma'lumotlarni olish
                sql = f'SELECT * FROM videos {where_clause} ORDER BY {sort_field} {order} LIMIT ? OFFSET ?'
                c.execute(sql, params + [limit, offset])
                videos = [dict(r) for r in c.fetchall()]
                
                return videos, total
                
        except Exception as e:
            logger.error(f"Get videos xatosi: {e}")
            return [], 0
    
    def get_videos_by_date_range(self, days: int = 7, 
                                 platform: Optional[str] = None) -> List[dict]:
        """Oxirgi N kundagi videolarni olish"""
        date_from = (datetime.now() - timedelta(days=days)).isoformat()
        videos, _ = self.get_videos(
            platform=platform,
            date_from=date_from,
            sort_by='created_at',
            limit=1000
        )
        return videos
    
    def get_videos_by_views_range(self, min_views: int = 0, 
                                   max_views: Optional[int] = None,
                                   platform: Optional[str] = None,
                                   limit: int = 100) -> List[dict]:
        """Ko'rishlar soni oralig'idagi videolarni olish"""
        videos, _ = self.get_videos(
            platform=platform,
            min_views=min_views,
            max_views=max_views,
            sort_by='views',
            limit=limit
        )
        return videos
    
    def search_advanced(self, 
                        keyword: Optional[str] = None,
                        platform: Optional[str] = None,
                        category: Optional[str] = None,
                        model: Optional[str] = None,
                        tag: Optional[str] = None,
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None,
                        is_premium: Optional[bool] = None,
                        has_russian_audio: Optional[bool] = None,
                        sort_by: str = 'created_at',
                        sort_order: str = 'DESC',
                        limit: int = 100,
                        offset: int = 0) -> Tuple[List[dict], int]:
        """Kengaytirilgan qidiruv - 10+ filtr"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if keyword:
                    conditions.append('(title LIKE ? OR description LIKE ? OR tags LIKE ? OR models LIKE ?)')
                    kw = f'%{keyword}%'
                    params.extend([kw, kw, kw, kw])
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if category:
                    conditions.append('category=?')
                    params.append(category)
                if model:
                    conditions.append('models LIKE ?')
                    params.append(f'%{model}%')
                if tag:
                    conditions.append('tags LIKE ?')
                    params.append(f'%{tag}%')
                if date_from:
                    conditions.append('date_added >= ?')
                    params.append(date_from)
                if date_to:
                    conditions.append('date_added <= ?')
                    params.append(date_to)
                if is_premium is not None:
                    conditions.append('is_premium=?')
                    params.append(1 if is_premium else 0)
                if has_russian_audio is not None:
                    conditions.append('has_russian_audio=?')
                    params.append(1 if has_russian_audio else 0)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                allowed_sort = {
                    'created_at': 'created_at',
                    'views': 'CAST(REPLACE(views," ","") AS INTEGER)',
                    'title': 'title',
                    'rating': 'CAST(rating AS REAL)',
                    'duration': 'duration'
                }
                
                sort_field = allowed_sort.get(sort_by, 'created_at')
                order = sort_order.upper() if sort_order.upper() in ['ASC', 'DESC'] else 'DESC'
                
                count_sql = f'SELECT COUNT(*) FROM videos {where_clause}'
                c.execute(count_sql, params)
                total = c.fetchone()[0]
                
                sql = f'SELECT * FROM videos {where_clause} ORDER BY {sort_field} {order} LIMIT ? OFFSET ?'
                c.execute(sql, params + [limit, offset])
                results = [dict(r) for r in c.fetchall()]
                
                return results, total
                
        except Exception as e:
            logger.error(f"Advanced search xatosi: {e}")
            return [], 0
    
    def get_categories(self, platform: Optional[str] = None,
                       group: Optional[str] = None,
                       letter: Optional[str] = None) -> List[dict]:
        """Kategoriyalarni olish (filtrlar bilan)"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if group:
                    conditions.append('group_name=?')
                    params.append(group)
                if letter:
                    conditions.append('letter=?')
                    params.append(letter)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                c.execute(f'SELECT * FROM categories {where_clause} ORDER BY title')
                return [dict(r) for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get categories xatosi: {e}")
            return []
    
    def get_categories_with_stats(self, platform: Optional[str] = None) -> List[dict]:
        """Kategoriyalar statistikasi bilan birga"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                if platform:
                    c.execute('''SELECT 
                        c.*,
                        COUNT(v.id) as actual_video_count,
                        AVG(CAST(REPLACE(v.views," ","") AS INTEGER)) as avg_views
                        FROM categories c
                        LEFT JOIN videos v ON c.title = v.category AND c.platform = v.platform
                        WHERE c.platform=?
                        GROUP BY c.url
                        ORDER BY actual_video_count DESC''', (platform,))
                else:
                    c.execute('''SELECT 
                        c.*,
                        COUNT(v.id) as actual_video_count,
                        AVG(CAST(REPLACE(v.views," ","") AS INTEGER)) as avg_views
                        FROM categories c
                        LEFT JOIN videos v ON c.title = v.category AND c.platform = v.platform
                        GROUP BY c.url
                        ORDER BY actual_video_count DESC''')
                
                return [dict(r) for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get categories with stats xatosi: {e}")
            return []
    
    def get_photos(self, platform: Optional[str] = None,
                   studio: Optional[str] = None,
                   sort_by: str = 'created_at',
                   limit: int = 100) -> List[dict]:
        """Fotosuratlarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if studio:
                    conditions.append('studio=?')
                    params.append(studio)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                allowed_sort = ['created_at', 'views', 'rating', 'likes']
                if sort_by not in allowed_sort:
                    sort_by = 'created_at'
                
                c.execute(f'SELECT * FROM photos {where_clause} ORDER BY {sort_by} DESC LIMIT ?', 
                         params + [limit])
                
                return [dict(r) for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get photos xatosi: {e}")
            return []
    
    def get_models(self, platform: Optional[str] = None,
                   country: Optional[str] = None,
                   min_videos: Optional[int] = None,
                   sort_by: str = 'video_count',
                   limit: int = 100) -> List[dict]:
        """Modellarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if country:
                    conditions.append('country=?')
                    params.append(country)
                if min_videos is not None:
                    conditions.append('CAST(video_count AS INTEGER) >= ?')
                    params.append(min_videos)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                allowed_sort = ['name', 'video_count', 'rating', 'created_at']
                if sort_by not in allowed_sort:
                    sort_by = 'video_count'
                
                if sort_by == 'video_count':
                    order = 'ORDER BY CAST(video_count AS INTEGER) DESC'
                elif sort_by == 'rating':
                    order = 'ORDER BY CAST(rating AS REAL) DESC'
                else:
                    order = f'ORDER BY {sort_by}'
                
                c.execute(f'SELECT * FROM models {where_clause} {order} LIMIT ?', 
                         params + [limit])
                
                return [dict(r) for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get models xatosi: {e}")
            return []
    
    def get_studios(self, platform: Optional[str] = None,
                    min_videos: Optional[int] = None,
                    limit: int = 100) -> List[dict]:
        """Studiyalarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if min_videos is not None:
                    conditions.append('CAST(video_count AS INTEGER) >= ?')
                    params.append(min_videos)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                c.execute(f'''SELECT * FROM studios {where_clause} 
                    ORDER BY CAST(video_count AS INTEGER) DESC LIMIT ?''', 
                    params + [limit])
                
                return [dict(r) for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get studios xatosi: {e}")
            return []
    
    def get_video_details(self, video_id: str, platform: str) -> Optional[dict]:
        """Video tafsilotlarini olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('SELECT * FROM video_details WHERE video_id=? AND platform=?',
                         (video_id, platform))
                r = c.fetchone()
                return dict(r) if r else None
        except Exception as e:
            logger.error(f"Get details xatosi: {e}")
            return None
    
    def get_parse_logs(self, platform: Optional[str] = None,
                       action: Optional[str] = None,
                       limit: int = 50) -> List[dict]:
        """Parse loglarini olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                conditions = []
                params: List[Any] = []
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if action:
                    conditions.append('action=?')
                    params.append(action)
                
                where_clause = ''
                if conditions:
                    where_clause = 'WHERE ' + ' AND '.join(conditions)
                
                c.execute(f'''SELECT * FROM parse_logs {where_clause} 
                    ORDER BY created_at DESC LIMIT ?''', params + [limit])
                
                return [dict(r) for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get parse logs xatosi: {e}")
            return []
    
    def get_all_data(self, platform: Optional[str] = None) -> dict:
        """Barcha ma'lumotlarni bitta so'rovda olish"""
        try:
            data = {
                'export_date': datetime.now().isoformat(),
                'database': self.db_path,
                'statistics': self.get_stats(),
                'videos': self.get_videos(platform=platform, limit=10000)[0],
                'categories': self.get_categories(platform=platform),
                'categories_with_stats': self.get_categories_with_stats(platform=platform),
                'photos': self.get_photos(platform=platform),
                'models': self.get_models(platform=platform),
                'studios': self.get_studios(platform=platform),
                'video_details': [],
                'parse_logs': self.get_parse_logs(platform=platform)
            }
            
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('SELECT * FROM video_details WHERE platform=?', (platform,))
                else:
                    c.execute('SELECT * FROM video_details')
                data['video_details'] = [dict(r) for r in c.fetchall()]
            
            return data
            
        except Exception as e:
            logger.error(f"Get all data xatosi: {e}")
            return {}
    
    def get_unique_values(self, column: str, table: str = 'videos',
                          platform: Optional[str] = None) -> List[str]:
        """Jadvaldagi unikal qiymatlarni olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                
                if platform and table == 'videos':
                    c.execute(f'''SELECT DISTINCT {column} FROM {table} 
                        WHERE platform=? AND {column} IS NOT NULL AND {column} != "" 
                        ORDER BY {column}''', (platform,))
                else:
                    c.execute(f'''SELECT DISTINCT {column} FROM {table} 
                        WHERE {column} IS NOT NULL AND {column} != "" 
                        ORDER BY {column}''')
                
                return [r[0] for r in c.fetchall()]
                
        except Exception as e:
            logger.error(f"Get unique values xatosi: {e}")
            return []
    
    def get_data_by_id(self, video_id: str) -> Optional[dict]:
        """ID bo'yicha video ma'lumotlarini olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('SELECT * FROM videos WHERE id=?', (video_id,))
                r = c.fetchone()
                return dict(r) if r else None
        except Exception as e:
            logger.error(f"Get data by id xatosi: {e}")
            return None
    
    def get_data_by_url(self, url: str) -> Optional[dict]:
        """URL bo'yicha video ma'lumotlarini olish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('SELECT * FROM videos WHERE url=?', (url,))
                r = c.fetchone()
                return dict(r) if r else None
        except Exception as e:
            logger.error(f"Get data by url xatosi: {e}")
            return None
    
    # ============ BACKUP/RESTORE ============
    
    def backup(self, backup_dir: str = 'backups') -> str:
        """Ma'lumotlar bazasini zaxiralash"""
        Path(backup_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = Path(backup_dir) / f'xxx_collector_backup_{timestamp}.db'
        
        with self.lock:
            backup_conn = sqlite3.connect(str(backup_path))
            self.conn.backup(backup_conn)
            backup_conn.close()
        
        self._cleanup_old_backups(backup_dir)
        logger.info(f"Backup yaratildi: {backup_path}")
        return str(backup_path)
    
    def restore(self, backup_path: str) -> bool:
        """Ma'lumotlar bazasini tiklash"""
        try:
            if not Path(backup_path).exists():
                logger.error(f"Backup fayl topilmadi: {backup_path}")
                return False
            
            with self.lock:
                backup_conn = sqlite3.connect(backup_path)
                backup_conn.backup(self.conn)
                backup_conn.close()
            
            logger.info(f"Backup tiklandi: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore xatosi: {e}")
            return False
    
    def _cleanup_old_backups(self, backup_dir: str, days: int = 7) -> None:
        """Eski backuplarni o'chirish"""
        cutoff = datetime.now() - timedelta(days=days)
        for f in Path(backup_dir).glob('xxx_collector_backup_*.db'):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                logger.info(f"Eski backup o'chirildi: {f}")
    
    def cleanup_duplicates(self) -> int:
        """Duplikatlarni tozalash"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('''DELETE FROM videos WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM videos GROUP BY id, platform)''')
                deleted = c.rowcount
                self.conn.commit()
                logger.info(f"Duplikat tozalash: {deleted} ta")
                return deleted
        except Exception as e:
            logger.error(f"Tozalash xatosi: {e}")
            return 0
    
    # ============ EKSPORT ============
    
    def export_json_full(self, filepath: str, chunk_size: int = 1000) -> Tuple[bool, int]:
        """To'liq JSON eksport"""
        try:
            video_count = self.get_table_count('videos')
            if video_count == 0:
                logger.warning("⚠️  Eksport qilinadigan video yo'q!")
                return False, 0
            
            with self.lock:
                stats = self.get_stats()
                categories = [dict(r) for r in self.conn.execute('SELECT * FROM categories').fetchall()]
                models_data = [dict(r) for r in self.conn.execute('SELECT * FROM models').fetchall()]
                studios_data = [dict(r) for r in self.conn.execute('SELECT * FROM studios').fetchall()]
                photos_data = [dict(r) for r in self.conn.execute('SELECT * FROM photos').fetchall()]
                details_data = [dict(r) for r in self.conn.execute('SELECT * FROM video_details').fetchall()]
            
            total = stats.get('total_videos', 0)
            offset = 0
            written_videos = 0
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('{\n')
                f.write(f'  "export_date": "{datetime.now().isoformat()}",\n')
                f.write(f'  "database": "{self.db_path}",\n')
                f.write(f'  "statistics": {json.dumps(stats, ensure_ascii=False)},\n')
                f.write(f'  "categories": {json.dumps(categories, ensure_ascii=False)},\n')
                f.write(f'  "photos": {json.dumps(photos_data, ensure_ascii=False)},\n')
                f.write(f'  "models": {json.dumps(models_data, ensure_ascii=False)},\n')
                f.write(f'  "studios": {json.dumps(studios_data, ensure_ascii=False)},\n')
                f.write(f'  "video_details": {json.dumps(details_data, ensure_ascii=False)},\n')
                f.write('  "videos": [\n')
                
                first = True
                while offset < total:
                    with self.lock:
                        c = self.conn.cursor()
                        c.execute('SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?',
                                (chunk_size, offset))
                        chunk = [dict(r) for r in c.fetchall()]
                    
                    if not chunk:
                        break
                    
                    for video in chunk:
                        if not first:
                            f.write(',\n')
                        else:
                            first = False
                        f.write('    ')
                        json.dump(video, f, ensure_ascii=False)
                        written_videos += 1
                    
                    offset += len(chunk)
                    if offset % 5000 == 0:
                        logger.info(f"Eksport: {offset}/{total}")
                
                f.write('\n  ]\n}')
            
            logger.info(f"✅ To'liq JSON eksport: {filepath} ({written_videos} ta video)")
            return True, written_videos
            
        except Exception as e:
            logger.error(f"JSON eksport xatosi: {e}")
            return False, 0
    
    def export_csv(self, filepath: str, platform: Optional[str] = None) -> Tuple[int, int]:
        """CSV eksport"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('SELECT COUNT(*) FROM videos WHERE platform=?', (platform,))
                else:
                    c.execute('SELECT COUNT(*) FROM videos')
                total = c.fetchone()[0]
            
            if total == 0:
                logger.warning("⚠️  Eksport qilinadigan video yo'q!")
                return 0, 0
            
            exported = 0
            offset = 0
            chunk_size = 500
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = None
                while offset < total:
                    with self.lock:
                        c = self.conn.cursor()
                        if platform:
                            c.execute('''SELECT * FROM videos 
                                WHERE platform=? 
                                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                                (platform, chunk_size, offset))
                        else:
                            c.execute('''SELECT * FROM videos 
                                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                                (chunk_size, offset))
                        chunk = [dict(r) for r in c.fetchall()]
                    
                    if not chunk:
                        break
                    
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=list(chunk[0].keys()))
                        writer.writeheader()
                    
                    writer.writerows(chunk)
                    offset += len(chunk)
                    exported += len(chunk)
            
            logger.info(f"✅ CSV: {exported} ta")
            return exported, total
            
        except Exception as e:
            logger.error(f"CSV eksport xatosi: {e}")
            return 0, 0
    
    def export_mp4_urls(self, filepath: str, platform: Optional[str] = None) -> int:
        """MP4 URL larini eksport qilish"""
        try:
            with self.lock:
                c = self.conn.cursor()
                urls: set = set()
                
                if platform:
                    c.execute('''SELECT video_urls FROM videos 
                        WHERE video_urls IS NOT NULL AND video_urls!="[]" 
                        AND platform=?''', (platform,))
                else:
                    c.execute('''SELECT video_urls FROM videos 
                        WHERE video_urls IS NOT NULL AND video_urls!="[]"''')
                
                for row in c.fetchall():
                    try:
                        loaded = json.loads(row[0]) if row[0] else []
                        for u in loaded:
                            if u and str(u).strip():
                                urls.add(str(u).strip())
                    except:
                        pass
                
                if platform:
                    c.execute('''SELECT download_links FROM video_details 
                        WHERE download_links IS NOT NULL AND download_links!="[]" 
                        AND platform=?''', (platform,))
                else:
                    c.execute('''SELECT download_links FROM video_details 
                        WHERE download_links IS NOT NULL AND download_links!="[]"''')
                
                for row in c.fetchall():
                    try:
                        loaded = json.loads(row[0]) if row[0] else []
                        for dl in loaded:
                            if isinstance(dl, dict) and dl.get('url'):
                                urls.add(str(dl['url']))
                            elif isinstance(dl, str) and dl.strip():
                                urls.add(dl.strip())
                    except:
                        pass
            
            total_urls = len(urls)
            
            if total_urls == 0:
                logger.warning("⚠️  Eksport qilinadigan URL yo'q!")
                return 0
            
            with open(filepath, 'w', encoding='utf-8') as f:
                for u in sorted(urls):
                    f.write(u + '\n')
            
            logger.info(f"URL eksport: {total_urls} ta")
            return total_urls
            
        except Exception as e:
            logger.error(f"URL eksport xatosi: {e}")
            return 0


# ==================== NATIJALARNI FORMATLASH MODULI ====================

class DataFormatter:
    """Ma'lumotlarni turli formatlarda chiqarish"""
    
    @staticmethod
    def format_videos_table(videos: List[dict], show_preview: bool = True) -> str:
        """Videolarni jadval ko'rinishida formatlash"""
        if not videos:
            return "❌ Videolar topilmadi!"
        
        separator = "─" * 100
        header = f"\n{separator}\n"
        header += f"│ {'#':<4} │ {'Platforma':<8} │ {'Sarlavha':<40} │ {'Korishlar':<12} │ {'Premium':<8} │\n"
        header += f"{separator}\n"
        
        rows = []
        for i, v in enumerate(videos, 1):
            premium = "💎" if v.get('is_premium') else ""
            title = str(v.get('title', ''))[:38]
            views = str(v.get('views', 'N/A'))
            platform = str(v.get('platform', ''))
            
            row = f"│ {i:<4} │ {platform:<8} │ {title:<40} │ {views:<12} │ {premium:<8} │"
            rows.append(row)
            
            if show_preview and v.get('description'):
                desc = str(v.get('description', ''))[:80]
                rows.append(f"│      │          📝 {desc}")
        
        footer = f"{separator}\nJami: {len(videos)} ta video\n"
        return header + '\n'.join(rows) + '\n' + footer
    
    @staticmethod
    def format_video_card(video: dict) -> str:
        """Bitta video kartochkasi"""
        if not video:
            return "❌ Video topilmadi!"
        
        premium = "💎 PREMIUM" if video.get('is_premium') else "🆓 BEPUL"
        ru_audio = "🔊 Ruscha ovoz" if video.get('has_russian_audio') else ""
        
        card = f"""
╔══════════════════════════════════════════════════════════════╗
║  🎬 {str(video.get('title', 'Nomsiz'))[:50]}
╠══════════════════════════════════════════════════════════════╣
║  🏷️  Platforma: {video.get('platform', 'N/A')}
║  👁️  Ko'rishlar: {video.get('views', 'N/A')}
║  ⭐ Reyting: {video.get('rating', 'N/A')}
║  ⏱️  Davomiylik: {video.get('duration', 'N/A')}
║  📅 Sana: {video.get('date_added', 'N/A')}
║  📂 Kategoriya: {video.get('category', 'N/A')}
║  🏷️  Status: {premium} {ru_audio}
║  🔗 URL: {video.get('url', 'N/A')[:50]}
╚══════════════════════════════════════════════════════════════╝
"""
        if video.get('description'):
            card += f"\n📝 Tavsif: {str(video.get('description', ''))[:200]}...\n"
        
        if video.get('tags'):
            try:
                tags = json.loads(video['tags']) if isinstance(video['tags'], str) else video['tags']
                card += f"\n🏷️  Teglar: {', '.join(tags[:10])}\n"
            except:
                pass
        
        if video.get('models'):
            try:
                models = json.loads(video['models']) if isinstance(video['models'], str) else video['models']
                card += f"\n👤 Modellar: {', '.join(models[:10])}\n"
            except:
                pass
        
        return card
    
    @staticmethod
    def format_stats_report(stats: dict) -> str:
        """Statistika hisoboti"""
        report = f"""
╔══════════════════════════════════════════════════════════╗
║              📊 TO'LIQ STATISTIKA HISOBOTI               ║
╠══════════════════════════════════════════════════════════╣
║  📹 Videolar:           {stats.get('total_videos', 0):>8}                    ║
║  📂 Kategoriyalar:      {stats.get('total_categories', 0):>8}                    ║
║  📷 Fotosuratlar:       {stats.get('total_photos', 0):>8}                    ║
║  👤 Modellar:           {stats.get('total_models', 0):>8}                    ║
║  🏢 Studiyalar:         {stats.get('total_studios', 0):>8}                    ║
║  📋 Video tafsilotlari: {stats.get('total_video_details', 0):>8}                    ║
╠══════════════════════════════════════════════════════════╣
║  🔍 Unikal kategoriyalar: {stats.get('unique_categories', 0):>6}                  ║
║  👁️  O'rtacha ko'rish:    {stats.get('avg_views', 0):>8}                    ║
║  🕐 Oxirgi yangilash: {str(stats.get('last_update', 'N/A'))[:19]:<25} ║
╚══════════════════════════════════════════════════════════╝
"""
        by_platform = stats.get('by_platform', {})
        if by_platform:
            report += "\n📊 Platformalar bo'yicha:\n" + "─" * 40 + "\n"
            for pl, count in sorted(by_platform.items()):
                bar = "█" * min(count // 10 if count > 0 else 0, 20)
                report += f"  {pl:<6}: {count:>6} {bar}\n"
        
        return report
    
    @staticmethod
    def format_category_tree(categories: List[dict]) -> str:
        """Kategoriyalarni daraxt ko'rinishida formatlash"""
        if not categories:
            return "❌ Kategoriyalar topilmadi!"
        
        tree = "\n📂 KATEGORIYALAR DARAXTI\n" + "═" * 60 + "\n"
        
        by_platform: dict = {}
        for cat in categories:
            pl = cat.get('platform', 'other')
            if pl not in by_platform:
                by_platform[pl] = []
            by_platform[pl].append(cat)
        
        for pl, cats in sorted(by_platform.items()):
            tree += f"\n🏷️  [{pl.upper()}] - {len(cats)} ta kategoriya\n" + "─" * 50 + "\n"
            
            by_letter: dict = {}
            for cat in cats:
                letter = cat.get('letter') or cat.get('group') or 'Umumiy'
                if letter not in by_letter:
                    by_letter[letter] = []
                by_letter[letter].append(cat)
            
            for letter, items in sorted(by_letter.items()):
                tree += f"  📁 {letter}\n"
                for cat in items[:5]:
                    title = str(cat.get('title', ''))[:35]
                    count = cat.get('video_count', '0')
                    tree += f"    ├─ {title:<35} ({count} ta)\n"
                
                if len(items) > 5:
                    tree += f"    └─ ... yana {len(items) - 5} ta\n"
        
        return tree


# ==================== TEZKOR YORDAMCHI FUNKSIYALAR ====================

def get_database(db_path: str = 'data/xxx_collector.db') -> Database:
    """Tezkor ma'lumotlar bazasi ulanishi"""
    return Database(db_path)


def quick_save(data: Union[dict, List[dict]], filename: str, format: str = 'json') -> str:
    """Ma'lumotlarni tezkor saqlash (JSON, TXT, CSV)"""
    fmt = DataFormatter()
    
    if format == 'json':
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif format == 'txt':
        with open(filename, 'w', encoding='utf-8') as f:
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        f.write(fmt.format_video_card(item))
                        f.write('\n')
                    else:
                        f.write(str(item) + '\n')
            else:
                f.write(str(data))
    elif format == 'csv':
        if isinstance(data, list) and data:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                writer.writeheader()
                writer.writerows(data)
    
    return filename


# ==================== BASE PARSER ====================

class BaseParser(ABC):
    """Barcha parserlar uchun asos klass"""
    
    def __init__(self, base_url: str, name: str, config: Config):
        self.base_url = base_url
        self.name = name
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.5',
        })
    
    def _get(self, url: str, retries: Optional[int] = None) -> Optional[BeautifulSoup]:
        """HTTP GET so'rovi"""
        if retries is None:
            retries = self.config.max_retries
        
        for attempt in range(retries):
            try:
                r = self.session.get(url, timeout=self.config.timeout)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return BeautifulSoup(r.text, 'html.parser')
                elif r.status_code == 404:
                    return None
                elif r.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    logger.warning(f"[{self.name}] Rate limit, kutish: {wait}s")
                    time.sleep(wait)
            except Exception as e:
                logger.warning(f"[{self.name}] So'rov xatosi ({attempt+1}/{retries}): {e}")
                time.sleep(1)
        return None
    
    def _text(self, e: Any) -> str:
        """Element matnini olish"""
        return e.get_text(strip=True) if e else ''
    
    def _attr(self, e: Any, a: str, default: str = '') -> str:
        """Element atributini olish"""
        if e is None:
            return default
        v = e.get(a, default)
        if v is None:
            return default
        if isinstance(v, list):
            return ' '.join(str(x) for x in v)
        return str(v)
    
    def _id(self, url: str) -> str:
        """URL dan ID ajratib olish"""
        if not url:
            return ''
        parts = url.rstrip('/').split('/')
        skip = ['video', 'photos', 'categories', 'actresses', 'studios']
        for part in reversed(parts):
            if part and part not in skip:
                return part
        return parts[-1] if parts else ''
    
    def _clean_views(self, views_str: str) -> str:
        """Ko'rishlar sonini tozalash"""
        if not views_str:
            return ''
        return re.sub(r'[\s\u2009\u00A0]', '', views_str)
    
    @abstractmethod
    def videos(self, **kw: Any) -> List[dict]:
        """Videolarni yig'ish"""
        pass
    
    @abstractmethod
    def categories(self) -> List[dict]:
        """Kategoriyalarni yig'ish"""
        pass
    
    def video_details(self, url: str) -> Optional[dict]:
        """Video tafsilotlari (default)"""
        return None
    
    def photos(self, page: int = 1) -> List[dict]:
        """Fotosuratlar (default)"""
        return []
    
    def models(self, url: Optional[str] = None) -> List[dict]:
        """Modellar (default)"""
        return []
    
    def studios(self) -> List[dict]:
        """Studiyalar (default)"""
        return []
    
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        """Kategoriyadan videolar"""
        return []


class LatParser(BaseParser):
    """sosalkino.lat parseri"""
    
    def __init__(self, c: Config):
        super().__init__("https://sosalkino.lat", "lat", c)
    
    def videos(self, **kw: Any) -> List[dict]:
        s = self._get(self.base_url)
        if not s:
            return []
        res = []
        for d in s.find_all('div', class_='content'):
            for v in d.find_all('div', class_='video'):
                a = v.find_parent('a')
                if not a:
                    continue
                url = urljoin(self.base_url, self._attr(a, 'href'))
                img = v.find('img', class_='screen')
                res.append({
                    'id': self._id(url),
                    'platform': self.name,
                    'url': url,
                    'title': self._text(v.find('span', class_='videotitle')),
                    'thumbnail': self._attr(img, 'data-original') or self._attr(img, 'src'),
                    'duration': self._text(v.find('div', class_='videoduration')),
                    'views': self._clean_views(self._text(v.find('span', class_='videoviews'))),
                })
        return res
    
    def categories(self) -> List[dict]:
        s = self._get(f"{self.base_url}/category/")
        if not s:
            return []
        result = []
        for a in s.find_all('a', class_='catlink'):
            img_tag = a.find('img', class_='prewpic')
            result.append({
                'platform': self.name,
                'url': urljoin(self.base_url, self._attr(a, 'href')),
                'title': self._text(a.find('span', class_='videotitle')),
                'video_count': self._text(a.find('span', class_='videoviews')),
                'image': self._attr(img_tag, 'data-original') or self._attr(img_tag, 'src')
            })
        return result
    
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        res = []
        base = url.rstrip('/')
        for p in range(1, pages + 1):
            u = base if p == 1 else f"{base}/page{p}/"
            s = self._get(u)
            if not s:
                break
            cn = self._text(s.find('h1', class_='title'))
            cd = s.find('div', class_='content')
            if not cd:
                break
            for v in cd.find_all('div', class_='video'):
                a = v.find_parent('a')
                if not a:
                    continue
                vu = urljoin(self.base_url, self._attr(a, 'href'))
                img = v.find('img', class_='screen')
                res.append({
                    'id': self._id(vu),
                    'platform': self.name,
                    'url': vu,
                    'title': self._text(v.find('span', class_='videotitle')),
                    'category': cn,
                    'thumbnail': self._attr(img, 'data-original') or self._attr(img, 'src'),
                    'duration': self._text(v.find('div', class_='videoduration')),
                    'views': self._clean_views(self._text(v.find('span', class_='videoviews'))),
                })
            time.sleep(self.config.request_delay)
        return res
    
    def video_details(self, url: str) -> Optional[dict]:
        s = self._get(url)
        if not s:
            return None
        
        details: dict = {
            'video_id': self._id(url),
            'platform': self.name,
            'url': url,
            'description': '', 'likes': '', 'dislikes': '',
            'download_links': [], 'comments': [],
            'related_videos': [], 'tags': [], 'models': [],
            'full_views': '', 'date_added': '', 'date_updated': '',
        }
        
        h1 = s.find('h1', class_='title')
        if h1:
            details['title'] = h1.text.strip()
        
        for link in s.find_all('a', class_='icon'):
            text = link.text.strip()
            classes = link.get('class')
            if classes and isinstance(classes, list):
                if 'icon-calendar' in classes:
                    details['date_added'] = text
                elif 'icon-eye' in classes:
                    details['full_views'] = self._clean_views(text)
                elif 'icon-clock' in classes:
                    details['duration'] = text
        
        like_div = s.find('div', class_='like')
        if like_div:
            counter = like_div.find('span', class_='counter')
            if counter:
                details['likes'] = counter.text.strip()
        
        dislike_div = s.find('div', class_='like2')
        if dislike_div:
            counter = dislike_div.find('span', class_='counter')
            if counter:
                details['dislikes'] = counter.text.strip()
        
        details['categories'] = [{
            'title': cat.text.strip(),
            'url': urljoin(self.base_url, self._attr(cat, 'href'))
        } for cat in s.find_all('a', class_='linkcat')]
        
        for dl in s.find_all('a', class_='download'):
            span_tag = dl.find('span')
            details['download_links'].append({
                'url': urljoin(self.base_url, self._attr(dl, 'href')),
                'quality': span_tag.text.strip() if span_tag else '480p'
            })
        
        related_section = s.find('div', class_='buttvideo')
        if related_section:
            next_div = related_section.find_next_sibling('div', class_='video')
            count = 0
            while next_div is not None and count < 20:
                count += 1
                classes = next_div.get('class')
                if not classes or not isinstance(classes, list) or 'video' not in classes:
                    break
                a = next_div.find_parent('a')
                if a:
                    related_url = urljoin(self.base_url, self._attr(a, 'href'))
                    details['related_videos'].append({
                        'url': related_url,
                        'id': self._id(related_url),
                        'title': self._text(next_div.find('span', class_='videotitle')),
                    })
                next_div = next_div.find_next_sibling('div', class_='video')
        
        return details


class BestParser(BaseParser):
    """sosalkino.best parseri"""
    
    def __init__(self, c: Config):
        super().__init__("https://r.sosalkino.best", "best", c)
    
    def videos(self, page: int = 1, **kw: Any) -> List[dict]:
        u = self.base_url if page == 1 else f"{self.base_url}/{page}/"
        s = self._get(u)
        if not s:
            return []
        vl = s.find('div', class_='items-list')
        if not vl:
            return []
        res = []
        for it in vl.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a:
                continue
            vu = urljoin(self.base_url, self._attr(a, 'href'))
            v: dict = {'id': self._id(vu), 'platform': self.name, 'url': vu}
            
            ti = it.find('div', class_='title-item')
            if ti:
                title_p = ti.find('p', class_='title')
                if title_p:
                    v['title'] = self._text(title_p)
            
            ih = it.find('div', class_='img-holder')
            if ih:
                im = ih.find('img', class_='thumb')
                if im:
                    v['thumbnail'] = self._attr(im, 'data-src') or self._attr(im, 'src')
                
                pr = ih.find('div', class_='premium-icons')
                if pr:
                    diamond_found = pr.find('img', src=lambda x: bool(x and 'diamond' in str(x)))
                    v['is_premium'] = bool(diamond_found)
                    ru_found = pr.find('div', string='Русская озвучка')
                    v['has_russian_audio'] = bool(ru_found)
                
                preview = ih.get('data-preview', '')
                if preview:
                    v['preview_url'] = str(preview)
            
            info = it.find('div', class_='info-holder')
            if info:
                for d in info.find_all('div', class_='item-info'):
                    t = d.find('span', class_='text')
                    ic = d.find('i')
                    if t and ic:
                        classes = ic.get('class')
                        if classes and isinstance(classes, list):
                            cl = ' '.join(classes)
                            tx = t.text.strip()
                            if 'icon-clock' in cl:
                                v['duration'] = tx
                            elif 'icon-eye' in cl:
                                v['views'] = self._clean_views(tx)
                            elif 'icon-like' in cl:
                                v['rating'] = tx
                            elif 'icon-calendar' in cl:
                                v['date_added'] = tx
            res.append(v)
        return res
    
    def videos_fast(self, pages: int = 5) -> List[dict]:
        res: List[dict] = []
        workers = min(self.config.max_workers, pages)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fs = {ex.submit(self.videos, page=p): p for p in range(1, pages + 1)}
            for f in as_completed(fs):
                try:
                    result = f.result()
                    if result:
                        res.extend(result)
                except Exception as e:
                    logger.error(f"[best] p{fs[f]}: {e}")
        return res
    
    def categories(self) -> List[dict]:
        s = self._get(f"{self.base_url}/categories/")
        if not s:
            return []
        res: List[dict] = []
        for tab_name, gf in [('title', 'letter'), ('groups', 'group')]:
            tab = s.find('div', class_='tabs-content', attrs={'data-group-open': tab_name})
            if not tab:
                continue
            holders = (tab.find_all('div', class_='letter-holder') if gf == 'letter'
                      else tab.find_all('div', class_='category-group'))
            for h in holders:
                gv = (self._text(h.find('span', class_='letter')) if gf == 'letter'
                     else self._text(h.find('div', class_='title-group')))
                for it in h.find_all('div', class_='item'):
                    a = it.find('a', class_='link')
                    if a:
                        cat: dict = {
                            'platform': self.name,
                            'url': urljoin(self.base_url, self._attr(a, 'href')),
                            'title': self._text(a.find('span', class_='title')),
                            'video_count': self._text(a.find('span', class_='quantity'))
                        }
                        if gf == 'letter':
                            cat['letter'] = gv
                        else:
                            cat['group'] = gv
                        res.append(cat)
        return res
    
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        res: List[dict] = []
        base = url.rstrip('/')
        for p in range(1, pages + 1):
            u = base + '/' if p == 1 else f"{base}/{p}/"
            s = self._get(u)
            if not s:
                break
            for it in s.find_all('div', class_='item'):
                a = it.find('a', class_='link')
                if not a:
                    continue
                vu = urljoin(self.base_url, self._attr(a, 'href'))
                v: dict = {'id': self._id(vu), 'platform': self.name, 'url': vu}
                ti = it.find('div', class_='title-item')
                if ti:
                    title_p = ti.find('p', class_='title')
                    if title_p:
                        v['title'] = self._text(title_p)
                ih = it.find('div', class_='img-holder')
                if ih:
                    thumb = ih.find('img', class_='thumb')
                    if thumb:
                        v['thumbnail'] = self._attr(thumb, 'data-src') or self._attr(thumb, 'src')
                info = it.find('div', class_='info-holder')
                if info:
                    for d in info.find_all('div', class_='item-info'):
                        t = d.find('span', class_='text')
                        ic = d.find('i')
                        if t and ic:
                            classes = ic.get('class')
                            if classes and isinstance(classes, list):
                                cl = ' '.join(classes)
                                tx = t.text.strip()
                                if 'icon-clock' in cl:
                                    v['duration'] = tx
                                elif 'icon-eye' in cl:
                                    v['views'] = self._clean_views(tx)
                                elif 'icon-like' in cl:
                                    v['rating'] = tx
                res.append(v)
            time.sleep(self.config.request_delay)
        return res
    
    def photos(self, page: int = 1) -> List[dict]:
        u = f"{self.base_url}/photos/" if page == 1 else f"{self.base_url}/photos/{page}/"
        s = self._get(u)
        if not s:
            return []
        res: List[dict] = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a:
                continue
            pu = urljoin(self.base_url, self._attr(a, 'href'))
            p: dict = {'id': self._id(pu), 'platform': self.name, 'url': pu}
            
            mt = it.find('div', class_='models-title')
            if mt:
                model_span = mt.find('span', class_='model')
                if model_span:
                    p['title'] = self._text(model_span)
            
            ih = it.find('div', class_='img-holder')
            if ih:
                img_tag = ih.find('img', class_='img')
                if img_tag:
                    p['thumbnail'] = self._attr(img_tag, 'data-src') or self._attr(img_tag, 'src')
            
            info = it.find('div', class_='info')
            if info:
                for d in info.find_all('div', class_='item-info'):
                    t = d.find('span', class_='text')
                    ic = d.find('i')
                    if t and ic:
                        classes = ic.get('class')
                        if classes and isinstance(classes, list):
                            cl = ' '.join(classes)
                            tx = t.text.strip()
                            if 'icon-eye' in cl:
                                p['views'] = tx
                            elif 'icon-camera' in cl:
                                p['photo_count'] = tx
                            elif 'icon-star' in cl:
                                p['rating'] = tx
                            elif 'icon-like' in cl:
                                p['likes'] = tx
                            elif 'icon-calendar' in cl:
                                p['date'] = tx
            
            ch = it.find('div', class_='categor-holder')
            if ch:
                for rw in ch.find_all('div', class_='row'):
                    rt = rw.find('p', class_='row-title')
                    if rt:
                        if 'Студия' in rt.text:
                            row_item = rw.find('span', class_='row-item')
                            if row_item:
                                p['studio'] = self._text(row_item)
                        elif 'Модели' in rt.text:
                            p['models'] = [self._text(m) for m in rw.find_all('span', class_='row-item')]
            res.append(p)
        return res
    
    def models(self, url: Optional[str] = None) -> List[dict]:
        if url is None:
            url = f"{self.base_url}/actresses/"
        s = self._get(url)
        if not s:
            return []
        res: List[dict] = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a:
                continue
            m: dict = {'platform': self.name, 'url': urljoin(self.base_url, self._attr(a, 'href'))}
            ih = it.find('div', class_='img-holder')
            if ih:
                img_tag = ih.find('img', class_='img')
                if img_tag:
                    m['image'] = self._attr(img_tag, 'data-src') or self._attr(img_tag, 'src')
                ci = ih.find('span', class_='country_img')
                if ci:
                    fi = ci.find('img')
                    if fi:
                        m['country'] = self._attr(fi, 'title')
            info = it.find('div', class_='info-holder')
            if info:
                title_p = info.find('p', class_='title')
                if title_p:
                    m['name'] = self._text(title_p)
                qty = info.find('span', class_='quantity')
                if qty:
                    m['video_count'] = self._text(qty)
                rt = info.find('span', class_='rating')
                if rt:
                    m['rating'] = self._text(rt)
            res.append(m)
        return res
    
    def studios(self) -> List[dict]:
        s = self._get(f"{self.base_url}/studios/")
        if not s:
            return []
        res: List[dict] = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a:
                continue
            studio: dict = {
                'platform': self.name,
                'url': urljoin(self.base_url, self._attr(a, 'href')),
                'name': '', 'image': '', 'video_count': ''
            }
            ti = it.find('div', class_='title-item')
            if ti:
                title_p = ti.find('p', class_='title')
                if title_p:
                    studio['name'] = self._text(title_p)
                qty = ti.find('span', class_='quantity')
                if qty:
                    studio['video_count'] = self._text(qty)
            ih = it.find('div', class_='img-holder')
            if ih:
                img_tag = ih.find('img', class_='img')
                if img_tag:
                    studio['image'] = self._attr(img_tag, 'data-src') or self._attr(img_tag, 'src')
            res.append(studio)
        return res
    
    def video_details(self, url: str) -> Optional[dict]:
        s = self._get(url)
        if not s:
            return None
        details: dict = {
            'video_id': self._id(url), 'platform': self.name, 'url': url,
            'description': '', 'likes': '', 'dislikes': '',
            'download_links': [], 'comments': [], 'related_videos': [],
            'tags': [], 'models': [], 'full_views': '',
        }
        title_elem = s.find('h1', class_='title')
        if title_elem:
            details['title'] = title_elem.text.strip()
        
        view_elem = s.find('p', class_='view-video')
        if view_elem:
            bold = view_elem.find('span', class_='bold')
            if bold:
                details['full_views'] = self._clean_views(bold.text.strip())
        
        cat_holder = s.find('div', class_='categor-holder')
        if cat_holder:
            details['categories'] = [{
                'title': a.text.strip(),
                'url': urljoin(self.base_url, self._attr(a, 'href'))
            } for a in cat_holder.find_all('a')]
        
        rating_fav = s.find('div', class_='rating-fav')
        if rating_fav:
            likes_btn = rating_fav.find('a', class_='like')
            if likes_btn:
                qty = likes_btn.find('span', class_='quantity')
                if qty:
                    details['likes'] = qty.text.strip()
            dislikes_btn = rating_fav.find('a', class_='dislike')
            if dislikes_btn:
                qty = dislikes_btn.find('span', class_='quantity')
                if qty:
                    details['dislikes'] = qty.text.strip()
        
        desc_elem = s.find('p', class_='description')
        if desc_elem:
            desc_text = desc_elem.text.strip()
            if 'Теги:' in desc_text:
                parts = desc_text.split('Теги:')
                details['description'] = parts[0].replace('Описание:', '').strip()
                tags_part = parts[1] if len(parts) > 1 else ''
                if 'Модели:' in tags_part:
                    tags_models = tags_part.split('Модели:')
                    details['tags'] = [t.strip() for t in tags_models[0].split(',') if t.strip()]
                    details['models'] = [m.strip() for m in tags_models[1].split(',') if m.strip()]
                else:
                    details['tags'] = [t.strip() for t in tags_part.split(',') if t.strip()]
            elif 'Описание:' in desc_text:
                details['description'] = desc_text.replace('Описание:', '').strip()
        
        for comment in s.find_all('div', class_='comment-item'):
            user_name = comment.find('span', class_='user-name')
            comment_text = comment.find('div', class_='text')
            if user_name and comment_text:
                details['comments'].append({
                    'user': user_name.text.strip(),
                    'text': comment_text.text.strip()
                })
        return details


class Ru5Parser(BaseParser):
    """sosalkino5.ru parseri"""
    
    def __init__(self, c: Config):
        super().__init__("https://sosalkino5.ru", "5ru", c)
    
    def videos(self, **kw: Any) -> List[dict]:
        s = self._get(self.base_url)
        if not s:
            return []
        res: List[dict] = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a:
                continue
            img_tag = a.find('img', class_='thumb')
            title_p = a.find('p', class_='title')
            res.append({
                'id': self._attr(a, 'href', '').replace('/', ''),
                'platform': self.name,
                'url': urljoin(self.base_url, self._attr(a, 'href')),
                'title': self._text(title_p),
                'thumbnail': self._attr(img_tag, 'src'),
            })
        return res
    
    def categories(self) -> List[dict]:
        s = self._get(f"{self.base_url}/category/")
        if not s:
            return []
        res: List[dict] = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a:
                continue
            img_tag = a.find('img', class_='thumb')
            title_p = a.find('p', class_='title')
            res.append({
                'platform': self.name,
                'url': urljoin(self.base_url, self._attr(a, 'href')),
                'title': self._text(title_p),
                'image': urljoin(self.base_url, self._attr(img_tag, 'src'))
            })
        return res
    
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        res: List[dict] = []
        base = url.rstrip('/')
        for p in range(1, pages + 1):
            u = url if p == 1 else f"{base}/{p}/"
            if u.endswith('//'):
                u = u[:-1]
            s = self._get(u)
            if not s:
                break
            for it in s.find_all('div', class_='item'):
                a = it.find('a', class_='link')
                if not a:
                    continue
                vu = urljoin(self.base_url, self._attr(a, 'href'))
                v: dict = {
                    'id': self._attr(a, 'href', '').replace('/', ''),
                    'platform': self.name,
                    'url': vu,
                    'title': self._text(a.find('p', class_='title')),
                    'thumbnail': self._attr(a.find('img', class_='thumb'), 'src'),
                }
                info = it.find('div', class_='info-holder')
                if info:
                    for d in info.find_all('div', class_='item-info'):
                        t = d.find('span', class_='text')
                        ic = d.find('i')
                        if t and ic:
                            classes = ic.get('class')
                            if classes and isinstance(classes, list):
                                cl = ' '.join(classes)
                                tx = t.text.strip()
                                if 'icon-eye' in cl:
                                    v['views'] = tx
                                elif 'icon-like' in cl:
                                    v['rating'] = tx
                                elif 'icon-calendar' in cl:
                                    v['date_added'] = tx
                res.append(v)
            time.sleep(self.config.request_delay)
        return res
    
    def video_details(self, url: str) -> Optional[dict]:
        s = self._get(url)
        if not s:
            return None
        details: dict = {
            'video_id': self._id(url), 'platform': self.name, 'url': url,
            'description': '', 'likes': '', 'dislikes': '',
            'download_links': [], 'comments': [], 'related_videos': [],
            'tags': [], 'models': [], 'full_views': '', 'video_url': '',
        }
        h1 = s.find('h1')
        if h1:
            details['title'] = h1.text.strip()
        
        iframe = s.find('iframe', id='player')
        if iframe:
            details['video_url'] = self._attr(iframe, 'src')
        
        desc_elem = s.find('p', class_='description')
        if desc_elem:
            desc_text = desc_elem.text.strip()
            if 'Теги:' in desc_text:
                parts = desc_text.split('Теги:')
                details['description'] = parts[0].replace('Описание:', '').strip()
                tags_part = parts[1] if len(parts) > 1 else ''
                if 'Модели:' in tags_part:
                    tags_models = tags_part.split('Модели:')
                    details['tags'] = [t.strip() for t in tags_models[0].split(',') if t.strip()]
                    details['models'] = [m.strip() for m in tags_models[1].split(',') if m.strip()]
                else:
                    details['tags'] = [t.strip() for t in tags_part.split(',') if t.strip()]
        
        view_elem = s.find('p', class_='view-video')
        if view_elem:
            bold = view_elem.find('span', class_='bold')
            if bold:
                details['full_views'] = self._clean_views(bold.text.strip())
        
        cat_elem = s.find('div', class_='categor-holder')
        if cat_elem:
            cat_link = cat_elem.find('a')
            if cat_link:
                details['categories'] = [{
                    'title': cat_link.text.strip(),
                    'url': urljoin(self.base_url, self._attr(cat_link, 'href'))
                }]
        return details


# ==================== COLLECTOR ====================

class Collector:
    """Asosiy yig'uvchi klass"""
    
    def __init__(self, config: Optional[Config] = None):
        self.cfg = config if config is not None else Config()
        self.db = Database(self.cfg.db_path)
        self.parsers = {
            'lat': LatParser(self.cfg),
            'best': BestParser(self.cfg),
            '5ru': Ru5Parser(self.cfg)
        }
    
    def collect(self, platform: str, pages: int = 3) -> None:
        """Bitta platformadan ma'lumot yig'ish"""
        p = self.parsers.get(platform)
        if not p:
            logger.error(f"Parser topilmadi: {platform}")
            return
        
        t0 = time.time()
        items = 0
        errs = 0
        
        try:
            logger.info(f"🔄 [{platform}] Ma'lumot yig'ish boshlandi...")
            
            # Kategoriyalar
            for c in p.categories():
                self.db.insert_category(c)
            
            # Videolar
            vids = p.videos_fast(pages) if platform == 'best' else p.videos()
            for v in vids:
                self.db.insert_video(v)
            items += len(vids)
            logger.info(f"[{platform}] {len(vids)} ta video yig'ildi")
            
            # Qo'shimcha ma'lumotlar (faqat best uchun)
            if platform == 'best':
                if self.cfg.collect_photos:
                    for pg in range(1, min(pages, 3) + 1):
                        for ph in p.photos(pg):
                            self.db.insert_photo(ph)
                    logger.info(f"[{platform}] Fotosuratlar yig'ildi")
                
                if self.cfg.collect_models:
                    for m in p.models():
                        self.db.insert_model(m)
                    logger.info(f"[{platform}] Modellar yig'ildi")
                
                if self.cfg.collect_studios:
                    for s in p.studios():
                        self.db.insert_studio(s)
                    logger.info(f"[{platform}] Studiyalar yig'ildi")
            
            # Video tafsilotlari
            if self.cfg.collect_details and vids:
                detail_count = 0
                for v in vids[:self.cfg.max_detail_videos]:
                    details = p.video_details(v['url'])
                    if details:
                        self.db.insert_video_details(details)
                        detail_count += 1
                    time.sleep(0.3)
                items += detail_count
                logger.info(f"[{platform}] Video tafsilotlari: {detail_count} ta")
        
        except Exception as e:
            logger.error(f"[{platform}] Xatolik: {e}", exc_info=True)
            errs += 1
        
        duration = time.time() - t0
        self.db.log_parse(platform, 'collect', items, errs, duration)
        logger.info(f"[{platform}] ✅ {items} items, {duration:.1f}s")
    
    def collect_all(self, pages: int = 3) -> None:
        """Barcha platformalardan ma'lumot yig'ish"""
        print(f"\n🔄 BARCHA PLATFORMALARDAN MA'LUMOT YIG'ISH ({pages} sahifa)...\n")
        for pl in self.cfg.platforms:
            self.collect(pl, pages)
            time.sleep(1)
        print(f"\n✅ Ma'lumot yig'ish yakunlandi!")
        self._show_stats()
    
    def collect_category(self, platform: str, url: str, pages: int = 3) -> int:
        """Kategoriya bo'yicha yig'ish"""
        p = self.parsers.get(platform)
        if not p:
            logger.error(f"Platforma topilmadi: {platform}")
            return 0
        
        vids = p.cat_videos(url, pages)
        for v in vids:
            self.db.insert_video(v)
        
        logger.info(f"[{platform}] Kategoriya: {len(vids)} ta video")
        return len(vids)
    
    def collect_details(self, video_id: str, platform: str) -> Optional[dict]:
        """Bitta video tafsilotlarini yig'ish"""
        p = self.parsers.get(platform)
        if not p:
            return None
        
        videos = self.db.search(video_id, platform=platform, limit=1)
        if not videos:
            logger.warning(f"Video topilmadi: {video_id}")
            return None
        
        url = videos[0].get('url')
        if not url:
            return None
        
        details = p.video_details(str(url))
        if details:
            self.db.insert_video_details(details)
        
        return details
    
    def _show_stats(self) -> None:
        """Statistikani ko'rsatish"""
        s = self.db.get_stats()
        print(f"""
╔══════════════════════════════════════════════╗
║              STATISTIKA                      ║
╠══════════════════════════════════════════════╣
║  Videolar:           {s.get('total_videos',0):>6}                  ║
║  Kategoriyalar:      {s.get('total_categories',0):>6}                  ║
║  Fotosuratlar:       {s.get('total_photos',0):>6}                  ║
║  Modellar:           {s.get('total_models',0):>6}                  ║
║  Studiyalar:         {s.get('total_studios',0):>6}                  ║
║  Video tafsilotlari: {s.get('total_video_details',0):>6}                  ║
║  Unikal kategoriya:  {s.get('unique_categories',0):>6}                  ║
║  O'rtacha ko'rish:   {s.get('avg_views',0):>6}                  ║
║  Oxirgi yangilash:   {str(s.get('last_update','N/A'))[:19]}  ║
╚══════════════════════════════════════════════╝""")
    
    def search(self, q: str, platform: Optional[str] = None,
               category: Optional[str] = None) -> List[dict]:
        return self.db.search(q, platform, category)
    
    def top_videos(self, limit: int = 20, platform: Optional[str] = None) -> List[dict]:
        return self.db.get_top_videos(limit, platform)
    
    def get_details(self, video_id: str, platform: str) -> Optional[dict]:
        return self.db.get_video_details(video_id, platform)
    
    def backup(self) -> str:
        return self.db.backup(self.cfg.backup_dir)
    
    def restore(self, path: str) -> bool:
        return self.db.restore(path)
    
    def cleanup(self) -> int:
        return self.db.cleanup_duplicates()
    
    def export_json(self, fn: Optional[str] = None) -> str:
        """JSON eksport"""
        if fn is None:
            fn = f"export_{datetime.now():%Y%m%d_%H%M%S}.json"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        video_count = self.db.get_table_count('videos')
        if video_count == 0:
            print("\n❌ XATOLIK: Ma'lumotlar bazasida video yo'q!")
            print("   Avval ma'lumot yig'ing: python collector.py --collect all --pages 3")
            return ""
        
        t0 = time.time()
        success, written = self.db.export_json_full(str(fp))
        
        if success:
            mb = fp.stat().st_size / (1024 * 1024) if fp.exists() else 0
            print(f"\n✅ Eksport muvaffaqiyatli!")
            print(f"   📁 Fayl: {fp}")
            print(f"   📊 Videolar: {written} ta")
            print(f"   💾 Hajmi: {mb:.1f} MB ({time.time()-t0:.1f}s)")
            return str(fp)
        else:
            print(f"\n❌ Eksportda xatolik yuz berdi!")
            return ""
    
    def export_csv(self, platform: Optional[str] = None) -> str:
        """CSV eksport"""
        fn = f"videos_{datetime.now():%Y%m%d_%H%M%S}.csv"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        exported, total = self.db.export_csv(str(fp), platform)
        
        if exported > 0:
            mb = fp.stat().st_size / (1024 * 1024) if fp.exists() else 0
            print(f"\n✅ CSV eksport muvaffaqiyatli!")
            print(f"   📁 Fayl: {fp}")
            print(f"   📊 Videolar: {exported}/{total} ta")
            print(f"   💾 Hajmi: {mb:.1f} MB")
            return str(fp)
        else:
            print(f"\n❌ Eksport qilinadigan ma'lumot yo'q!")
            print("   Avval ma'lumot yig'ing: python collector.py --collect all --pages 3")
            return ""
    
    def export_urls(self, platform: Optional[str] = None) -> str:
        """URL eksport"""
        fn = f"mp4_urls_{datetime.now():%Y%m%d_%H%M%S}.txt"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        total_urls = self.db.export_mp4_urls(str(fp), platform)
        
        if total_urls > 0:
            print(f"\n✅ URL eksport muvaffaqiyatli!")
            print(f"   📁 Fayl: {fp}")
            print(f"   🔗 URL lar: {total_urls} ta")
            return str(fp)
        else:
            print(f"\n❌ Eksport qilinadigan URL yo'q!")
            print("   Avval ma'lumot yig'ing: python collector.py --collect all --pages 3")
            return ""


# ==================== CLI ====================

def main() -> None:
    """Asosiy CLI interfeysi"""
    parser = argparse.ArgumentParser(
        description='XXX Content Collector - Professional Web Parser v9.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔══════════════════════════════════════════════════╗
║                FOYDALANISH MISSOLLARI             ║
╠══════════════════════════════════════════════════╣
║  python collector.py --collect all --pages 5     ║
║  python collector.py --collect best --pages 3    ║
║  python collector.py --search "query"            ║
║  python collector.py --top 20 --platform best    ║
║  python collector.py --export json               ║
║  python collector.py --export csv --platform lat ║
║  python collector.py --export urls               ║
║  python collector.py --stats                     ║
║  python collector.py --backup                    ║
║  python collector.py --cleanup                   ║
╚══════════════════════════════════════════════════╝
        """
    )
    
    # Asosiy buyruqlar
    parser.add_argument('--collect', '-c', choices=['all', 'lat', 'best', '5ru'],
                       help='Platformadan ma\'lumot yig\'ish')
    parser.add_argument('--pages', '-p', type=int, default=3,
                       help='Sahifalar soni (default: 3)')
    
    # Eksport
    parser.add_argument('--export', '-e', choices=['json', 'csv', 'urls'],
                       help='Eksport turi')
    parser.add_argument('--platform', '-pl', help='Platforma filtri')
    
    # Qidiruv va ko'rish
    parser.add_argument('--search', '-s', help='Video qidirish')
    parser.add_argument('--top', '-t', type=int, help='Top videolarni ko\'rsatish')
    parser.add_argument('--details', '-d', help='Video tafsilotlarini olish (video_id)')
    parser.add_argument('--category', help='Kategoriya filtri')
    
    # Boshqaruv
    parser.add_argument('--stats', action='store_true', help='Statistikani ko\'rsatish')
    parser.add_argument('--backup', action='store_true', help='Backup yaratish')
    parser.add_argument('--restore', help='Backupdan tiklash (fayl yo\'li)')
    parser.add_argument('--cleanup', action='store_true', help='Duplikatlarni tozalash')
    parser.add_argument('--verbose', '-v', action='store_true', help='Batafsil log')
    parser.add_argument('--config', default='config.json', help='Konfiguratsiya fayli')
    parser.add_argument('--no-details', action='store_true', 
                       help='Video tafsilotlarini yig\'maslik')
    
    args = parser.parse_args()
    
    # Konfiguratsiya
    cfg = Config.from_file(args.config) if Path(args.config).exists() else Config()
    if args.verbose:
        cfg.log_level = 'DEBUG'
    if args.no_details:
        cfg.collect_details = False
    
    # Logger
    global logger
    logger = setup_logging(args.verbose)
    
    # Collector
    col = Collector(cfg)
    
    # Buyruqlarni bajarish
    if args.backup:
        path = col.backup()
        print(f"✅ Backup: {path}")
    
    if args.restore:
        if col.restore(args.restore):
            print(f"✅ Backup tiklandi: {args.restore}")
        else:
            print(f"❌ Tiklashda xatolik")
    
    if args.cleanup:
        n = col.cleanup()
        print(f"✅ {n} ta duplikat tozalandi")
    
    if args.collect:
        print(f"\n🔄 {args.collect.upper()} platformasidan ma'lumot yig'ilmoqda...")
        if args.collect == 'all':
            col.collect_all(args.pages)
        else:
            col.collect(args.collect, args.pages)
        print(f"✅ Ma'lumot yig'ish yakunlandi!")
    
    if args.stats:
        col._show_stats()
    
    if args.details:
        pl = args.platform or 'best'
        details = col.get_details(args.details, pl)
        if details:
            print(json.dumps(details, ensure_ascii=False, indent=2))
        else:
            print(f"❌ Tafsilotlar topilmadi: {args.details}")
    
    if args.search:
        print(f"\n🔍 Qidirilmoqda: {args.search}")
        results = col.search(args.search, args.platform, args.category)
        if results:
            for v in results[:20]:
                print(f"  [{v['platform']}] {str(v.get('title',''))[:60]} - {v.get('views','')}")
                if v.get('description'):
                    print(f"    📝 {str(v.get('description',''))[:100]}...")
            print(f"\n✅ {len(results)} ta natija topildi")
        else:
            print(f"\n❌ Hech narsa topilmadi!")
    
    if args.top:
        videos = col.top_videos(args.top, args.platform)
        if videos:
            for i, v in enumerate(videos, 1):
                premium = " 💎" if v.get('is_premium') else ""
                print(f"  {i}. [{v['platform']}]{premium} "
                      f"{str(v.get('title',''))[:50]} - {v.get('views','')}")
        else:
            print(f"\n❌ Video topilmadi!")
    
    if args.export:
        if args.export == 'json':
            col.export_json()
        elif args.export == 'csv':
            col.export_csv(args.platform)
        elif args.export == 'urls':
            col.export_urls(args.platform)
    
    # Interaktiv menyu
    if not any([args.collect, args.export, args.search, args.top, args.stats,
                args.backup, args.restore, args.cleanup, args.details]):
        interactive_menu(col)


def interactive_menu(col: Collector) -> None:
    """Interaktiv menyu"""
    print("""
╔══════════════════════════════════════════════════╗
║   XXX CONTENT COLLECTOR - Ultimate Pro v9.0     ║
║   3 platforma • SQLite • To'liq tafsilotlar     ║
╚══════════════════════════════════════════════════╝
    """)
    
    stats = col.db.get_stats()
    video_count = stats.get('total_videos', 0)
    if video_count == 0:
        print("⚠️  MA'LUMOTLAR BAZASI BO'SH!")
        print("   Eksport qilishdan oldin 1-4 bandlardan birini tanlang!\n")
    
    while True:
        print("""
╔══════════════════════════════════════════════╗
║              MENYU                           ║
╠══════════════════════════════════════════════╣
║  1. Barcha platformalardan yig'ish          ║
║  2. Faqat LAT    3. Faqat BEST              ║
║  4. Faqat 5RU    5. Kategoriyadan videolar  ║
║  6. Qidirish     7. Top videolar            ║
║  8. Video tafsilotlari                      ║
║  9. JSON eksport 10. CSV eksport            ║
║  11. MP4 URL eksport                        ║
║  12. Statistika  13. Backup yaratish        ║
║  14. Duplikatlarni tozalash                 ║
║  0. Chiqish                                 ║
╚══════════════════════════════════════════════╝
        """)
        
        ch = input("Tanlang: ").strip()
        
        if ch == '1':
            pages = int(input("Sahifalar (1-10): ") or '3')
            col.collect_all(pages)
        elif ch == '2':
            col.collect('lat', 3)
        elif ch == '3':
            col.collect('best', 3)
        elif ch == '4':
            col.collect('5ru', 3)
        elif ch == '5':
            pl = input("Platforma (lat/best/5ru): ").strip()
            url = input("URL: ").strip()
            pages = int(input("Sahifalar: ") or '3')
            n = col.collect_category(pl, url, pages)
            print(f"✅ {n} ta video")
        elif ch == '6':
            q = input("Qidiruv: ").strip()
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            cat_input = input("Kategoriya: ").strip()
            cat = cat_input if cat_input else None
            results = col.search(q, pl, cat)
            if results:
                for v in results[:20]:
                    print(f"  [{v['platform']}] {str(v.get('title',''))[:60]}")
                print(f"\n✅ {len(results)} ta natija")
            else:
                print("\n❌ Hech narsa topilmadi!")
        elif ch == '7':
            n = int(input("Nechta: ") or '20')
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            videos = col.top_videos(n, pl)
            if videos:
                for i, v in enumerate(videos, 1):
                    premium = " 💎" if v.get('is_premium') else ""
                    print(f"  {i}. [{v['platform']}]{premium} "
                          f"{str(v.get('title',''))[:50]} - {v.get('views','')}")
            else:
                print("\n❌ Video topilmadi!")
        elif ch == '8':
            vid = input("Video ID: ").strip()
            pl = input("Platforma: ").strip() or 'best'
            details = col.get_details(vid, pl)
            if details:
                print(json.dumps(details, ensure_ascii=False, indent=2))
            else:
                print("❌ Topilmadi. Yangidan yig'ish kerak.")
                if input("Yig'ishni xohlaysizmi? (ha/yo'q): ").lower() == 'ha':
                    det = col.collect_details(vid, pl)
                    if det:
                        print(json.dumps(det, ensure_ascii=False, indent=2))
        elif ch == '9':
            video_count = col.db.get_table_count('videos')
            if video_count == 0:
                print("\n❌ MA'LUMOTLAR BAZASI BO'SH! Avval 1-4 bandlarni tanlang.")
                continue
            col.export_json()
        elif ch == '10':
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            col.export_csv(pl)
        elif ch == '11':
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            col.export_urls(pl)
        elif ch == '12':
            col._show_stats()
        elif ch == '13':
            fp = col.backup()
            print(f"✅ Backup: {fp}")
        elif ch == '14':
            n = col.cleanup()
            print(f"✅ {n} ta duplikat tozalandi")
        elif ch == '0':
            print("\n👋 Xayr!")
            break
        else:
            print("❌ Noto'g'ri tanlov!")


if __name__ == "__main__":
    main()