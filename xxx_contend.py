#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  XXX CONTENT COLLECTOR - Ultimate Pro v7.0 - COMPLETE EDITION       ║
║  3 platforma • SQLite • Tezkor eksport • Backup • API • CLI        ║
╚══════════════════════════════════════════════════════════════════════╝
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
import shutil
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from abc import ABC, abstractmethod

# ==================== LOGGING ====================

def setup_logging(verbose: bool = False):
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger('XXXCollector')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    fh = logging.FileHandler(log_dir / f'collector_{datetime.now():%Y%m%d}.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

logger = setup_logging()

# ==================== KONFIG ====================

@dataclass
class Config:
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
    
    @classmethod
    def from_file(cls, path: str = 'config.json') -> 'Config':
        """Konfiguratsiyani JSON fayldan yuklash"""
        if Path(path).exists():
            with open(path, 'r') as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()
    
    def save(self, path: str = 'config.json'):
        """Konfiguratsiyani JSON faylga saqlash"""
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

# ==================== DATABASE ====================

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_tables()
        self._create_indexes()
        logger.info(f"Database: {db_path}")
    
    def _init_tables(self):
        with self.lock:
            c = self.conn.cursor()
            
            # Videos jadvalini tekshirish va tuzatish
            try:
                c.execute("SELECT * FROM videos LIMIT 0")
                cols = [d[0] for d in c.description]
                if len(cols) != 16:
                    logger.warning(f"Videos jadvali noto'g'ri ({len(cols)} ustun). Qayta yaratilmoqda...")
                    c.execute("DROP TABLE IF EXISTS videos")
            except:
                pass
            
            c.execute('''CREATE TABLE IF NOT EXISTS videos (
                id TEXT, platform TEXT DEFAULT '', title TEXT DEFAULT '', url TEXT DEFAULT '',
                thumbnail TEXT DEFAULT '', duration TEXT DEFAULT '', views TEXT DEFAULT '',
                rating TEXT DEFAULT '', date_added TEXT DEFAULT '', category TEXT DEFAULT '',
                tags TEXT DEFAULT '[]', models TEXT DEFAULT '[]', video_urls TEXT DEFAULT '[]',
                is_premium INTEGER DEFAULT 0, created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
                PRIMARY KEY (id, platform))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT DEFAULT '',
                title TEXT DEFAULT '', url TEXT UNIQUE, video_count TEXT DEFAULT '0',
                image TEXT DEFAULT '', letter TEXT DEFAULT '', group_name TEXT DEFAULT '',
                created_at TEXT DEFAULT '')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS photos (
                id TEXT, platform TEXT DEFAULT '', title TEXT DEFAULT '', url TEXT DEFAULT '',
                thumbnail TEXT DEFAULT '', date TEXT DEFAULT '', views TEXT DEFAULT '',
                photo_count TEXT DEFAULT '', rating TEXT DEFAULT '', likes TEXT DEFAULT '',
                studio TEXT DEFAULT '', models TEXT DEFAULT '[]', created_at TEXT DEFAULT '',
                PRIMARY KEY (id, platform))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT DEFAULT '',
                name TEXT DEFAULT '', url TEXT UNIQUE, image TEXT DEFAULT '',
                country TEXT DEFAULT '', video_count TEXT DEFAULT '',
                rating TEXT DEFAULT '', created_at TEXT DEFAULT '')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS studios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT DEFAULT '',
                name TEXT DEFAULT '', url TEXT UNIQUE, image TEXT DEFAULT '',
                video_count TEXT DEFAULT '', created_at TEXT DEFAULT '')''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS parse_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT DEFAULT '',
                action TEXT DEFAULT '', items_count INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0, duration_seconds REAL DEFAULT 0,
                created_at TEXT DEFAULT '')''')
            
            # Yangi jadval: duplicate videos tracking
            c.execute('''CREATE TABLE IF NOT EXISTS duplicate_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT, platform TEXT, reason TEXT,
                created_at TEXT DEFAULT '')''')
            
            self.conn.commit()
    
    def _create_indexes(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute('CREATE INDEX IF NOT EXISTS idx_v_platform ON videos(platform)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_v_created ON videos(created_at)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_v_views ON videos(views)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_v_category ON videos(category)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_v_rating ON videos(rating)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_categories_url ON categories(url)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_models_url ON models(url)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_studios_url ON studios(url)')
            self.conn.commit()
    
    # ============ INSERT METODLARI ============
    
    def insert_video(self, video: dict) -> bool:
        try:
            with self.lock:
                c = self.conn.cursor()
                now = datetime.now().isoformat()
                vid = video.get('id') or hashlib.md5(
                    (video.get('url','')+video.get('platform','')).encode()).hexdigest()[:16]
                
                # Duplicate tekshirish
                c.execute('SELECT id FROM videos WHERE id=? AND platform=?', (vid, video.get('platform','')))
                if c.fetchone():
                    return True  # Allaqachon mavjud
                
                c.execute('''INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    str(vid), str(video.get('platform','')), str(video.get('title','')),
                    str(video.get('url','')), str(video.get('thumbnail','')),
                    str(video.get('duration','')), str(video.get('views','')),
                    str(video.get('rating','')), str(video.get('date_added','')),
                    str(video.get('category','')),
                    json.dumps(video.get('tags',[]), ensure_ascii=False),
                    json.dumps(video.get('models',[]), ensure_ascii=False),
                    json.dumps(video.get('video_urls',[]), ensure_ascii=False),
                    1 if video.get('is_premium') else 0, now, now))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Video insert: {e}")
            return False
    
    def insert_category(self, cat: dict) -> bool:
        try:
            with self.lock:
                self.conn.execute('''INSERT OR IGNORE INTO categories 
                    (platform,title,url,video_count,image,letter,group_name,created_at)
                    VALUES (?,?,?,?,?,?,?,?)''', (
                    str(cat.get('platform','')), str(cat.get('title','')),
                    str(cat.get('url','')), str(cat.get('video_count','0')),
                    str(cat.get('image','')), str(cat.get('letter','')),
                    str(cat.get('group','')), datetime.now().isoformat()))
                self.conn.commit()
                return True
        except: return False
    
    def insert_photo(self, photo: dict) -> bool:
        try:
            with self.lock:
                pid = photo.get('id') or hashlib.md5(
                    (photo.get('url','')+photo.get('platform','')).encode()).hexdigest()[:16]
                self.conn.execute('''INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    str(pid), str(photo.get('platform','')), str(photo.get('title','')),
                    str(photo.get('url','')), str(photo.get('thumbnail','')),
                    str(photo.get('date','')), str(photo.get('views','')),
                    str(photo.get('photo_count','')), str(photo.get('rating','')),
                    str(photo.get('likes','')), str(photo.get('studio','')),
                    json.dumps(photo.get('models',[]), ensure_ascii=False),
                    datetime.now().isoformat()))
                self.conn.commit()
                return True
        except: return False
    
    def insert_model(self, model: dict) -> bool:
        try:
            with self.lock:
                self.conn.execute('''INSERT OR IGNORE INTO models 
                    (platform,name,url,image,country,video_count,rating,created_at)
                    VALUES (?,?,?,?,?,?,?,?)''', (
                    str(model.get('platform','')), str(model.get('name','')),
                    str(model.get('url','')), str(model.get('image','')),
                    str(model.get('country','')), str(model.get('video_count','')),
                    str(model.get('rating','')), datetime.now().isoformat()))
                self.conn.commit()
                return True
        except: return False
    
    def insert_studio(self, studio: dict) -> bool:
        try:
            with self.lock:
                self.conn.execute('''INSERT OR IGNORE INTO studios 
                    (platform,name,url,image,video_count,created_at) VALUES (?,?,?,?,?,?)''', (
                    str(studio.get('platform','')), str(studio.get('name','')),
                    str(studio.get('url','')), str(studio.get('image','')),
                    str(studio.get('video_count','')), datetime.now().isoformat()))
                self.conn.commit()
                return True
        except: return False
    
    def log_parse(self, platform: str, action: str, items: int, errors: int, duration: float):
        try:
            with self.lock:
                self.conn.execute('''INSERT INTO parse_logs VALUES (NULL,?,?,?,?,?,?)''',
                    (str(platform), str(action), items, errors, duration, datetime.now().isoformat()))
                self.conn.commit()
        except: pass
    
    # ============ SOROV METODLARI ============
    
    def get_stats(self) -> dict:
        try:
            with self.lock:
                c = self.conn.cursor()
                stats = {}
                for t in ['videos','categories','photos','models','studios']:
                    c.execute(f'SELECT COUNT(*) FROM {t}')
                    stats[f'total_{t}'] = c.fetchone()[0]
                c.execute('SELECT platform, COUNT(*) FROM videos GROUP BY platform')
                stats['by_platform'] = dict(c.fetchall())
                
                # Qo'shimcha statistika
                c.execute('SELECT COUNT(DISTINCT category) FROM videos WHERE category != ""')
                stats['unique_categories'] = c.fetchone()[0]
                
                c.execute('SELECT AVG(CAST(REPLACE(views," ","") AS INTEGER)) FROM videos WHERE views != ""')
                avg = c.fetchone()[0]
                stats['avg_views'] = int(avg) if avg else 0
                
                c.execute('SELECT MAX(created_at) FROM videos')
                stats['last_update'] = c.fetchone()[0] or 'Never'
                
                return stats
        except: return {}
    
    def search(self, query: str, platform: str = None, category: str = None, 
               limit: int = 50, offset: int = 0) -> List[dict]:
        try:
            with self.lock:
                c = self.conn.cursor()
                conditions = ['(title LIKE ? OR category LIKE ? OR tags LIKE ?)']
                params = [f'%{query}%', f'%{query}%', f'%{query}%']
                
                if platform:
                    conditions.append('platform=?')
                    params.append(platform)
                if category:
                    conditions.append('category=?')
                    params.append(category)
                
                sql = f'SELECT * FROM videos WHERE {" AND ".join(conditions)} ORDER BY created_at DESC LIMIT ? OFFSET ?'
                params.extend([limit, offset])
                c.execute(sql, params)
                return [dict(r) for r in c.fetchall()]
        except: return []
    
    def get_top_videos(self, limit: int = 20, platform: str = None) -> List[dict]:
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('''SELECT * FROM videos WHERE platform=? AND views!="" 
                        ORDER BY CAST(REPLACE(views," ","") AS INTEGER) DESC LIMIT ?''',
                        (platform, limit))
                else:
                    c.execute('''SELECT * FROM videos WHERE views!="" 
                        ORDER BY CAST(REPLACE(views," ","") AS INTEGER) DESC LIMIT ?''',
                        (limit,))
                return [dict(r) for r in c.fetchall()]
        except: return []
    
    def get_categories_stats(self) -> List[dict]:
        """Kategoriyalar bo'yicha statistika"""
        try:
            with self.lock:
                c = self.conn.cursor()
                c.execute('''SELECT category, COUNT(*) as count, platform 
                    FROM videos WHERE category!="" 
                    GROUP BY category, platform 
                    ORDER BY count DESC LIMIT 50''')
                return [dict(r) for r in c.fetchall()]
        except: return []
    
    def cleanup_duplicates(self) -> int:
        """Duplikat videolarni tozalash"""
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
    
    # ============ BACKUP/RESTORE ============
    
    def backup(self, backup_dir: str = 'backups') -> str:
        """Ma'lumotlar bazasini zaxiralash"""
        Path(backup_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = Path(backup_dir) / f'xxx_collector_backup_{timestamp}.db'
        
        with self.lock:
            # Yangi backup yaratish
            backup_conn = sqlite3.connect(str(backup_path))
            self.conn.backup(backup_conn)
            backup_conn.close()
        
        # Eski backuplarni tozalash (7 kundan eski)
        self._cleanup_old_backups(backup_dir, days=7)
        
        logger.info(f"Backup yaratildi: {backup_path}")
        return str(backup_path)
    
    def restore(self, backup_path: str) -> bool:
        """Ma'lumotlar bazasini tiklash"""
        try:
            with self.lock:
                backup_conn = sqlite3.connect(backup_path)
                backup_conn.backup(self.conn)
                backup_conn.close()
            logger.info(f"Backup tiklandi: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore xatosi: {e}")
            return False
    
    def _cleanup_old_backups(self, backup_dir: str, days: int = 7):
        """Eski backuplarni o'chirish"""
        cutoff = datetime.now() - timedelta(days=days)
        for f in Path(backup_dir).glob('xxx_collector_backup_*.db'):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                logger.info(f"Eski backup o'chirildi: {f}")
    
    # ============ EKSPORT METODLARI ============
    
    def export_json_fast(self, filepath: str, chunk_size: int = 1000, 
                         include_photos: bool = False) -> bool:
        try:
            with self.lock:
                stats = self.get_stats()
                categories = [dict(r) for r in self.conn.execute('SELECT * FROM categories').fetchall()]
                models_data = [dict(r) for r in self.conn.execute('SELECT * FROM models').fetchall()]
                studios_data = [dict(r) for r in self.conn.execute('SELECT * FROM studios').fetchall()]
                photos_data = [dict(r) for r in self.conn.execute('SELECT * FROM photos').fetchall()] if include_photos else []
            
            total = stats.get('total_videos', 0)
            offset = 0
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('{\n')
                f.write(f'  "export_date": "{datetime.now().isoformat()}",\n')
                f.write(f'  "database": "{self.db_path}",\n')
                f.write(f'  "statistics": {json.dumps(stats, ensure_ascii=False)},\n')
                f.write(f'  "categories": {json.dumps(categories, ensure_ascii=False)},\n')
                
                if include_photos:
                    f.write(f'  "photos": {json.dumps(photos_data, ensure_ascii=False)},\n')
                else:
                    f.write(f'  "photos": [],\n')
                
                f.write(f'  "models": {json.dumps(models_data, ensure_ascii=False)},\n')
                f.write(f'  "studios": {json.dumps(studios_data, ensure_ascii=False)},\n')
                f.write('  "videos": [\n')
                
                first = True
                while offset < total:
                    with self.lock:
                        c = self.conn.cursor()
                        c.execute('SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?',
                            (chunk_size, offset))
                        chunk = [dict(r) for r in c.fetchall()]
                    
                    if not chunk: break
                    
                    for video in chunk:
                        if not first: f.write(',\n')
                        else: first = False
                        f.write('    ')
                        json.dump(video, f, ensure_ascii=False)
                    
                    offset += len(chunk)
                    if offset % 5000 == 0:
                        logger.info(f"Eksport: {offset}/{total}")
                
                f.write('\n  ]\n}')
            
            logger.info(f"✅ Eksport: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Eksport xatosi: {e}")
            return False
    
    def export_videos_chunked(self, filepath: str, platform: str = None,
                              chunk_size: int = 1000, max_videos: int = None) -> int:
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('SELECT COUNT(*) FROM videos WHERE platform=?', (platform,))
                else:
                    c.execute('SELECT COUNT(*) FROM videos')
                total = c.fetchone()[0]
                if max_videos: total = min(total, max_videos)
            
            exported = 0; offset = 0
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('[\n'); first = True
                
                while offset < total:
                    with self.lock:
                        c = self.conn.cursor()
                        if platform:
                            c.execute('SELECT * FROM videos WHERE platform=? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                                (platform, chunk_size, offset))
                        else:
                            c.execute('SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?',
                                (chunk_size, offset))
                        chunk = [dict(r) for r in c.fetchall()]
                    
                    if not chunk: break
                    
                    for video in chunk:
                        if not first: f.write(',\n')
                        else: first = False
                        f.write('  ')
                        json.dump(video, f, ensure_ascii=False)
                    
                    offset += len(chunk); exported += len(chunk)
                    if max_videos and exported >= max_videos: break
                
                f.write('\n]')
            
            logger.info(f"✅ Video eksport: {exported} ta")
            return exported
        except Exception as e:
            logger.error(f"Eksport xatosi: {e}")
            return 0
    
    def export_csv(self, filepath: str, platform: str = None) -> int:
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform: c.execute('SELECT COUNT(*) FROM videos WHERE platform=?', (platform,))
                else: c.execute('SELECT COUNT(*) FROM videos')
                total = c.fetchone()[0]
            
            exported = 0; offset = 0; chunk_size = 500
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = None
                while offset < total:
                    with self.lock:
                        c = self.conn.cursor()
                        if platform:
                            c.execute('SELECT * FROM videos WHERE platform=? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                                (platform, chunk_size, offset))
                        else:
                            c.execute('SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?',
                                (chunk_size, offset))
                        chunk = [dict(r) for r in c.fetchall()]
                    
                    if not chunk: break
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=chunk[0].keys())
                        writer.writeheader()
                    writer.writerows(chunk)
                    offset += len(chunk); exported += len(chunk)
            
            logger.info(f"✅ CSV: {exported} ta")
            return exported
        except Exception as e:
            logger.error(f"CSV xatosi: {e}")
            return 0
    
    def export_mp4_urls(self, filepath: str, platform: str = None) -> int:
        try:
            with self.lock:
                c = self.conn.cursor()
                if platform:
                    c.execute('''SELECT DISTINCT video_urls FROM videos 
                        WHERE video_urls IS NOT NULL AND video_urls!="[]" AND platform=?''', (platform,))
                else:
                    c.execute('''SELECT DISTINCT video_urls FROM videos 
                        WHERE video_urls IS NOT NULL AND video_urls!="[]"''')
                
                urls = set()
                for row in c.fetchall():
                    try:
                        for u in (json.loads(row[0]) if row[0] else []):
                            if u and u.strip(): urls.add(u.strip())
                    except: pass
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    for u in sorted(urls): f.write(u + '\n')
                
                logger.info(f"URL eksport: {len(urls)} ta")
                return len(urls)
        except Exception as e:
            logger.error(f"URL xatosi: {e}")
            return 0


# ==================== PARSERS ====================

class BaseParser(ABC):
    def __init__(self, base_url: str, name: str, config: Config):
        self.base_url = base_url; self.name = name; self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.5'})
    
    def _get(self, url: str) -> Optional[BeautifulSoup]:
        for _ in range(self.config.max_retries):
            try:
                r = self.session.get(url, timeout=self.config.timeout)
                r.encoding = 'utf-8'
                if r.status_code == 200: return BeautifulSoup(r.text, 'html.parser')
                elif r.status_code == 404: return None
                elif r.status_code == 429: time.sleep(5)
            except Exception as e:
                logger.warning(f"[{self.name}] {url}: {e}")
                time.sleep(1)
        return None
    
    def _text(self, e) -> str: return e.get_text(strip=True) if e else ''
    
    def _attr(self, e, a: str, default: str = '') -> str:
        if e is None: return default
        v = e.get(a, default)
        return str(v) if v else default
    
    def _id(self, url: str) -> str: return url.rstrip('/').split('/')[-1] if url else ''
    
    @abstractmethod
    def videos(self, **kw) -> List[dict]: pass
    @abstractmethod
    def categories(self) -> List[dict]: pass


class LatParser(BaseParser):
    def __init__(self, c: Config): super().__init__("https://sosalkino.lat", "lat", c)
    def videos(self, **kw) -> List[dict]:
        s = self._get(self.base_url)
        if not s: return []
        res = []
        for d in s.find_all('div', class_='content'):
            for v in d.find_all('div', class_='video'):
                a = v.find_parent('a')
                if not a: continue
                url = urljoin(self.base_url, self._attr(a, 'href'))
                img = v.find('img', class_='screen')
                res.append({'id': self._id(url), 'platform': self.name, 'url': url,
                    'title': self._text(v.find('span', class_='videotitle')),
                    'thumbnail': self._attr(img, 'data-original') or self._attr(img, 'src'),
                    'duration': self._text(v.find('div', class_='videoduration')),
                    'views': self._text(v.find('span', class_='videoviews'))})
        return res
    def categories(self) -> List[dict]:
        s = self._get(f"{self.base_url}/category/")
        if not s: return []
        return [{'platform': self.name, 'url': urljoin(self.base_url, self._attr(a, 'href')),
            'title': self._text(a.find('span', class_='videotitle')),
            'video_count': self._text(a.find('span', class_='videoviews')),
            'image': self._attr(a.find('img', class_='prewpic'), 'data-original') or self._attr(a.find('img', class_='prewpic'), 'src')}
            for a in s.find_all('a', class_='catlink')]
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        res = []; base = url.rstrip('/')
        for p in range(1, pages+1):
            u = base if p == 1 else f"{base}/page{p}/"
            s = self._get(u)
            if not s: break
            cn = self._text(s.find('h1', class_='title'))
            cd = s.find('div', class_='content')
            if not cd: break
            for v in cd.find_all('div', class_='video'):
                a = v.find_parent('a')
                if not a: continue
                vu = urljoin(self.base_url, self._attr(a, 'href'))
                img = v.find('img', class_='screen')
                res.append({'id': self._id(vu), 'platform': self.name, 'url': vu,
                    'title': self._text(v.find('span', class_='videotitle')), 'category': cn,
                    'thumbnail': self._attr(img, 'data-original') or self._attr(img, 'src'),
                    'duration': self._text(v.find('div', class_='videoduration')),
                    'views': self._text(v.find('span', class_='videoviews'))})
            time.sleep(self.config.request_delay)
        return res


class BestParser(BaseParser):
    def __init__(self, c: Config): super().__init__("https://r.sosalkino.best", "best", c)
    def videos(self, page: int = 1, **kw) -> List[dict]:
        u = self.base_url if page == 1 else f"{self.base_url}/{page}/"
        s = self._get(u)
        if not s: return []
        vl = s.find('div', class_='items-list')
        if not vl: return []
        res = []
        for it in vl.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a: continue
            vu = urljoin(self.base_url, self._attr(a, 'href'))
            v = {'id': self._id(vu), 'platform': self.name, 'url': vu}
            ti = it.find('div', class_='title-item')
            if ti: v['title'] = self._text(ti.find('p', class_='title'))
            ih = it.find('div', class_='img-holder')
            if ih:
                im = ih.find('img', class_='thumb')
                v['thumbnail'] = self._attr(im, 'data-src') or self._attr(im, 'src')
                pr = ih.find('div', class_='premium-icons')
                if pr: v['is_premium'] = bool(pr.find('img', src=lambda x: x and 'diamond' in str(x)))
            info = it.find('div', class_='info-holder')
            if info:
                for d in info.find_all('div', class_='item-info'):
                    t = d.find('span', class_='text'); ic = d.find('i')
                    if t and ic:
                        cl = ' '.join(ic.get('class', [])); tx = self._text(t)
                        if 'icon-clock' in cl: v['duration'] = tx
                        elif 'icon-eye' in cl: v['views'] = tx.replace('\u2009','')
                        elif 'icon-like' in cl: v['rating'] = tx
                        elif 'icon-calendar' in cl: v['date_added'] = tx
            res.append(v)
        return res
    def videos_fast(self, pages: int = 5) -> List[dict]:
        res = []
        with ThreadPoolExecutor(max_workers=min(self.config.max_workers, pages)) as ex:
            fs = {ex.submit(self.videos, page=p): p for p in range(1, pages+1)}
            for f in as_completed(fs):
                try: res.extend(f.result())
                except Exception as e: logger.error(f"[best] p{fs[f]}: {e}")
        return res
    def categories(self) -> List[dict]:
        s = self._get(f"{self.base_url}/categories/")
        if not s: return []
        res = []
        for tab_name, gf in [('title','letter'), ('groups','group')]:
            tab = s.find('div', class_='tabs-content', attrs={'data-group-open': tab_name})
            if not tab: continue
            holders = tab.find_all('div', class_='letter-holder') if gf == 'letter' else tab.find_all('div', class_='category-group')
            for h in holders:
                gv = self._text(h.find('span', class_='letter')) if gf == 'letter' else self._text(h.find('div', class_='title-group'))
                for it in h.find_all('div', class_='item'):
                    a = it.find('a', class_='link')
                    if a:
                        cat = {'platform': self.name, 'url': urljoin(self.base_url, self._attr(a, 'href')),
                            'title': self._text(a.find('span', class_='title')),
                            'video_count': self._text(a.find('span', class_='quantity'))}
                        if gf == 'letter': cat['letter'] = gv
                        else: cat['group'] = gv
                        res.append(cat)
        return res
    def photos(self, page: int = 1) -> List[dict]:
        u = f"{self.base_url}/photos/" if page == 1 else f"{self.base_url}/photos/{page}/"
        s = self._get(u)
        if not s: return []
        res = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a: continue
            pu = urljoin(self.base_url, self._attr(a, 'href'))
            p = {'id': self._id(pu), 'platform': self.name, 'url': pu}
            mt = it.find('div', class_='models-title')
            if mt: p['title'] = self._text(mt.find('span', class_='model'))
            ih = it.find('div', class_='img-holder')
            if ih: p['thumbnail'] = self._attr(im := ih.find('img', class_='img'), 'data-src') or self._attr(im, 'src')
            info = it.find('div', class_='info')
            if info:
                for d in info.find_all('div', class_='item-info'):
                    t = d.find('span', class_='text'); ic = d.find('i')
                    if t and ic:
                        cl = ' '.join(ic.get('class', [])); tx = self._text(t)
                        if 'icon-eye' in cl: p['views'] = tx
                        elif 'icon-camera' in cl: p['photo_count'] = tx
                        elif 'icon-star' in cl: p['rating'] = tx
                        elif 'icon-like' in cl: p['likes'] = tx
            ch = it.find('div', class_='categor-holder')
            if ch:
                for rw in ch.find_all('div', class_='row'):
                    rt = rw.find('p', class_='row-title')
                    if rt:
                        if 'Студия' in rt.text: p['studio'] = self._text(rw.find('span', class_='row-item'))
                        elif 'Модели' in rt.text: p['models'] = [self._text(m) for m in rw.find_all('span', class_='row-item')]
            res.append(p)
        return res
    def models(self, url: str = None) -> List[dict]:
        if url is None: url = f"{self.base_url}/actresses/"
        s = self._get(url)
        if not s: return []
        res = []
        for it in s.find_all('div', class_='item'):
            a = it.find('a', class_='link')
            if not a: continue
            m = {'platform': self.name, 'url': urljoin(self.base_url, self._attr(a, 'href'))}
            ih = it.find('div', class_='img-holder')
            if ih:
                m['image'] = self._attr(im := ih.find('img', class_='img'), 'data-src') or self._attr(im, 'src')
                if ci := ih.find('span', class_='country_img'):
                    if fi := ci.find('img'): m['country'] = self._attr(fi, 'title')
            info = it.find('div', class_='info-holder')
            if info:
                m['name'] = self._text(info.find('p', class_='title'))
                m['video_count'] = self._text(info.find('span', class_='quantity'))
                m['rating'] = self._text(info.find('span', class_='rating'))
            res.append(m)
        return res
    def studios(self) -> List[dict]:
        s = self._get(f"{self.base_url}/studios/")
        if not s: return []
        return [{'platform': self.name, 'url': urljoin(self.base_url, self._attr(a := it.find('a', class_='link'), 'href')),
            'name': self._text(ti.find('p', class_='title')) if (ti := it.find('div', class_='title-item')) else '',
            'video_count': self._text(ti.find('span', class_='quantity')) if ti else '',
            'image': self._attr(ih.find('img', class_='img'), 'data-src') or self._attr(ih.find('img', class_='img'), 'src') if (ih := it.find('div', class_='img-holder')) else ''}
            for it in s.find_all('div', class_='item') if it.find('a', class_='link')]
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        res = []; base = url.rstrip('/')
        for p in range(1, pages+1):
            u = base + '/' if p == 1 else f"{base}/{p}/"
            s = self._get(u)
            if not s: break
            for it in s.find_all('div', class_='item'):
                a = it.find('a', class_='link')
                if not a: continue
                vu = urljoin(self.base_url, self._attr(a, 'href'))
                v = {'id': self._id(vu), 'platform': self.name, 'url': vu}
                if ti := it.find('div', class_='title-item'): v['title'] = self._text(ti.find('p', class_='title'))
                if ih := it.find('div', class_='img-holder'):
                    v['thumbnail'] = self._attr(ih.find('img', class_='thumb'), 'data-src') or self._attr(ih.find('img', class_='thumb'), 'src')
                info = it.find('div', class_='info-holder')
                if info:
                    for d in info.find_all('div', class_='item-info'):
                        t = d.find('span', class_='text'); ic = d.find('i')
                        if t and ic:
                            cl = ' '.join(ic.get('class', [])); tx = self._text(t)
                            if 'icon-clock' in cl: v['duration'] = tx
                            elif 'icon-eye' in cl: v['views'] = tx
                            elif 'icon-like' in cl: v['rating'] = tx
                res.append(v)
            time.sleep(self.config.request_delay)
        return res


class Ru5Parser(BaseParser):
    def __init__(self, c: Config): super().__init__("https://sosalkino5.ru", "5ru", c)
    def videos(self, **kw) -> List[dict]:
        s = self._get(self.base_url)
        if not s: return []
        return [{'id': self._attr(a := it.find('a', class_='link'), 'href', '').replace('/',''), 'platform': self.name,
            'url': urljoin(self.base_url, self._attr(a, 'href')),
            'title': self._text(a.find('p', class_='title')),
            'thumbnail': self._attr(a.find('img', class_='thumb'), 'src')}
            for it in s.find_all('div', class_='item') if it.find('a', class_='link')]
    def categories(self) -> List[dict]:
        s = self._get(f"{self.base_url}/category/")
        if not s: return []
        return [{'platform': self.name, 'url': urljoin(self.base_url, self._attr(a := it.find('a', class_='link'), 'href')),
            'title': self._text(a.find('p', class_='title')),
            'image': urljoin(self.base_url, self._attr(a.find('img', class_='thumb'), 'src'))}
            for it in s.find_all('div', class_='item') if it.find('a', class_='link')]
    def cat_videos(self, url: str, pages: int = 3) -> List[dict]:
        res = []; base = url.rstrip('/')
        for p in range(1, pages+1):
            u = url if p == 1 else f"{base}/{p}/"
            if u.endswith('//'): u = u[:-1]
            s = self._get(u)
            if not s: break
            for it in s.find_all('div', class_='item'):
                a = it.find('a', class_='link')
                if not a: continue
                vu = urljoin(self.base_url, self._attr(a, 'href'))
                res.append({'id': self._attr(a, 'href', '').replace('/',''), 'platform': self.name,
                    'url': vu, 'title': self._text(a.find('p', class_='title')),
                    'thumbnail': self._attr(a.find('img', class_='thumb'), 'src')})
            time.sleep(self.config.request_delay)
        return res


# ==================== COLLECTOR ====================

class Collector:
    def __init__(self, config: Config = None):
        self.cfg = config or Config()
        self.db = Database(self.cfg.db_path)
        self.parsers = {'lat': LatParser(self.cfg), 'best': BestParser(self.cfg), '5ru': Ru5Parser(self.cfg)}
        self._running = False
    
    def collect(self, platform: str, pages: int = 3):
        p = self.parsers.get(platform)
        if not p: return
        t0 = time.time(); items = 0; errs = 0
        try:
            for c in p.categories(): self.db.insert_category(c)
            vids = p.videos_fast(pages) if platform == 'best' else p.videos()
            for v in vids: self.db.insert_video(v)
            items += len(vids)
            if platform == 'best':
                for pg in range(1, 3):
                    for ph in p.photos(pg): self.db.insert_photo(ph)
                for m in p.models(): self.db.insert_model(m)
                for s in p.studios(): self.db.insert_studio(s)
        except Exception as e:
            logger.error(f"[{platform}] {e}", exc_info=True); errs += 1
        self.db.log_parse(platform, 'collect', items, errs, time.time()-t0)
        logger.info(f"[{platform}] ✅ {items} items, {time.time()-t0:.1f}s")
    
    def collect_all(self, pages: int = 3):
        for pl in self.cfg.platforms:
            self.collect(pl, pages); time.sleep(1)
        self._show_stats()
    
    def _show_stats(self):
        s = self.db.get_stats()
        print(f"""
    ╔══════════════════════════════════════════╗
    ║           STATISTIKA                    ║
    ╠══════════════════════════════════════════╣
    ║  Videolar:         {s.get('total_videos',0):>6}               ║
    ║  Kategoriyalar:    {s.get('total_categories',0):>6}               ║
    ║  Fotosuratlar:     {s.get('total_photos',0):>6}               ║
    ║  Modellar:         {s.get('total_models',0):>6}               ║
    ║  Studiyalar:       {s.get('total_studios',0):>6}               ║
    ║  Unikal kategoriya: {s.get('unique_categories',0):>6}               ║
    ║  O'rtacha ko'rish:  {s.get('avg_views',0):>6}               ║
    ║  Oxirgi yangilash:  {str(s.get('last_update','N/A'))[:16]}  ║
    ╚══════════════════════════════════════════╝""")
    
    def search(self, q: str, platform: str = None, category: str = None) -> List[dict]:
        return self.db.search(q, platform, category)
    
    def top_videos(self, limit: int = 20, platform: str = None) -> List[dict]:
        return self.db.get_top_videos(limit, platform)
    
    def categories_stats(self) -> List[dict]:
        return self.db.get_categories_stats()
    
    def backup(self) -> str:
        return self.db.backup(self.cfg.backup_dir)
    
    def restore(self, path: str) -> bool:
        return self.db.restore(path)
    
    def cleanup(self) -> int:
        return self.db.cleanup_duplicates()
    
    # ============ EKSPORT ============
    
    def export_json(self, fn: str = None, include_photos: bool = False) -> str:
        if fn is None: fn = f"export_{datetime.now():%Y%m%d_%H%M%S}.json"
        fp = Path(self.cfg.export_dir) / fn; fp.parent.mkdir(exist_ok=True)
        t0 = time.time()
        self.db.export_json_fast(str(fp), include_photos=include_photos)
        mb = fp.stat().st_size/(1024*1024) if fp.exists() else 0
        logger.info(f"JSON: {fp} ({mb:.1f}MB, {time.time()-t0:.1f}s)")
        return str(fp)
    
    def export_videos(self, platform: str = None, max_videos: int = None) -> str:
        fn = f"videos_{datetime.now():%Y%m%d_%H%M%S}.json"
        fp = Path(self.cfg.export_dir) / fn; fp.parent.mkdir(exist_ok=True)
        n = self.db.export_videos_chunked(str(fp), platform, max_videos=max_videos)
        return str(fp)
    
    def export_csv(self, platform: str = None) -> str:
        fn = f"videos_{datetime.now():%Y%m%d_%H%M%S}.csv"
        fp = Path(self.cfg.export_dir) / fn; fp.parent.mkdir(exist_ok=True)
        self.db.export_csv(str(fp), platform)
        return str(fp)
    
    def export_urls(self, platform: str = None) -> str:
        fn = f"mp4_urls_{datetime.now():%Y%m%d_%H%M%S}.txt"
        fp = Path(self.cfg.export_dir) / fn; fp.parent.mkdir(exist_ok=True)
        self.db.export_mp4_urls(str(fp), platform)
        return str(fp)


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(description='XXX Content Collector - Professional Web Parser')
    parser.add_argument('--collect', '-c', choices=['all','lat','best','5ru'], help='Platformadan malumot yigish')
    parser.add_argument('--pages', '-p', type=int, default=3, help='Sahifalar soni')
    parser.add_argument('--export', '-e', choices=['json','videos','csv','urls'], help='Eksport turi')
    parser.add_argument('--platform', '-pl', help='Platforma filtri')
    parser.add_argument('--search', '-s', help='Video qidirish')
    parser.add_argument('--top', '-t', type=int, help='Top videolarni korsatish')
    parser.add_argument('--stats', action='store_true', help='Statistika')
    parser.add_argument('--backup', action='store_true', help='Backup yaratish')
    parser.add_argument('--cleanup', action='store_true', help='Duplikatlarni tozalash')
    parser.add_argument('--verbose', '-v', action='store_true', help='Batafsil log')
    parser.add_argument('--config', default='config.json', help='Konfiguratsiya fayli')
    
    args = parser.parse_args()
    
    # Konfiguratsiya
    cfg = Config.from_file(args.config) if Path(args.config).exists() else Config()
    if args.verbose: cfg.log_level = 'DEBUG'
    
    global logger
    logger = setup_logging(args.verbose)
    
    col = Collector(cfg)
    
    # CLI buyruqlarini bajarish
    if args.backup:
        path = col.backup()
        print(f"✅ Backup: {path}")
    
    if args.cleanup:
        n = col.cleanup()
        print(f"✅ {n} ta duplikat tozalandi")
    
    if args.collect:
        if args.collect == 'all':
            col.collect_all(args.pages)
        else:
            col.collect(args.collect, args.pages)
    
    if args.stats:
        col._show_stats()
    
    if args.search:
        results = col.search(args.search, args.platform)
        for v in results[:20]:
            print(f"  [{v['platform']}] {v.get('title','')[:60]} - {v.get('views','')}")
        print(f"\n✅ {len(results)} ta natija")
    
    if args.top:
        videos = col.top_videos(args.top, args.platform)
        for i, v in enumerate(videos, 1):
            print(f"  {i}. [{v['platform']}] {v.get('title','')[:60]} - {v.get('views','')}")
    
    if args.export:
        if args.export == 'json':
            fp = col.export_json()
        elif args.export == 'videos':
            fp = col.export_videos(args.platform)
        elif args.export == 'csv':
            fp = col.export_csv(args.platform)
        elif args.export == 'urls':
            fp = col.export_urls(args.platform)
        print(f"✅ Eksport: {fp}")
    
    # Hech qanday argument bo'lmasa interaktiv menyu
    if not any([args.collect, args.export, args.search, args.top, args.stats, args.backup, args.cleanup]):
        interactive_menu(col)


def interactive_menu(col: Collector):
    """Interaktiv menyu"""
    print("""
    ╔══════════════════════════════════════════════╗
    ║   XXX CONTENT COLLECTOR - Ultimate Pro v7.0 ║
    ║  3 platforma • SQLite • Backup • CLI        ║
    ╚══════════════════════════════════════════════╝
    """)
    
    while True:
        print("""
========================================
 1. Barcha platformalardan yig'ish
 2. Faqat LAT   3. Faqat BEST   4. Faqat 5RU
 5. Kategoriyadan videolar
 6. Qidirish    7. Top videolar
 8. JSON eksport (barchasi)
 9. Faqat videolar eksporti
10. CSV eksport
11. MP4 URL eksport
12. Statistika
13. Backup yaratish
14. Duplikatlarni tozalash
 0. Chiqish
========================================
        """)
        
        ch = input("Tanlang: ").strip()
        
        if ch == '1':
            pages = int(input("Sahifalar (1-10): ") or '3')
            col.collect_all(pages)
        elif ch == '2': col.collect('lat', 3)
        elif ch == '3': col.collect('best', 3)
        elif ch == '4': col.collect('5ru', 3)
        elif ch == '5':
            pl = input("Platforma (lat/best/5ru): ").strip()
            url = input("URL: ").strip()
            if p := col.parsers.get(pl):
                vids = p.cat_videos(url, 3)
                for v in vids: col.db.insert_video(v)
                print(f"✅ {len(vids)} ta")
        elif ch == '6':
            q = input("Qidiruv: ").strip()
            pl = input("Platforma: ").strip() or None
            cat = input("Kategoriya: ").strip() or None
            for v in col.search(q, pl, cat)[:20]:
                print(f"  [{v['platform']}] {v.get('title','')[:60]}")
        elif ch == '7':
            n = int(input("Nechta: ") or '20')
            pl = input("Platforma: ").strip() or None
            for i, v in enumerate(col.top_videos(n, pl), 1):
                print(f"  {i}. [{v['platform']}] {v.get('title','')[:50]} - {v.get('views','')}")
        elif ch == '8':
            fp = col.export_json(include_photos=True)
            print(f"✅ {fp}")
        elif ch == '9':
            pl = input("Platforma: ").strip() or None
            mx = input("Max: ").strip()
            fp = col.export_videos(pl, int(mx) if mx else None)
            print(f"✅ {fp}")
        elif ch == '10':
            pl = input("Platforma: ").strip() or None
            fp = col.export_csv(pl)
            print(f"✅ {fp}")
        elif ch == '11':
            pl = input("Platforma: ").strip() or None
            fp = col.export_urls(pl)
            print(f"✅ {fp}")
        elif ch == '12': col._show_stats()
        elif ch == '13':
            fp = col.backup()
            print(f"✅ Backup: {fp}")
        elif ch == '14':
            n = col.cleanup()
            print(f"✅ {n} ta duplikat tozalandi")
        elif ch == '0': break


if __name__ == "__main__":
    main()