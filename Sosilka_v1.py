import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin, urlparse
import re

class Sosalkino5Parser:
    def __init__(self):
        self.base_url = "https://sosalkino5.ru"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.categories = []
        self.videos = []
        self.video_details = []
        
    def get_page(self, url):
        """Sahifani yuklash"""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            else:
                print(f"❌ HTTP xatolik: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ So'rov xatolik: {e}")
            return None
    
    def parse_categories(self):
        """Barcha kategoriyalarni olish"""
        print("\n" + "="*60)
        print("📋 KATEGORIYALAR YUKLANMOQDA...")
        print("="*60)
        
        url = f"{self.base_url}/category/"
        html = self.get_page(url)
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Kategoriya elementlarini topish
        items = soup.find_all('div', class_='item')
        
        for item in items:
            link = item.find('a', class_='link')
            if link:
                img = link.find('img', class_='thumb')
                title_elem = link.find('p', class_='title')
                
                category = {
                    'title': title_elem.text.strip() if title_elem else '',
                    'url': urljoin(self.base_url, link.get('href')),
                    'image': urljoin(self.base_url, img.get('src')) if img else '',
                    'slug': link.get('href', '').replace('/', '')
                }
                self.categories.append(category)
        
        print(f"✅ {len(self.categories)} ta kategoriya topildi")
        return self.categories
    
    def parse_videos_from_category(self, category_url, category_name, max_pages=5):
        """Kategoriyadan videolarni olish"""
        print(f"\n📁 {category_name} kategoriyasi")
        print("-" * 40)
        
        videos = []
        current_page = 1
        
        # Birinchi sahifa
        html = self.get_page(category_url)
        if not html:
            return videos
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Sahifalar sonini aniqlash
        pagination = soup.find('div', class_='pagination')
        total_pages = 1
        if pagination:
            page_links = pagination.find_all('a')
            if page_links:
                page_numbers = []
                for link in page_links:
                    try:
                        page_numbers.append(int(link.text.strip()))
                    except:
                        pass
                if page_numbers:
                    total_pages = min(max(page_numbers), max_pages)
        
        print(f"  📊 Jami sahifalar: {total_pages}")
        
        while current_page <= total_pages:
            print(f"  📄 Sahifa {current_page}/{total_pages} olinmoqda...")
            
            # Videolarni olish
            items = soup.find_all('div', class_='item')
            
            for item in items:
                link = item.find('a', class_='link')
                if link and link.get('href'):
                    img = link.find('img', class_='thumb')
                    title_elem = link.find('p', class_='title')
                    
                    # Qo'shimcha ma'lumotlar
                    info_holder = item.find('div', class_='info-holder')
                    views = ''
                    rating = ''
                    date = ''
                    
                    if info_holder:
                        infos = info_holder.find_all('div', class_='item-info')
                        for info in infos:
                            text_elem = info.find('span', class_='text')
                            if text_elem:
                                text = text_elem.text.strip()
                                if 'icon-eye' in str(info):
                                    views = text
                                elif 'icon-like' in str(info):
                                    rating = text
                                elif 'icon-calendar' in str(info):
                                    date = text
                    
                    video = {
                        'title': title_elem.text.strip() if title_elem else '',
                        'url': urljoin(self.base_url, link.get('href')),
                        'thumbnail': img.get('src') if img else '',
                        'views': views,
                        'rating': rating,
                        'date_added': date,
                        'category': category_name
                    }
                    videos.append(video)
            
            if current_page >= total_pages:
                break
            
            # Keyingi sahifaga o'tish
            current_page += 1
            next_url = f"{category_url}{current_page}/" if category_url.endswith('/') else f"{category_url}/{current_page}/"
            html = self.get_page(next_url)
            if not html:
                break
            soup = BeautifulSoup(html, 'html.parser')
            time.sleep(1)
        
        print(f"  ✅ {len(videos)} ta video topildi")
        return videos
    
    def parse_video_details(self, video_url):
        """Alohida video sahifasidan to'liq ma'lumot olish"""
        print(f"  🎬 Video tafsilotlari olinmoqda: {video_url}")
        
        html = self.get_page(video_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        details = {
            'url': video_url,
            'title': '',
            'description': '',
            'views': '',
            'rating': '',
            'date_added': '',
            'tags': [],
            'models': [],
            'category': '',
            'video_url': '',
            'thumbnail': ''
        }
        
        # Sarlavha
        title_elem = soup.find('h1')
        if title_elem:
            details['title'] = title_elem.text.strip()
        
        # Video URL (iframe)
        iframe = soup.find('iframe', id='player')
        if iframe:
            details['video_url'] = iframe.get('src', '')
        
        # Tavsif
        desc_elem = soup.find('p', class_='description')
        if desc_elem:
            desc_text = desc_elem.text.strip()
            # Teglar va modellarni ajratib olish
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
        
        # Ko'rishlar soni
        view_elem = soup.find('p', class_='view-video')
        if view_elem:
            bold = view_elem.find('span', class_='bold')
            if bold:
                details['views'] = bold.text.strip()
        
        # Kategoriya
        cat_elem = soup.find('div', class_='categor-holder')
        if cat_elem:
            cat_link = cat_elem.find('a')
            if cat_link:
                details['category'] = cat_link.text.strip()
        
        return details
    
    def save_data(self, data, filename, format='json'):
        """Ma'lumotlarni saqlash"""
        if format == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == 'csv':
            import csv
            if data and len(data) > 0:
                # CSV uchun maydonlarni tekislash
                flat_data = []
                for item in data:
                    flat_item = {}
                    for key, value in item.items():
                        if isinstance(value, list):
                            flat_item[key] = ', '.join(value)
                        else:
                            flat_item[key] = value
                    flat_data.append(flat_item)
                
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=flat_data[0].keys())
                    writer.writeheader()
                    writer.writerows(flat_data)
        
        print(f"💾 Saqlandi: {filename}")
    
    def print_category_list(self):
        """Kategoriyalar ro'yxatini chiqarish"""
        print("\n" + "="*60)
        print("📋 KATEGORIYALAR RO'YXATI:")
        print("="*60)
        for i, cat in enumerate(self.categories, 1):
            print(f"  {i:3d}. {cat['title']}")
    
    def run_interactive(self):
        """Interaktiv rejimda ishga tushirish"""
        print("\n" + "="*60)
        print("🚀 SOSALKINO5.RU PARSER")
        print("="*60)
        
        # 1. Kategoriyalarni olish
        self.parse_categories()
        self.print_category_list()
        
        if not self.categories:
            print("❌ Kategoriyalar topilmadi!")
            return
        
        # 2. Foydalanuvchidan kategoriya tanlash
        print("\n" + "="*60)
        print("🎯 KATEGORIYA TANLANG:")
        print("  0 - BARCHA KATEGORIYALAR")
        for i, cat in enumerate(self.categories, 1):
            print(f"  {i} - {cat['title']}")
        
        try:
            choice = input("\nTanlang (0-{}): ".format(len(self.categories)))
            
            if choice == "0":
                selected_categories = self.categories
                max_pages = int(input("Har bir kategoriyadan nechta sahifa olinsin? (1-10): ") or "2")
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(self.categories):
                    selected_categories = [self.categories[idx]]
                    max_pages = int(input(f"Nechta sahifa olinsin? (1-10): ") or "5")
                else:
                    print("❌ Noto'g'ri tanlov!")
                    return
        except ValueError:
            print("❌ Noto'g'ri kiritish!")
            return
        
        # 3. Videolarni yig'ish
        all_videos = []
        
        for cat in selected_categories:
            print(f"\n📁 {cat['title']} yuklanmoqda...")
            videos = self.parse_videos_from_category(cat['url'], cat['title'], max_pages)
            
            for video in videos:
                video['category_title'] = cat['title']
                video['category_url'] = cat['url']
            
            all_videos.extend(videos)
            time.sleep(1)
        
        if all_videos:
            # Videolarni saqlash
            self.save_data(all_videos, 'videos_list.json', 'json')
            
            print(f"\n📊 JAMI: {len(all_videos)} ta video topildi")
            
            # 4. Video tafsilotlarini olish (ixtiyoriy)
            get_details = input("\nHar bir videoning to'liq tafsilotlarini olishni xohlaysizmi? (ha/yo'q): ").lower()
            
            if get_details == 'ha':
                limit = int(input(f"Nechta video tafsiloti olinsin? (1-{len(all_videos)}): ") or "5")
                limit = min(limit, len(all_videos))
                
                print(f"\n🎬 {limit} ta VIDEO TAFSILOTLARI OLINMOQDA...")
                detailed_videos = []
                
                for i, video in enumerate(all_videos[:limit], 1):
                    print(f"\n  {i}/{limit}: {video['title'][:60]}...")
                    details = self.parse_video_details(video['url'])
                    if details:
                        detailed_videos.append(details)
                    time.sleep(1)
                
                if detailed_videos:
                    self.save_data(detailed_videos, 'video_details.json', 'json')
                    print(f"\n✅ {len(detailed_videos)} ta video tafsiloti saqlandi")
        else:
            print("❌ Videolar topilmadi!")
        
        print("\n" + "="*60)
        print("✅ PARSER ISHI TUGADI!")
        print("="*60)


# Dasturni ishga tushirish
if __name__ == "__main__":
    parser = Sosalkino5Parser()
    
    # Avtomatik rejim (barcha kategoriyalarni olish)
    auto_mode = input("Avtomatik rejimda barcha kategoriyalarni olmoqchimisiz? (ha/yo'q): ").lower()
    
    if auto_mode == 'ha':
        print("\n🚀 AVTOMATIK REJIM ISHGA TUSHIRILDI")
        parser.parse_categories()
        
        all_videos = []
        for cat in parser.categories:
            print(f"\n📁 {cat['title']}...")
            videos = parser.parse_videos_from_category(cat['url'], cat['title'], max_pages=2)
            for video in videos:
                video['category_title'] = cat['title']
            all_videos.extend(videos)
            time.sleep(1)
        
        if all_videos:
            parser.save_data(all_videos, 'all_videos.json', 'json')
            print(f"\n📊 JAMI: {len(all_videos)} ta video saqlandi")
    else:
        parser.run_interactive()