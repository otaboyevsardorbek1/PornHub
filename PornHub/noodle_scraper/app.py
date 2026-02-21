#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Noodlemagazine Scraper
Bitta faylda to'liq funksional: popular va search, parametrlar bilan, Redis kesh, antibot.
Qo'shimcha: video sahifasidan to'g'ridan-to'g'ri .mp4 yoki m3u8 URL olish.
Ishlatish:
    python app.py --mode popular --period month --max 50
    python app.py --mode search --query japanes --sort-by views --hd 1 --max 100 --get-direct-url
"""

import asyncio
import argparse
import csv
import json
import logging
import hashlib
import random
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from urllib.parse import urljoin, urlencode

import aiohttp
from lxml import html
from fake_useragent import UserAgent

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# -------------------- Konfiguratsiya --------------------
class Config:
    # Umumiy sozlamalar
    DEBUG_MODE = True
    REQUEST_TIMEOUT = 30
    MAX_CONCURRENT = 5
    REQUEST_DELAY = 1.5

    # Redis keshi
    ENABLE_REDIS = True and REDIS_AVAILABLE
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
    REDIS_DB = 0
    CACHE_TTL = 3600

    # Antibot
    ENABLE_ANTIBOT = True
    ROTATE_USER_AGENT = True
    USE_PROXY = False
    PROXY_LIST = []

    # Noodlemagazine
    BASE_URL = "https://noodlemagazine.com"
    POPULAR_URLS = {
        'month': f"{BASE_URL}/popular/month?sort_by=views&sort_order=desc",
        'week': f"{BASE_URL}/popular/week?sort_by=views&sort_order=desc&p=0",
        'day': f"{BASE_URL}/popular/day?sort_by=views&sort_order=desc&p=0",
        'recent': f"{BASE_URL}/popular/recent?sort_by=views&sort_order=desc&p=0"
    }

    # Qidiruv URL shabloni
    SEARCH_URL_TEMPLATE = f"{BASE_URL}/video/{{query}}"

    # Standart qidiruv parametrlari
    DEFAULT_SEARCH_PARAMS = {
        'sort_by': 'relevance',
        'sort_order': 'desc',
        'len': 'any',
        'sort': '2',
        'hd': '0'
    }

    # CSS selektorlar (sayt tuzilishiga moslab sozlang)
    SELECTORS = {
        'video_container': 'div.thumb, div.item, div.video-item',
        'title': 'a[title], .title a',
        'views': '.views, .views-count',
        'duration': '.duration, .time',
        'link': 'a',
        'thumbnail': 'img',
    }

    # Ma'lumotlarni saqlash
    SAVE_TO_CSV = True
    SAVE_TO_JSON = False
    CSV_FILENAME = "videos.csv"
    JSON_FILENAME = "videos.json"

    # Logging
    LOG_LEVEL = "INFO"


# -------------------- Antibot --------------------
class AntiBot:
    def __init__(self):
        self.ua = UserAgent() if Config.ROTATE_USER_AGENT else None
        self.proxies = Config.PROXY_LIST if Config.USE_PROXY else []

    async def get_headers(self, referer=None):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        if self.ua:
            headers['User-Agent'] = self.ua.random
        if referer:
            headers['Referer'] = referer
        return headers

    async def get_proxy(self):
        if self.proxies:
            return random.choice(self.proxies)
        return None

    async def smart_delay(self):
        delay = random.uniform(Config.REQUEST_DELAY, Config.REQUEST_DELAY * 1.5)
        if Config.DEBUG_MODE:
            print(f"Kechikish: {delay:.2f} sekund")
        await asyncio.sleep(delay)


# -------------------- Redis keshi --------------------
class RedisCache:
    def __init__(self):
        self.client = None
        if Config.ENABLE_REDIS:
            try:
                self.client = redis.Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    db=Config.REDIS_DB,
                    decode_responses=True
                )
                logger.info("Redis ga ulanish muvaffaqiyatli")
            except Exception as e:
                logger.error(f"Redis ga ulanishda xatolik: {e}")
                self.client = None

    async def get_cache(self, url):
        if not self.client:
            return None
        key = hashlib.md5(url.encode()).hexdigest()
        data = await self.client.get(key)
        if data:
            logger.debug(f"Kesh topildi: {url}")
            return json.loads(data)
        return None

    async def set_cache(self, url, data, ttl=Config.CACHE_TTL):
        if not self.client:
            return
        key = hashlib.md5(url.encode()).hexdigest()
        await self.client.setex(key, ttl, json.dumps(data, default=str))
        logger.debug(f"Keshga saqlandi: {url}")

    async def clear_cache(self, url=None):
        if not self.client:
            return
        if url:
            key = hashlib.md5(url.encode()).hexdigest()
            await self.client.delete(key)
            logger.info(f"Kesh o'chirildi: {url}")
        else:
            await self.client.flushdb()
            logger.info("Barcha kesh tozalandi")

    async def get_stats(self):
        if not self.client:
            return None
        info = await self.client.info()
        return {
            'keys': await self.client.dbsize(),
            'memory_usage': info.get('used_memory_human', 'N/A'),
            'hits': info.get('keyspace_hits', 0),
            'misses': info.get('keyspace_misses', 0)
        }

    async def close(self):
        if self.client:
            await self.client.close()
            logger.info("Redis ulanishi yopildi")


# -------------------- Video model --------------------
@dataclass
class Video:
    title: str
    url: str          # video sahifasining URL manzili (masalan, /watch/...)
    views: str
    duration: str
    thumbnail: Optional[str] = None
    source_page: Optional[str] = None
    direct_url: Optional[str] = None   # to'g'ridan-to'g'ri video fayl URL (.mp4 yoki .m3u8)

    def to_dict(self):
        return asdict(self)


# -------------------- Asosiy Scraper --------------------
class NoodleScraper:
    def __init__(self):
        self.antiban = AntiBot() if Config.ENABLE_ANTIBOT else None
        self.cache = RedisCache() if Config.ENABLE_REDIS else None
        self.session = None
        self.base_url = Config.BASE_URL
        self.selectors = Config.SELECTORS

    async def __aenter__(self):
        await self.create_session()
        # Cookie olish uchun bosh sahifaga so'rov (ixtiyoriy)
        await self.fetch_html(self.base_url + "/new-video")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def create_session(self):
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=Config.MAX_CONCURRENT)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        logger.debug("HTTP seans yaratildi")

    async def close(self):
        if self.session:
            await self.session.close()
            logger.debug("HTTP seans yopildi")
        if self.cache:
            await self.cache.close()

    async def fetch_html(self, url: str, referer: str = None) -> Optional[str]:
        """URL dan HTML kontentni olish (kesh bilan)"""
        if self.cache:
            cached = await self.cache.get_cache(url)
            if cached:
                logger.info(f"Keshdan olindi: {url}")
                return cached.get('html')

        headers = {}
        proxy = None
        if self.antiban:
            headers = await self.antiban.get_headers(referer=referer)
            proxy = await self.antiban.get_proxy() if Config.USE_PROXY else None

        try:
            async with self.session.get(url, headers=headers, proxy=proxy) as response:
                if response.status != 200:
                    logger.error(f"Xato {response.status}: {url}")
                    return None

                html_text = await response.text()

                if self.cache:
                    await self.cache.set_cache(url, {'html': html_text})

                if self.antiban:
                    await self.antiban.smart_delay()
                return html_text

        except Exception as e:
            logger.error(f"So'rovda xatolik {url}: {e}")
            return None

    def parse_videos(self, html_text: str, source_url: str) -> List[Video]:
        """Ro'yxat sahifasidan video ma'lumotlarini ajratib olish"""
        tree = html.fromstring(html_text)
        videos = []
        containers = tree.cssselect(self.selectors['video_container'])
        logger.debug(f"Topilgan konteynerlar soni: {len(containers)}")

        for container in containers:
            try:
                title_elem = container.cssselect(self.selectors['title'])
                title = title_elem[0].text_content().strip() if title_elem else "Noma'lum"

                views_elem = container.cssselect(self.selectors['views'])
                views = views_elem[0].text_content().strip() if views_elem else "0"

                duration_elem = container.cssselect(self.selectors['duration'])
                duration = duration_elem[0].text_content().strip() if duration_elem else "00:00"

                link_elem = container.cssselect(self.selectors['link'])
                if link_elem:
                    link = urljoin(self.base_url, link_elem[0].get('href', ''))
                else:
                    link = ""

                thumb_elem = container.cssselect(self.selectors['thumbnail'])
                thumbnail = urljoin(self.base_url, thumb_elem[0].get('src', '')) if thumb_elem else None

                video = Video(
                    title=title,
                    url=link,
                    views=views,
                    duration=duration,
                    thumbnail=thumbnail,
                    source_page=source_url
                )
                videos.append(video)

            except Exception as e:
                logger.error(f"Videoni parse qilishda xatolik: {e}")
                continue

        logger.info(f"{len(videos)} ta video topildi: {source_url}")
        return videos

    async def get_video_direct_url(self, video_page_url: str) -> Optional[str]:
        """
        Video sahifasidan to'g'ridan-to'g'ri video fayl URL manzilini olish.
        Bir necha usul bilan qidiradi: video tegi, source, yoki m3u8.
        Qaytaradi: .mp4 yoki .m3u8 manzili yoki None.
        """
        logger.info(f"Video sahifasidan direct URL olinmoqda: {video_page_url}")
        html_text = await self.fetch_html(video_page_url, referer=self.base_url + "/new-video")
        if not html_text:
            return None

        tree = html.fromstring(html_text)

        # 1-usul: <video> tegining src atributi
        video_src = tree.xpath('//video/@src')
        if video_src:
            src = video_src[0].strip()
            if src:
                full_url = urljoin(self.base_url, src)
                logger.debug(f"Video src topildi: {full_url}")
                return full_url

        # 2-usul: <video> ichidagi <source> teglari
        source_src = tree.xpath('//video/source/@src')
        if source_src:
            src = source_src[0].strip()
            if src:
                full_url = urljoin(self.base_url, src)
                logger.debug(f"Video source src topildi: {full_url}")
                return full_url

        # 3-usul: iframe yoki boshqa elementlar? (murakkab)
        # 4-usul: sahifadagi JavaScript o'zgaruvchilarini qidirish? (murakkab, hozircha o'tkazib yuboramiz)

        # 5-usul: m3u8 playlist manzili (ba'zi saytlar video o'rniga m3u8 ishlatadi)
        # Bu odatda video tegi orqali bo'ladi, lekin ba'zida alohida link bo'ladi
        m3u8_links = tree.xpath('//a[contains(@href, ".m3u8")]/@href')
        if m3u8_links:
            src = m3u8_links[0].strip()
            full_url = urljoin(self.base_url, src)
            logger.debug(f"m3u8 link topildi: {full_url}")
            return full_url

        # Hech narsa topilmadi
        logger.warning(f"Direct URL topilmadi: {video_page_url}")
        return None

    async def get_popular(self, period: str = 'month', max_videos: int = 50) -> List[Video]:
        if period not in Config.POPULAR_URLS:
            logger.error(f"Noto'g'ri period: {period}. Tanlov: {list(Config.POPULAR_URLS.keys())}")
            return []

        url = Config.POPULAR_URLS[period]
        html_text = await self.fetch_html(url)
        if not html_text:
            return []

        videos = self.parse_videos(html_text, url)
        return videos[:max_videos]

    async def search(self, query: str, params: dict = None, max_videos: int = 50) -> List[Video]:
        """
        Qidiruv so'rovi bo'yicha videolarni olish.
        params: dict kalitlari: sort_by, sort_order, len, sort, hd
        """
        search_params = Config.DEFAULT_SEARCH_PARAMS.copy()
        if params:
            allowed_keys = {'sort_by', 'sort_order', 'len', 'sort', 'hd'}
            for k, v in params.items():
                if k in allowed_keys and v is not None:
                    search_params[k] = v

        query_encoded = query.replace(' ', '+')
        base_url = Config.SEARCH_URL_TEMPLATE.format(query=query_encoded)
        query_string = urlencode(search_params)
        search_url = f"{base_url}?{query_string}"

        logger.info(f"Qidiruv URL: {search_url}")
        html_text = await self.fetch_html(search_url, referer=self.base_url + "/new-video")
        if not html_text:
            return []

        videos = self.parse_videos(html_text, search_url)
        return videos[:max_videos]

    # Yordamchi metodlar
    async def search_sorted_by_views(self, query: str, hd_only: bool = False, max_videos: int = 50) -> List[Video]:
        params = {'sort_by': 'views', 'sort_order': 'desc', 'hd': '1' if hd_only else '0'}
        return await self.search(query, params, max_videos)

    async def search_recent(self, query: str, max_videos: int = 50) -> List[Video]:
        params = {'sort': '0', 'sort_order': 'desc'}
        return await self.search(query, params, max_videos)

    async def get_multiple_popular(self, periods: List[str] = None, max_videos_per_period: int = 30) -> List[Video]:
        if periods is None:
            periods = ['day', 'week', 'month']

        all_videos = []
        semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT)

        async def fetch_period(period):
            async with semaphore:
                return await self.get_popular(period, max_videos_per_period)

        tasks = [fetch_period(p) for p in periods]
        results = await asyncio.gather(*tasks)

        for videos in results:
            all_videos.extend(videos)
        return all_videos


# -------------------- Yordamchi funksiyalar (saqlash, logging) --------------------
def setup_logging():
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def save_to_csv(videos: List[Video], filename: str):
    if not videos:
        logger.warning("Saqlash uchun video ma'lumotlari yo'q")
        return
    fieldnames = ['title', 'views', 'duration', 'url', 'thumbnail', 'source_page', 'direct_url']
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in videos:
            writer.writerow(v.to_dict())
    logger.info(f"{len(videos)} ta video {filename} fayliga saqlandi")

def save_to_json(videos: List[Video], filename: str):
    if not videos:
        logger.warning("Saqlash uchun video ma'lumotlari yo'q")
        return
    data = [v.to_dict() for v in videos]
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"{len(videos)} ta video {filename} fayliga saqlandi")


# -------------------- Asosiy ishga tushirish --------------------
async def main():
    parser = argparse.ArgumentParser(description="Noodlemagazine skraper")
    parser.add_argument('--mode', choices=['popular', 'search'], default='popular',
                        help="Ish rejimi: popular yoki search")
    parser.add_argument('--period', choices=['day', 'week', 'month', 'recent'], default='month',
                        help="Popular videolar davri (faqat popular rejimida)")
    parser.add_argument('--query', type=str, help="Qidiruv so'rovi (search rejimida)")
    parser.add_argument('--max', type=int, default=50, help="Olinadigan videolar soni")

    # Qidiruv parametrlari
    parser.add_argument('--sort-by', choices=['views', 'date_added', 'duration', 'relevance'],
                        default='relevance', help="Saralash mezoni")
    parser.add_argument('--sort-order', choices=['desc', 'asc'], default='desc',
                        help="Saralash tartibi")
    parser.add_argument('--len', choices=['any', 'long', 'short'], default='any',
                        help="Video davomiyligi")
    parser.add_argument('--sort-type', choices=['0', '1', '2'], default='2',
                        help="Saralash turi (0=sana, 1=davomiylik, 2=moslik)")
    parser.add_argument('--hd', choices=['0', '1'], default='0',
                        help="HD filtri (0=barcha, 1=faqat HD)")

    parser.add_argument('--output', type=str, default=Config.CSV_FILENAME,
                        help="Chiqish fayli nomi (CSV uchun)")
    parser.add_argument('--json', action='store_true', help="JSON formatida saqlash")
    parser.add_argument('--no-csv', action='store_true', help="CSV saqlamaslik")

    # Yangi flag: to'g'ridan-to'g'ri URL olish
    parser.add_argument('--get-direct-url', action='store_true',
                        help="Har bir video sahifasidan to'g'ridan-to'g'ri video fayl URL manzilini olish (ko'proq vaqt oladi)")

    args = parser.parse_args()

    # Sozlamalarni yangilash
    if args.json:
        Config.SAVE_TO_JSON = True
        Config.SAVE_TO_CSV = not args.no_csv
    elif args.no_csv:
        Config.SAVE_TO_CSV = False

    async with NoodleScraper() as scraper:
        videos = []

        if args.mode == 'popular':
            logger.info(f"Mashhur videolar yig'ilmoqda: {args.period}")
            videos = await scraper.get_popular(period=args.period, max_videos=args.max)

        elif args.mode == 'search':
            if not args.query:
                logger.error("Qidiruv rejimida --query parametri talab qilinadi")
                return

            search_params = {
                'sort_by': args.sort_by,
                'sort_order': args.sort_order,
                'len': args.len,
                'sort': args.sort_type,
                'hd': args.hd
            }
            logger.info(f"Qidiruv: '{args.query}' parametrlar: {search_params}")
            videos = await scraper.search(query=args.query, params=search_params, max_videos=args.max)

        logger.info(f"Jami {len(videos)} ta video olindi")

        # Agar direct URL olish kerak bo'lsa
        if args.get_direct_url and videos:
            logger.info("Har bir video uchun to'g'ridan-to'g'ri URL olinmoqda...")
            for idx, video in enumerate(videos, 1):
                if video.url:
                    direct_url = await scraper.get_video_direct_url(video.url)
                    video.direct_url = direct_url
                    logger.info(f"[{idx}/{len(videos)}] {video.title[:50]}... -> {direct_url if direct_url else 'topilmadi'}")
                    # Kechikish (antibot)
                    if scraper.antiban:
                        await scraper.antiban.smart_delay()
                else:
                    logger.warning(f"Video URL mavjud emas, o'tkazib yuborildi")

        # Saqlash
        if Config.SAVE_TO_CSV:
            save_to_csv(videos, args.output)

        if Config.SAVE_TO_JSON:
            json_file = args.output.replace('.csv', '.json') if args.output.endswith('.csv') else 'videos.json'
            save_to_json(videos, json_file)

        if scraper.cache:
            stats = await scraper.cache.get_stats()
            if stats:
                logger.info(f"Kesh statistikasi: {stats}")


if __name__ == "__main__":
    asyncio.run(main())