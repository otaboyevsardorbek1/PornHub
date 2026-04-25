import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin
import csv
from datetime import datetime

class SosalkinoFullParser:
    def __init__(self):
        self.base_url = "https://sosalkino.lat"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        })
        
    def get_main_page_videos(self):
        """Asosiy sahifadagi barcha videolarni yig'ish"""
        print("="*60)
        print("🏠 ASOSIY SAHIFA VIDEOLARI YUKLANMOQDA...")
        print("="*60)
        
        main_page_data = {
            'new_videos': [],      # Новое порно
            'best_videos': [],     # Лучшее порно
            'top_videos': [],      # Популярное порно
            'categories': []       # Категории
        }
        
        try:
            response = self.session.get(self.base_url, timeout=15)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Video bloklarini topish
            content_divs = soup.find_all('div', class_='content')
            
            video_block_index = 0
            for content_div in content_divs:
                # Har bir blokdagi videolarni olish
                video_cards = content_div.find_all('div', class_='video')
                
                if video_cards:
                    videos = []
                    for card in video_cards:
                        link = card.find_parent('a')
                        if link:
                            video = self._parse_video_card(card, link)
                            videos.append(video)
                    
                    # Qaysi blok ekanligini aniqlash
                    if video_block_index == 0:
                        main_page_data['new_videos'] = videos
                        print(f"📰 Yangi videolar: {len(videos)} ta")
                    elif video_block_index == 1:
                        main_page_data['best_videos'] = videos
                        print(f"⭐ Eng yaxshi videolar: {len(videos)} ta")
                    elif video_block_index == 2:
                        main_page_data['top_videos'] = videos
                        print(f"🔥 Ommabop videolar: {len(videos)} ta")
                    
                    video_block_index += 1
            
            # Kategoriyalarni olish
            categories = self._parse_categories(soup)
            main_page_data['categories'] = categories
            print(f"📂 Kategoriyalar: {len(categories)} ta")
            
            return main_page_data
            
        except Exception as e:
            print(f"❌ Asosiy sahifani yuklashda xatolik: {e}")
            return None
    
    def _parse_video_card(self, card, link):
        """Bitta video kartochkasidan ma'lumot olish"""
        video = {
            'title': '',
            'url': '',
            'thumbnail': '',
            'views': '',
            'duration': '',
            'video_id': ''
        }
        
        # Sarlavha
        title_span = card.find('span', class_='videotitle')
        if title_span:
            video['title'] = title_span.text.strip()
        
        # URL
        video['url'] = urljoin(self.base_url, link.get('href'))
        
        # Rasm
        img_tag = card.find('img', class_='screen')
        if img_tag:
            video['thumbnail'] = img_tag.get('data-original') or img_tag.get('src')
            video['title'] = video['title'] or img_tag.get('alt', '')
        
        # Ko'rishlar soni
        views_span = card.find('span', class_='videoviews')
        if views_span:
            video['views'] = views_span.text.strip()
        
        # Davomiylik
        duration_div = card.find('div', class_='videoduration')
        if duration_div:
            video['duration'] = duration_div.text.strip()
        
        # Video ID (URL dan)
        if '/video/' in video['url']:
            video['video_id'] = video['url'].split('/video/')[-1].rstrip('/')
        
        return video
    
    def _parse_categories(self, soup):
        """Kategoriyalarni HTML dan olish"""
        categories = []
        cat_links = soup.find_all('a', class_='catlink')
        
        for link in cat_links:
            category = {
                'title': '',
                'url': '',
                'image': '',
                'video_count': '0'
            }
            
            # Kategoriya sarlavhasi
            title_span = link.find('span', class_='videotitle')
            if title_span:
                category['title'] = title_span.text.strip()
            
            # URL
            category['url'] = urljoin(self.base_url, link.get('href'))
            
            # Rasm
            img_tag = link.find('img', class_='prewpic')
            if img_tag:
                category['image'] = img_tag.get('data-original') or img_tag.get('src')
            
            # Video soni
            views_span = link.find('span', class_='videoviews')
            if views_span:
                category['video_count'] = views_span.text.strip()
            
            categories.append(category)
        
        return categories
    
    def get_category_page(self, category_url, max_pages=5):
        """Kategoriya sahifasidagi barcha videolarni olish"""
        print(f"\n📁 Kategoriya: {category_url}")
        all_videos = []
        
        for page in range(1, max_pages + 1):
            if page == 1:
                url = category_url
            else:
                url = f"{category_url}page{page}/"
            
            print(f"  📄 Sahifa {page}/{max_pages}")
            
            try:
                response = self.session.get(url, timeout=10)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Sahifa sarlavhasi
                h1 = soup.find('h1', class_='title')
                if h1:
                    print(f"  📝 {h1.text.strip()}")
                
                # Videolarni topish
                video_cards = soup.find_all('div', class_='video')
                
                if not video_cards:
                    print(f"  ⚠️ Boshqa video yo'q")
                    break
                
                for card in video_cards:
                    link = card.find_parent('a')
                    if link:
                        video = self._parse_video_card(card, link)
                        all_videos.append(video)
                
                print(f"  ✅ {len(video_cards)} ta video")
                
                # Paginatsiyani tekshirish
                pagenat = soup.find('div', class_='pagenat')
                if not pagenat or page >= max_pages:
                    break
                
                time.sleep(1)  # Kechikish
                
            except Exception as e:
                print(f"  ❌ Xatolik: {e}")
                break
        
        return all_videos
    
    def get_video_details(self, video_url):
        """Bitta video haqida to'liq ma'lumot"""
        print(f"  🎬 Tafsilotlar: {video_url}")
        
        try:
            response = self.session.get(video_url, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            details = {
                'url': video_url,
                'title': '',
                'views': 0,
                'date_added': '',
                'date_updated': '',
                'duration': '',
                'categories': [],
                'download_links': [],
                'likes': 0,
                'dislikes': 0,
                'related_videos': []
            }
            
            # Sarlavha
            h1 = soup.find('h1', class_='title')
            if h1:
                details['title'] = h1.text.strip()
            
            # Statistikalar
            icon_links = soup.find_all('a', class_='icon')
            if len(icon_links) >= 4:
                details['date_added'] = icon_links[0].text.strip()
                views_text = icon_links[1].text.strip()
                details['views'] = int(''.join(filter(str.isdigit, views_text)) or 0)
                details['date_updated'] = icon_links[2].text.strip()
                details['duration'] = icon_links[3].text.strip()
            
            # Like/Dislike
            like_div = soup.find('div', class_='like')
            if like_div:
                counter = like_div.find('span', class_='counter')
                if counter:
                    details['likes'] = int(counter.text.strip() or 0)
            
            dislike_div = soup.find('div', class_='like2')
            if dislike_div:
                counter = dislike_div.find('span', class_='counter')
                if counter:
                    details['dislikes'] = int(counter.text.strip() or 0)
            
            # Kategoriyalar
            cat_links = soup.find_all('a', class_='linkcat')
            for cat in cat_links:
                details['categories'].append({
                    'title': cat.text.strip(),
                    'url': urljoin(self.base_url, cat.get('href'))
                })
            
            # Yuklab olish linklari
            download_links = soup.find_all('a', class_='download')
            for dl in download_links:
                details['download_links'].append({
                    'url': urljoin(self.base_url, dl.get('href')),
                    'quality': dl.find('span').text.strip() if dl.find('span') else '480p'
                })
            
            # O'xshash videolar
            related_section = soup.find('div', class_='buttvideo')
            if related_section:
                next_div = related_section.find_next_sibling('div', class_='video')
                while next_div and 'video' in next_div.get('class', []):
                    link = next_div.find_parent('a')
                    if link:
                        related = self._parse_video_card(next_div, link)
                        details['related_videos'].append(related)
                    next_div = next_div.find_next_sibling('div', class_='video')
            
            return details
            
        except Exception as e:
            print(f"  ❌ Tafsilotlarda xatolik: {e}")
            return None
    
    def save_data(self, data, filename, format='json'):
        """Ma'lumotlarni saqlash"""
        if format == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == 'csv':
            if isinstance(data, list) and data:
                keys = data[0].keys()
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(data)
        
        print(f"💾 Saqlandi: {filename}")

def main():
    parser = SosalkinoFullParser()
    
    print("\n" + "="*60)
    print("🚀 SOSALKINO TO'LIQ PARSER")
    print("="*60)
    
    # 1. Asosiy sahifa ma'lumotlari
    main_data = parser.get_main_page_videos()
    
    if main_data:
        # Barcha ma'lumotlarni bitta faylga saqlash
        parser.save_data(main_data, 'main_page_all_data.json', 'json')
        
        # Har bir blokni alohida saqlash
        if main_data['new_videos']:
            parser.save_data(main_data['new_videos'], 'new_videos.json', 'json')
        
        if main_data['best_videos']:
            parser.save_data(main_data['best_videos'], 'best_videos.json', 'json')
        
        if main_data['top_videos']:
            parser.save_data(main_data['top_videos'], 'top_videos.json', 'json')
        
        if main_data['categories']:
            parser.save_data(main_data['categories'], 'categories.json', 'json')
        
        # Statistikani ko'rsatish
        print("\n" + "="*60)
        print("📊 UMUMIY STATISTIKA:")
        print(f"  🆕 Yangi videolar: {len(main_data['new_videos'])} ta")
        print(f"  ⭐ Eng yaxshi: {len(main_data['best_videos'])} ta")
        print(f"  🔥 Ommabop: {len(main_data['top_videos'])} ta")
        print(f"  📂 Kategoriyalar: {len(main_data['categories'])} ta")
        
        # 2. Kategoriyalar bilan ishlash
        print("\n" + "="*60)
        print("📂 KATEGORIYALAR RO'YXATI:")
        for i, cat in enumerate(main_data['categories'], 1):
            print(f"  {i:2d}. {cat['title']:<25} ({cat['video_count']} ta video)")
        
        # 3. Kategoriya tanlash
        print("\n" + "="*60)
        choice = input("🎯 Qaysi kategoriyani ko'rishni xohlaysiz?\n  0 - Hammasini\n  yoki raqamni kiriting (1-12): ")
        
        if choice == "0":
            # Barcha kategoriyalardagi videolarni olish
            all_category_videos = {}
            for cat in main_data['categories'][:3]:  # Faqat 3 ta kategoriya
                print(f"\n📁 {cat['title']} kategoriyasi...")
                videos = parser.get_category_page(cat['url'], max_pages=2)
                all_category_videos[cat['title']] = videos
            
            parser.save_data(all_category_videos, 'all_categories_videos.json', 'json')
        
        elif choice.isdigit() and 1 <= int(choice) <= len(main_data['categories']):
            # Tanlangan kategoriya
            selected_cat = main_data['categories'][int(choice) - 1]
            print(f"\n📁 {selected_cat['title']} kategoriyasi yuklanmoqda...")
            
            videos = parser.get_category_page(selected_cat['url'], max_pages=3)
            
            if videos:
                parser.save_data(videos, f'category_{selected_cat["title"]}.json', 'json')
                parser.save_data(videos, f'category_{selected_cat["title"]}.csv', 'csv')
                
                # Video tafsilotlari (ixtiyoriy)
                get_details = input("\n🎬 Video tafsilotlarini olishni xohlaysizmi? (ha/yo'q): ")
                
                if get_details.lower() == 'ha':
                    detailed_videos = []
                    for i, video in enumerate(videos[:3], 1):  # Faqat 3 ta video
                        print(f"\n  {i}/3: {video['title'][:50]}...")
                        details = parser.get_video_details(video['url'])
                        if details:
                            detailed_videos.append(details)
                        time.sleep(1)
                    
                    if detailed_videos:
                        parser.save_data(detailed_videos, 'video_details.json', 'json')
    
    print("\n" + "="*60)
    print("✅ PARSER ISHI TUGADI!")
    print("="*60)

if __name__ == "__main__":
    main()