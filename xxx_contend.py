#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║     XXX CONTENT COLLECTOR - Ultimate Pro v11.0 - FINAL RELEASE          ║
║     3 Platform • SQLite • Auto Collect • Progress Bar • Multi Export    ║
║     Production Ready • Error Handling • Logging • CLI • Interactive     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

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
import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Union
from pathlib import Path
from abc import ABC, abstractmethod

# ==================== VERSIYA ====================

__version__ = "11.0.0"
__author__ = "XXX Content Collector Team"
__date__ = "2026-05-03"

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
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

# ==================== PROGRESS BAR ====================

def print_progress_bar(iteration: int, total: int, prefix: str = '', suffix: str = '', 
                       length: int = 50, fill: str = '█', print_end: str = "\r") -> None:
    """Konsolda progress barni ko'rsatish"""
    if total == 0:
        return
    
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '░' * (length - filled_length)
    
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
    
    if iteration == total:
        print()

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
    auto_backup: bool = True
    auto_export: bool = True
    auto_cleanup: bool = True
    log_level: str = 'INFO'
    collect_details: bool = True
    collect_photos: bool = True
    collect_models: bool = True
    collect_studios: bool = True
    max_detail_videos: int = 10
    default_pages: int = 3
    export_formats: List[str] = field(default_factory=lambda: ['json', 'csv', 'txt'])
    
    @classmethod
    def from_file(cls, path: str = 'config.json') -> 'Config':
        """JSON fayldan konfiguratsiyani yuklash"""
        if Path(path).exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                logger.error(f"Konfiguratsiya yuklashda xatolik: {e}")
                return cls()
        return cls()
    
    def save(self, path: str = 'config.json') -> None:
        """Konfiguratsiyani JSON faylga saqlash"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._asdict(), f, indent=2, ensure_ascii=False)
    
    def _asdict(self) -> dict:
        """Dataclass ni dict ga o'girish"""
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

# ==================== MA'LUMOTLAR BAZASI ====================

class Database:
    """SQLite ma'lumotlar bazasi boshqaruvi"""
    
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
                
                status_msg = "📊 Baza: " + ", ".join(f"{k}={v}" for k, v in tables.items())
                logger.info(status_msg)
                
                if tables['videos'] == 0:
                    logger.warning("⚠️  Videolar jadvali BO'SH!")
        except Exception as e:
            logger.error(f"Baza tekshirish: {e}")
    
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
    
    # ============ INSERT METODLARI ============
    
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
                return True
        except Exception as e:
            logger.error(f"Video insert: {e}")
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
            logger.error(f"Details insert: {e}")
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
            logger.error(f"Category insert: {e}")
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
            logger.error(f"Photo insert: {e}")
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
            logger.error(f"Model insert: {e}")
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
            logger.error(f"Studio insert: {e}")
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
            logger.error(f"Log parse: {e}")
    
    # ============ SO'ROV METODLARI ============
    
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
            logger.error(f"Get stats: {e}")
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
            logger.error(f"Search: {e}")
            return []
    
    def get_top_videos(self, limit: int = 20, platform: Optional[str] = None) -> List[dict]:
        """Top videolar"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('''SELECT * FROM videos 
                        WHERE platform=? AND views!="" 
                        ORDER BY CAST(REPLACE(views," ","") AS INTEGER) DESC LIMIT ?''', 
                        (platform, limit))
                else:
                    c.execute('''SELECT * FROM videos 
                        WHERE views!="" 
                        ORDER BY CAST(REPLACE(views," ","") AS INTEGER) DESC LIMIT ?''', 
                        (limit,))
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Top videos: {e}")
            return []
    
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
        """Kengaytirilgan video olish"""
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
                
                where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
                
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
                
                count_sql = f'SELECT COUNT(*) FROM videos {where}'
                c.execute(count_sql, params)
                total = c.fetchone()[0]
                
                sql = f'SELECT * FROM videos {where} ORDER BY {sort_field} {order} LIMIT ? OFFSET ?'
                c.execute(sql, params + [limit, offset])
                return [dict(r) for r in c.fetchall()], total
        except Exception as e:
            logger.error(f"Get videos: {e}")
            return [], 0
    
    def get_categories(self, platform: Optional[str] = None,
                       group: Optional[str] = None,
                       letter: Optional[str] = None) -> List[dict]:
        """Kategoriyalarni olish"""
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
                
                where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
                c.execute(f'SELECT * FROM categories {where} ORDER BY title')
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Get categories: {e}")
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
                
                where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
                allowed_sort = ['created_at', 'views', 'rating', 'likes']
                if sort_by not in allowed_sort:
                    sort_by = 'created_at'
                
                c.execute(f'SELECT * FROM photos {where} ORDER BY {sort_by} DESC LIMIT ?', 
                         params + [limit])
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Get photos: {e}")
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
                
                where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
                
                if sort_by == 'video_count':
                    order = 'ORDER BY CAST(video_count AS INTEGER) DESC'
                elif sort_by == 'rating':
                    order = 'ORDER BY CAST(rating AS REAL) DESC'
                else:
                    order = f'ORDER BY {sort_by}'
                
                c.execute(f'SELECT * FROM models {where} {order} LIMIT ?', params + [limit])
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Get models: {e}")
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
                
                where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
                c.execute(f'''SELECT * FROM studios {where} 
                    ORDER BY CAST(video_count AS INTEGER) DESC LIMIT ?''', params + [limit])
                return [dict(r) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Get studios: {e}")
            return []
    
    def get_video_details(self, video_id: str, platform: str) -> Optional[dict]:
        """Video tafsilotlari"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('SELECT * FROM video_details WHERE video_id=? AND platform=?',
                         (video_id, platform))
                r = c.fetchone()
                return dict(r) if r else None
        except Exception as e:
            logger.error(f"Get details: {e}")
            return None
    
    def get_all_data(self, platform: Optional[str] = None) -> dict:
        """Barcha ma'lumotlar"""
        try:
            data = {
                'export_date': datetime.now().isoformat(),
                'database': self.db_path,
                'statistics': self.get_stats(),
                'videos': self.get_videos(platform=platform, limit=10000)[0],
                'categories': self.get_categories(platform=platform),
                'photos': self.get_photos(platform=platform),
                'models': self.get_models(platform=platform),
                'studios': self.get_studios(platform=platform),
                'video_details': []
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
            logger.error(f"Get all data: {e}")
            return {}
    
    def get_unique_values(self, column: str, table: str = 'videos',
                          platform: Optional[str] = None) -> List[str]:
        """Unikal qiymatlar"""
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
            logger.error(f"Get unique: {e}")
            return []
    
    # ============ BACKUP/RESTORE ============
    
    def backup(self, backup_dir: str = 'backups') -> str:
        """Zaxiralash"""
        Path(backup_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = Path(backup_dir) / f'xxx_collector_backup_{timestamp}.db'
        
        with self.lock:
            backup_conn = sqlite3.connect(str(backup_path))
            self.conn.backup(backup_conn)
            backup_conn.close()
        
        self._cleanup_old_backups(backup_dir)
        logger.info(f"Backup: {backup_path}")
        return str(backup_path)
    
    def restore(self, backup_path: str) -> bool:
        """Tiklash"""
        try:
            if not Path(backup_path).exists():
                logger.error(f"Backup topilmadi: {backup_path}")
                return False
            with self.lock:
                backup_conn = sqlite3.connect(backup_path)
                backup_conn.backup(self.conn)
                backup_conn.close()
            logger.info(f"Restore: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore: {e}")
            return False
    
    def _cleanup_old_backups(self, backup_dir: str, days: int = 7) -> None:
        """Eski backuplarni o'chirish"""
        cutoff = datetime.now() - timedelta(days=days)
        for f in Path(backup_dir).glob('xxx_collector_backup_*.db'):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
    
    def cleanup_duplicates(self) -> int:
        """Duplikatlarni tozalash"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('''DELETE FROM videos WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM videos GROUP BY id, platform)''')
                deleted = c.rowcount
                self.conn.commit()
                logger.info(f"Cleanup: {deleted} ta")
                return deleted
        except Exception as e:
            logger.error(f"Cleanup: {e}")
            return 0
    
    # ============ EKSPORT (Progress Bar bilan) ============
    
    def export_json_full(self, filepath: str, chunk_size: int = 1000, 
                         show_progress: bool = True) -> Tuple[bool, int]:
        """To'liq JSON eksport"""
        try:
            video_count = self.get_table_count('videos')
            if video_count == 0:
                logger.warning("Eksport uchun video yo'q!")
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
            written = 0
            
            if show_progress:
                print(f"\n📦 JSON eksport: {total} ta video")
                print_progress_bar(0, total, prefix='JSON:', suffix='0%', length=50)
            
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
                        written += 1
                    
                    offset += len(chunk)
                    if show_progress:
                        print_progress_bar(offset, total, prefix='JSON:', 
                                         suffix=f'{offset}/{total}', length=50)
                
                f.write('\n  ]\n}')
            
            if show_progress:
                print_progress_bar(total, total, prefix='JSON:', suffix=f'{total}/{total} ✅', length=50)
                print()
            
            mb = Path(filepath).stat().st_size / (1024 * 1024) if Path(filepath).exists() else 0
            logger.info(f"JSON: {filepath} ({written} ta, {mb:.1f} MB)")
            return True, written
        except Exception as e:
            logger.error(f"JSON eksport: {e}")
            return False, 0
    
    def export_csv(self, filepath: str, platform: Optional[str] = None, 
                   show_progress: bool = True) -> Tuple[int, int]:
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
                logger.warning("Eksport uchun video yo'q!")
                return 0, 0
            
            if show_progress:
                print(f"\n📊 CSV eksport: {total} ta video")
                print_progress_bar(0, total, prefix='CSV:', suffix='0%', length=50)
            
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
                                WHERE platform=? ORDER BY created_at DESC LIMIT ? OFFSET ?''',
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
                    
                    if show_progress:
                        print_progress_bar(exported, total, prefix='CSV:', 
                                         suffix=f'{exported}/{total}', length=50)
            
            if show_progress:
                print_progress_bar(total, total, prefix='CSV:', suffix=f'{total}/{total} ✅', length=50)
                print()
            
            mb = Path(filepath).stat().st_size / (1024 * 1024) if Path(filepath).exists() else 0
            logger.info(f"CSV: {exported} ta, {mb:.1f} MB")
            return exported, total
        except Exception as e:
            logger.error(f"CSV eksport: {e}")
            return 0, 0
    
    def export_txt(self, filepath: str, platform: Optional[str] = None, 
                   show_progress: bool = True) -> Tuple[int, int]:
        """TXT eksport"""
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('SELECT COUNT(*) FROM videos WHERE platform=?', (platform,))
                else:
                    c.execute('SELECT COUNT(*) FROM videos')
                total = c.fetchone()[0]
            
            if total == 0:
                logger.warning("Eksport uchun video yo'q!")
                return 0, 0
            
            if show_progress:
                print(f"\n📄 TXT eksport: {total} ta video")
                print_progress_bar(0, total, prefix='TXT:', suffix='0%', length=50)
            
            exported = 0
            offset = 0
            chunk_size = 100
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("═" * 80 + "\n")
                f.write(f"XXX CONTENT COLLECTOR v{__version__} - TXT EKSPORT\n")
                f.write(f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Platforma: {platform if platform else 'Barchasi'}\n")
                f.write("═" * 80 + "\n\n")
                
                while offset < total:
                    with self.lock:
                        c = self.conn.cursor()
                        if platform:
                            c.execute('''SELECT * FROM videos 
                                WHERE platform=? ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                                (platform, chunk_size, offset))
                        else:
                            c.execute('''SELECT * FROM videos 
                                ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                                (chunk_size, offset))
                        chunk = [dict(r) for r in c.fetchall()]
                    
                    if not chunk:
                        break
                    
                    for video in chunk:
                        f.write(f"▸ {video.get('title', 'Nomsiz')}\n")
                        f.write(f"  Platforma: {video.get('platform', 'N/A')}\n")
                        f.write(f"  URL: {video.get('url', 'N/A')}\n")
                        f.write(f"  Ko'rishlar: {video.get('views', 'N/A')}\n")
                        f.write(f"  Reyting: {video.get('rating', 'N/A')}\n")
                        f.write(f"  Davomiylik: {video.get('duration', 'N/A')}\n")
                        f.write(f"  Sana: {video.get('date_added', 'N/A')}\n")
                        f.write(f"  Kategoriya: {video.get('category', 'N/A')}\n")
                        f.write(f"  Premium: {'Ha' if video.get('is_premium') else 'Yoq'}\n")
                        if video.get('description'):
                            f.write(f"  Tavsif: {str(video['description'])[:200]}...\n")
                        f.write("\n" + "─" * 40 + "\n\n")
                        exported += 1
                    
                    offset += len(chunk)
                    if show_progress:
                        print_progress_bar(exported, total, prefix='TXT:', 
                                         suffix=f'{exported}/{total}', length=50)
                
                f.write("═" * 80 + "\n")
                f.write(f"Jami: {exported} ta video\n")
                f.write(f"Eksport yakunlangan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if show_progress:
                print_progress_bar(total, total, prefix='TXT:', suffix=f'{total}/{total} ✅', length=50)
                print()
            
            mb = Path(filepath).stat().st_size / (1024 * 1024) if Path(filepath).exists() else 0
            logger.info(f"TXT: {exported} ta, {mb:.1f} MB")
            return exported, total
        except Exception as e:
            logger.error(f"TXT eksport: {e}")
            return 0, 0
    
    def export_mp4_urls(self, filepath: str, platform: Optional[str] = None, 
                        show_progress: bool = True) -> int:
        """MP4 URL eksport"""
        try:
            if show_progress:
                print(f"\n🔗 URL eksport...")
                print_progress_bar(0, 100, prefix='URL:', suffix='Yig\'ilmoqda...', length=50)
            
            with self.lock:
                c = self.conn.cursor()
                urls: set = set()
                
                if platform:
                    c.execute('''SELECT video_urls FROM videos 
                        WHERE video_urls IS NOT NULL AND video_urls!="[]" AND platform=?''', 
                        (platform,))
                else:
                    c.execute('''SELECT video_urls FROM videos 
                        WHERE video_urls IS NOT NULL AND video_urls!="[]"''')
                
                rows = c.fetchall()
                for i, row in enumerate(rows):
                    try:
                        loaded = json.loads(row[0]) if row[0] else []
                        for u in loaded:
                            if u and str(u).strip():
                                urls.add(str(u).strip())
                    except:
                        pass
                    if show_progress and rows:
                        progress = int((i + 1) / len(rows) * 50)
                        print_progress_bar(progress, 100, prefix='URL:', suffix=f'{progress}%', length=50)
                
                if platform:
                    c.execute('''SELECT download_links FROM video_details 
                        WHERE download_links IS NOT NULL AND download_links!="[]" AND platform=?''', 
                        (platform,))
                else:
                    c.execute('''SELECT download_links FROM video_details 
                        WHERE download_links IS NOT NULL AND download_links!="[]"''')
                
                details_rows = c.fetchall()
                for i, row in enumerate(details_rows):
                    try:
                        loaded = json.loads(row[0]) if row[0] else []
                        for dl in loaded:
                            if isinstance(dl, dict) and dl.get('url'):
                                urls.add(str(dl['url']))
                            elif isinstance(dl, str) and dl.strip():
                                urls.add(dl.strip())
                    except:
                        pass
                    if show_progress and details_rows:
                        progress = 50 + int((i + 1) / len(details_rows) * 30)
                        print_progress_bar(progress, 100, prefix='URL:', suffix=f'{progress}%', length=50)
            
            total_urls = len(urls)
            
            if total_urls == 0:
                if show_progress:
                    print_progress_bar(100, 100, prefix='URL:', suffix='URL yo\'q ❌', length=50)
                    print()
                logger.warning("Eksport uchun URL yo'q!")
                return 0
            
            if show_progress:
                print_progress_bar(80, 100, prefix='URL:', suffix=f'Yozilmoqda...', length=50)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                sorted_urls = sorted(urls)
                for i, u in enumerate(sorted_urls):
                    f.write(u + '\n')
                    if show_progress and i % max(1, len(sorted_urls) // 10) == 0:
                        progress = 80 + int((i + 1) / len(sorted_urls) * 20)
                        print_progress_bar(progress, 100, prefix='URL:', suffix=f'{progress}%', length=50)
            
            if show_progress:
                print_progress_bar(100, 100, prefix='URL:', suffix=f'{total_urls} ta ✅', length=50)
                print()
            
            mb = Path(filepath).stat().st_size / (1024 * 1024) if Path(filepath).exists() else 0
            logger.info(f"URL: {total_urls} ta, {mb:.1f} MB")
            return total_urls
        except Exception as e:
            logger.error(f"URL eksport: {e}")
            return 0
    
    def export_all_formats(self, platform: Optional[str] = None, 
                           export_dir: str = 'exports') -> Dict[str, str]:
        """Barcha formatlarda eksport"""
        Path(export_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results = {}
        
        # JSON
        json_path = str(Path(export_dir) / f'export_{timestamp}.json')
        success, count = self.export_json_full(json_path)
        if success:
            results['json'] = json_path
            
        # CSV
        csv_path = str(Path(export_dir) / f'videos_{timestamp}.csv')
        exported, total = self.export_csv(csv_path, platform)
        if exported > 0:
            results['csv'] = csv_path
            
        # TXT
        txt_path = str(Path(export_dir) / f'videos_{timestamp}.txt')
        exported, total = self.export_txt(txt_path, platform)
        if exported > 0:
            results['txt'] = txt_path
            
        # URL
        url_path = str(Path(export_dir) / f'mp4_urls_{timestamp}.txt')
        count = self.export_mp4_urls(url_path, platform)
        if count > 0:
            results['urls'] = url_path
            
        return results


# ==================== BASE PARSER ====================

class BaseParser(ABC):
    """Barcha parserlar uchun asos klass"""
    
    def __init__(self, base_url: str, name: str, config: Config):
        self.base_url = base_url
        self.name = name
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
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
                    logger.warning(f"[{self.name}] Rate limit: {wait}s")
                    time.sleep(wait)
            except Exception as e:
                logger.warning(f"[{self.name}] So'rov ({attempt+1}/{retries}): {e}")
                time.sleep(1)
        return None
    
    def _text(self, e: Any) -> str:
        return e.get_text(strip=True) if e else ''
    
    def _attr(self, e: Any, a: str, default: str = '') -> str:
        if e is None:
            return default
        v = e.get(a, default)
        if v is None:
            return default
        if isinstance(v, list):
            return ' '.join(str(x) for x in v)
        return str(v)
    
    def _id(self, url: str) -> str:
        if not url:
            return ''
        parts = url.rstrip('/').split('/')
        skip = ['video', 'photos', 'categories', 'actresses', 'studios']
        for part in reversed(parts):
            if part and part not in skip:
                return part
        return parts[-1] if parts else ''
    
    def _clean_views(self, views_str: str) -> str:
        if not views_str:
            return ''
        return re.sub(r'[\s\u2009\u00A0]', '', views_str)
    
    @abstractmethod
    def videos(self, **kw: Any) -> List[dict]:
        pass
    
    @abstractmethod
    def categories(self) -> List[dict]:
        pass
    
    def video_details(self, url: str) -> Optional[dict]:
        return None
    
    def photos(self, page: int = 1) -> List[dict]:
        return []
    
    def models(self, url: Optional[str] = None) -> List[dict]:
        return []
    
    def studios(self) -> List[dict]:
        return []
    
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        return []


# ==================== PARSERLAR (qisqartirilgan) ====================

class LatParser(BaseParser):
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
                    'id': self._id(url), 'platform': self.name, 'url': url,
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
                    'id': self._id(vu), 'platform': self.name, 'url': vu,
                    'title': self._text(v.find('span', class_='videotitle')),
                    'category': cn,
                    'thumbnail': self._attr(img, 'data-original') or self._attr(img, 'src'),
                    'duration': self._text(v.find('div', class_='videoduration')),
                    'views': self._clean_views(self._text(v.find('span', class_='videoviews'))),
                })
            time.sleep(self.config.request_delay)
        return res


class BestParser(BaseParser):
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


class Ru5Parser(BaseParser):
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
            res.append({
                'id': self._attr(a, 'href', '').replace('/', ''),
                'platform': self.name,
                'url': urljoin(self.base_url, self._attr(a, 'href')),
                'title': self._text(a.find('p', class_='title')),
                'thumbnail': self._attr(a.find('img', class_='thumb'), 'src'),
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
                    'platform': self.name, 'url': vu,
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


# ==================== COLLECTOR ====================

class Collector:
    """Asosiy yig'uvchi klass - AVTOMATLASHTIRILGAN"""
    
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
            print(f"\n🔄 [{platform.upper()}] Ma'lumot yig'ish ({pages} sahifa)...")
            
            # Kategoriyalar
            cats = p.categories()
            for c in cats:
                self.db.insert_category(c)
            logger.info(f"[{platform}] {len(cats)} kategoriya")
            
            # Videolar
            vids = p.videos_fast(pages) if platform == 'best' else p.videos()
            for v in vids:
                self.db.insert_video(v)
            items += len(vids)
            print(f"   ✅ {len(vids)} ta video yig'ildi")
            
            # Qo'shimcha (best)
            if platform == 'best':
                if self.cfg.collect_photos:
                    for pg in range(1, min(pages, 3) + 1):
                        for ph in p.photos(pg):
                            self.db.insert_photo(ph)
                
                if self.cfg.collect_models:
                    for m in p.models():
                        self.db.insert_model(m)
                
                if self.cfg.collect_studios:
                    for s in p.studios():
                        self.db.insert_studio(s)
            
            # Tafsilotlar
            if self.cfg.collect_details and vids:
                detail_count = 0
                for v in vids[:self.cfg.max_detail_videos]:
                    details = p.video_details(v['url'])
                    if details:
                        self.db.insert_video_details(details)
                        detail_count += 1
                    time.sleep(0.3)
                items += detail_count
        
        except Exception as e:
            logger.error(f"[{platform}] Xatolik: {e}")
            errs += 1
        
        duration = time.time() - t0
        self.db.log_parse(platform, 'collect', items, errs, duration)
        print(f"   ⏱️  {duration:.1f}s | 📊 {items} items")
    
    def collect_all(self, pages: int = 3) -> None:
        """Barcha platformalardan ma'lumot yig'ish"""
        print(f"\n{'='*60}")
        print(f"🔄 AVTOMATIK YIG'ISH: {len(self.cfg.platforms)} platforma, {pages} sahifa")
        print(f"{'='*60}")
        
        total_start = time.time()
        for pl in self.cfg.platforms:
            self.collect(pl, pages)
            time.sleep(1)
        
        total_duration = time.time() - total_start
        print(f"\n{'='*60}")
        print(f"✅ Yig'ish yakunlandi! ⏱️  {total_duration:.1f}s")
        print(f"{'='*60}")
        self._show_stats()
        
        # Avtomatik amallar
        if self.cfg.auto_cleanup:
            self.cleanup()
        
        if self.cfg.auto_backup:
            self.backup()
        
        if self.cfg.auto_export:
            self.export_all_formats()
    
    def collect_category(self, platform: str, url: str, pages: int = 3) -> int:
        """Kategoriya bo'yicha yig'ish"""
        p = self.parsers.get(platform)
        if not p:
            logger.error(f"Platforma topilmadi: {platform}")
            return 0
        
        vids = p.cat_videos(url, pages)
        for v in vids:
            self.db.insert_video(v)
        
        return len(vids)
    
    def _show_stats(self) -> None:
        """Statistikani ko'rsatish"""
        s = self.db.get_stats()
        print(f"""
┌──────────────────────────────────────────────────────┐
│                    STATISTIKA                         │
├──────────────────────────────────────────────────────┤
│  📹 Videolar:           {s.get('total_videos',0):>6}                         │
│  📂 Kategoriyalar:      {s.get('total_categories',0):>6}                         │
│  📷 Fotosuratlar:       {s.get('total_photos',0):>6}                         │
│  👤 Modellar:           {s.get('total_models',0):>6}                         │
│  🏢 Studiyalar:         {s.get('total_studios',0):>6}                         │
│  📋 Video tafsilotlari: {s.get('total_video_details',0):>6}                         │
│  🔍 Unikal kategoriya:  {s.get('unique_categories',0):>6}                         │
│  👁️  O'rtacha ko'rish:   {s.get('avg_views',0):>6}                         │
│  🕐 Oxirgi yangilash:   {str(s.get('last_update','N/A'))[:19]} │
└──────────────────────────────────────────────────────┘""")
    
    def search(self, q: str, platform: Optional[str] = None,
               category: Optional[str] = None) -> List[dict]:
        return self.db.search(q, platform, category)
    
    def top_videos(self, limit: int = 20, platform: Optional[str] = None) -> List[dict]:
        return self.db.get_top_videos(limit, platform)
    
    def get_details(self, video_id: str, platform: str) -> Optional[dict]:
        return self.db.get_video_details(video_id, platform)
    
    def backup(self) -> str:
        print(f"\n💾 Backup yaratilmoqda...")
        path = self.db.backup(self.cfg.backup_dir)
        print(f"   ✅ Backup: {path}")
        return path
    
    def restore(self, path: str) -> bool:
        return self.db.restore(path)
    
    def cleanup(self) -> int:
        n = self.db.cleanup_duplicates()
        if n > 0:
            print(f"   🧹 {n} ta duplikat tozalandi")
        return n
    
    def export_json(self, fn: Optional[str] = None) -> str:
        """JSON eksport"""
        if fn is None:
            fn = f"export_{datetime.now():%Y%m%d_%H%M%S}.json"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        video_count = self.db.get_table_count('videos')
        if video_count == 0:
            print("\n❌ Ma'lumotlar bazasida video yo'q!")
            return ""
        
        t0 = time.time()
        success, written = self.db.export_json_full(str(fp))
        
        if success:
            mb = fp.stat().st_size / (1024 * 1024) if fp.exists() else 0
            print(f"   📁 {fp.name} | 📊 {written} ta | 💾 {mb:.1f} MB | ⏱️ {time.time()-t0:.1f}s")
            return str(fp)
        return ""
    
    def export_csv(self, platform: Optional[str] = None) -> str:
        """CSV eksport"""
        fn = f"videos_{datetime.now():%Y%m%d_%H%M%S}.csv"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        t0 = time.time()
        exported, total = self.db.export_csv(str(fp), platform)
        
        if exported > 0:
            mb = fp.stat().st_size / (1024 * 1024) if fp.exists() else 0
            print(f"   📁 {fp.name} | 📊 {exported}/{total} ta | 💾 {mb:.1f} MB | ⏱️ {time.time()-t0:.1f}s")
            return str(fp)
        return ""
    
    def export_txt(self, platform: Optional[str] = None) -> str:
        """TXT eksport"""
        fn = f"videos_{datetime.now():%Y%m%d_%H%M%S}.txt"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        t0 = time.time()
        exported, total = self.db.export_txt(str(fp), platform)
        
        if exported > 0:
            mb = fp.stat().st_size / (1024 * 1024) if fp.exists() else 0
            print(f"   📁 {fp.name} | 📊 {exported}/{total} ta | 💾 {mb:.1f} MB | ⏱️ {time.time()-t0:.1f}s")
            return str(fp)
        return ""
    
    def export_urls(self, platform: Optional[str] = None) -> str:
        """URL eksport"""
        fn = f"mp4_urls_{datetime.now():%Y%m%d_%H%M%S}.txt"
        fp = Path(self.cfg.export_dir) / fn
        fp.parent.mkdir(exist_ok=True)
        
        t0 = time.time()
        total_urls = self.db.export_mp4_urls(str(fp), platform)
        
        if total_urls > 0:
            mb = fp.stat().st_size / (1024 * 1024) if fp.exists() else 0
            print(f"   📁 {fp.name} | 🔗 {total_urls} ta | 💾 {mb:.1f} MB | ⏱️ {time.time()-t0:.1f}s")
            return str(fp)
        return ""
    
    def export_all_formats(self, platform: Optional[str] = None) -> Dict[str, str]:
        """Barcha formatlarda eksport"""
        print(f"\n📦 BARCHA FORMATLARDA EKSPORT...")
        print(f"{'─'*50}")
        results = self.db.export_all_formats(platform, self.cfg.export_dir)
        print(f"{'─'*50}")
        print(f"✅ Jami: {len(results)} ta format")
        for fmt, path in results.items():
            print(f"   📁 {fmt.upper()}: {path}")
        return results
    
    def run_auto(self, pages: int = 3) -> None:
        """To'liq avtomatik ish rejimi"""
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║         XXX CONTENT COLLECTOR v{__version__}                     ║
║              AVTOMATIK ISH REJIMI                            ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Yig'ish
        self.collect_all(pages)
        
        # 2. Eksport
        self.export_all_formats()
        
        # 3. Statistika
        self._show_stats()
        
        print(f"\n✅ BARCHA AMALLAR BAJARILDI!")


# ==================== CLI ====================

def main() -> None:
    """Asosiy CLI"""
    parser = argparse.ArgumentParser(
        description=f'XXX Content Collector v{__version__}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔══════════════════════════════════════════════════════════╗
║              FOYDALANISH MISSOLLARI                       ║
╠══════════════════════════════════════════════════════════╣
║  python collector.py --auto                              ║
║  python collector.py --collect all --pages 5             ║
║  python collector.py --collect best --pages 3            ║
║  python collector.py --search "query"                    ║
║  python collector.py --top 20 --platform best            ║
║  python collector.py --export json                       ║
║  python collector.py --export-all                        ║
║  python collector.py --stats                             ║
║  python collector.py --backup                            ║
╚══════════════════════════════════════════════════════════╝
        """
    )
    
    # Asosiy
    parser.add_argument('--collect', '-c', choices=['all', 'lat', 'best', '5ru'],
                       help='Ma\'lumot yig\'ish')
    parser.add_argument('--pages', '-p', type=int, default=3,
                       help='Sahifalar soni (default: 3)')
    parser.add_argument('--auto', '-a', action='store_true',
                       help='To\'liq avtomatik rejim')
    
    # Eksport
    parser.add_argument('--export', '-e', choices=['json', 'csv', 'txt', 'urls'],
                       help='Eksport turi')
    parser.add_argument('--export-all', action='store_true',
                       help='Barcha formatlarda eksport')
    parser.add_argument('--platform', '-pl', help='Platforma filtri')
    
    # Qidiruv
    parser.add_argument('--search', '-s', help='Video qidirish')
    parser.add_argument('--top', '-t', type=int, help='Top videolar')
    parser.add_argument('--details', '-d', help='Video tafsilotlari (video_id)')
    parser.add_argument('--category', help='Kategoriya filtri')
    
    # Boshqaruv
    parser.add_argument('--stats', action='store_true', help='Statistika')
    parser.add_argument('--backup', action='store_true', help='Backup')
    parser.add_argument('--restore', help='Backupdan tiklash')
    parser.add_argument('--cleanup', action='store_true', help='Duplikatlarni tozalash')
    parser.add_argument('--verbose', '-v', action='store_true', help='Batafsil log')
    parser.add_argument('--config', default='config.json', help='Konfiguratsiya fayli')
    parser.add_argument('--version', action='version', version=f'v{__version__}')
    
    args = parser.parse_args()
    
    # Konfiguratsiya
    cfg = Config.from_file(args.config) if Path(args.config).exists() else Config()
    if args.verbose:
        cfg.log_level = 'DEBUG'
    
    global logger
    logger = setup_logging(args.verbose)
    
    col = Collector(cfg)
    
    # AVTOMATIK REJIM
    if args.auto:
        col.run_auto(args.pages)
        return
    
    # Boshqa buyruqlar
    if args.backup:
        col.backup()
    
    if args.restore:
        if col.restore(args.restore):
            print(f"✅ Tiklandi: {args.restore}")
        else:
            print(f"❌ Xatolik!")
    
    if args.cleanup:
        col.cleanup()
    
    if args.collect:
        if args.collect == 'all':
            col.collect_all(args.pages)
        else:
            col.collect(args.collect, args.pages)
    
    if args.stats:
        col._show_stats()
    
    if args.details:
        pl = args.platform or 'best'
        details = col.get_details(args.details, pl)
        if details:
            print(json.dumps(details, ensure_ascii=False, indent=2))
        else:
            print(f"❌ Topilmadi: {args.details}")
    
    if args.search:
        results = col.search(args.search, args.platform, args.category)
        if results:
            for v in results[:20]:
                print(f"  [{v['platform']}] {str(v.get('title',''))[:60]} - {v.get('views','')}")
            print(f"\n✅ {len(results)} ta natija")
        else:
            print(f"\n❌ Topilmadi!")
    
    if args.top:
        videos = col.top_videos(args.top, args.platform)
        if videos:
            for i, v in enumerate(videos, 1):
                premium = " 💎" if v.get('is_premium') else ""
                print(f"  {i}. [{v['platform']}]{premium} {str(v.get('title',''))[:50]} - {v.get('views','')}")
        else:
            print(f"\n❌ Topilmadi!")
    
    if args.export:
        if args.export == 'json':
            col.export_json()
        elif args.export == 'csv':
            col.export_csv(args.platform)
        elif args.export == 'txt':
            col.export_txt(args.platform)
        elif args.export == 'urls':
            col.export_urls(args.platform)
    
    if args.export_all:
        col.export_all_formats(args.platform)
    
    # Interaktiv menyu
    if not any([args.collect, args.export, args.export_all, args.search, args.top, 
                args.stats, args.backup, args.restore, args.cleanup, args.details, args.auto]):
        interactive_menu(col)


def interactive_menu(col: Collector) -> None:
    """Interaktiv menyu"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     XXX CONTENT COLLECTOR v{__version__}                          ║
║     3 Platforma • SQLite • Avtomatik • CLI                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    stats = col.db.get_stats()
    video_count = stats.get('total_videos', 0)
    if video_count == 0:
        print("⚠️  MA'LUMOTLAR BAZASI BO'SH!")
        print("   Avval 1-4 bandlardan birini tanlang!\n")
    else:
        print(f"📊 Bazada {video_count} ta video mavjud\n")
    
    while True:
        print("""
┌──────────────────────────────────────────────────────┐
│                      MENYU                           │
├──────────────────────────────────────────────────────┤
│  1. Barcha platformalardan yig'ish                  │
│  2. Faqat LAT        3. Faqat BEST                  │
│  4. Faqat 5RU        5. Kategoriyadan videolar      │
│  6. Qidirish          7. Top videolar               │
│  8. Video tafsilotlari                              │
│  9. JSON eksport      10. CSV eksport               │
│  11. TXT eksport      12. MP4 URL eksport           │
│  13. BARCHA FORMATLARDA EKSPORT                     │
│  14. Statistika       15. Backup yaratish           │
│  16. Duplikatlarni tozalash                         │
│  17. AVTOMATIK ISH REJIMI                           │
│  0. Chiqish                                         │
└──────────────────────────────────────────────────────┘
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
            results = col.search(q, pl)
            if results:
                for v in results[:20]:
                    print(f"  [{v['platform']}] {str(v.get('title',''))[:60]}")
                print(f"\n✅ {len(results)} ta natija")
            else:
                print("\n❌ Topilmadi!")
        elif ch == '7':
            n = int(input("Nechta: ") or '20')
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            videos = col.top_videos(n, pl)
            if videos:
                for i, v in enumerate(videos, 1):
                    premium = " 💎" if v.get('is_premium') else ""
                    print(f"  {i}. [{v['platform']}]{premium} {str(v.get('title',''))[:50]} - {v.get('views','')}")
        elif ch == '8':
            vid = input("Video ID: ").strip()
            pl = input("Platforma: ").strip() or 'best'
            details = col.get_details(vid, pl)
            if details:
                print(json.dumps(details, ensure_ascii=False, indent=2))
            else:
                print("❌ Topilmadi!")
        elif ch == '9':
            col.export_json()
        elif ch == '10':
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            col.export_csv(pl)
        elif ch == '11':
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            col.export_txt(pl)
        elif ch == '12':
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            col.export_urls(pl)
        elif ch == '13':
            pl_input = input("Platforma: ").strip()
            pl = pl_input if pl_input else None
            col.export_all_formats(pl)
        elif ch == '14':
            col._show_stats()
        elif ch == '15':
            col.backup()
        elif ch == '16':
            col.cleanup()
        elif ch == '17':
            pages = int(input("Sahifalar (1-10): ") or '3')
            col.run_auto(pages)
        elif ch == '0':
            print("\n👋 Xayr!")
            break
        else:
            print("❌ Noto'g'ri tanlov!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Dastur to'xtatildi!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Kutilmagan xatolik: {e}", exc_info=True)
        print(f"\n❌ Xatolik yuz berdi: {e}")
        sys.exit(1)