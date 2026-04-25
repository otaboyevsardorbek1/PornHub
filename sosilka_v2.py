import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re
from urllib.parse import urljoin, urlparse

class SosalkinoBestParser:
    """sosalkino.best sayti uchun to'liq parser"""
    
    def __init__(self):
        self.base_url = "https://r.sosalkino.best"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def get_soup(self, url):
        """HTML ni yuklash va pars qilish"""
        try:
            response = self.session.get(url, timeout=15)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            else:
                print(f"❌ HTTP xatolik: {response.status_code} - {url}")
                return None
        except Exception as e:
            print(f"❌ So'rov xatolik: {e}")
            return None
    
    def parse_main_page(self, page=1):
        """Asosiy sahifadagi videolarni olish"""
        print(f"\n📄 Bosh sahifa - {page}-bet")
        url = self.base_url if page == 1 else f"{self.base_url}/{page}/"
        
        soup = self.get_soup(url)
        if not soup:
            return []
        
        videos = []
        items = soup.find_all('div', class_='item')
        
        for item in items:
            link = item.find('a', class_='link')
            if not link:
                continue
            
            img_holder = item.find('div', class_='img-holder')
            info_holder = item.find('div', class_='info-holder')
            title_item = item.find('div', class_='title-item')
            
            video = {
                'title': title_item.find('p', class_='title').text.strip() if title_item and title_item.find('p', class_='title') else '',
                'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                'thumbnail': '',
                'duration': '',
                'date_added': '',
                'views': '',
                'rating': '',
                'preview_url': '',
            }
            
            # Rasm
            if img_holder:
                img = img_holder.find('img', class_='thumb')
                if img:
                    video['thumbnail'] = img.get('data-src', img.get('src', ''))
                video['preview_url'] = img_holder.get('data-preview', '')
            
            # Qo'shimcha ma'lumotlar
            if info_holder:
                infos = info_holder.find_all('div', class_='item-info')
                for info in infos:
                    text = info.find('span', class_='text')
                    icon = info.find('i')
                    if text and icon:
                        if 'icon-clock' in icon.get('class', []):
                            video['duration'] = text.text.strip()
                        elif 'icon-calendar' in icon.get('class', []):
                            video['date_added'] = text.text.strip()
                        elif 'icon-eye' in icon.get('class', []):
                            video['views'] = text.text.strip().replace('\u2009', '')
                        elif 'icon-like' in icon.get('class', []):
                            video['rating'] = text.text.strip()
            
            videos.append(video)
        
        print(f"  ✅ {len(videos)} ta video topildi")
        return videos
    
    def parse_categories_alphabetical(self):
        """Kategoriyalarni alifbo tartibida olish"""
        print("\n📋 Kategoriyalar (alifbo bo'yicha) yuklanmoqda...")
        url = f"{self.base_url}/categories/"
        
        soup = self.get_soup(url)
        if not soup:
            return []
        
        categories = []
        
        # Alfavit bo'yicha kategoriyalar (tab-content active)
        tabs_content = soup.find('div', class_='tabs-content', attrs={'data-group-open': 'title'})
        if tabs_content:
            letter_holders = tabs_content.find_all('div', class_='letter-holder')
            for holder in letter_holders:
                items = holder.find_all('div', class_='item')
                for item in items:
                    link = item.find('a', class_='link')
                    if link:
                        title = link.find('span', class_='title')
                        quantity = link.find('span', class_='quantity')
                        categories.append({
                            'title': title.text.strip() if title else '',
                            'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                            'video_count': quantity.text.strip() if quantity else '0'
                        })
        
        # Janr bo'yicha kategoriyalar
        groups_content = soup.find('div', class_='tabs-content', attrs={'data-group-open': 'groups'})
        if groups_content:
            groups = groups_content.find_all('div', class_='category-group')
            for group in groups:
                group_title = group.find('div', class_='title-group')
                items = group.find_all('div', class_='item')
                for item in items:
                    link = item.find('a', class_='link')
                    if link:
                        title = link.find('span', class_='title')
                        quantity = link.find('span', class_='quantity')
                        categories.append({
                            'title': title.text.strip() if title else '',
                            'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                            'video_count': quantity.text.strip() if quantity else '0',
                            'group': group_title.text.strip() if group_title else ''
                        })
        
        print(f"✅ {len(categories)} ta kategoriya topildi")
        return categories
    
    def parse_category_page(self, category_url, max_pages=3):
        """Kategoriya sahifasidan videolarni olish"""
        print(f"\n📁 Kategoriya: {category_url}")
        
        all_videos = []
        # URL ni tozalash
        base_url = category_url.rstrip('/')
        
        for page in range(1, max_pages + 1):
            if page == 1:
                url = base_url + '/'
            else:
                url = f"{base_url}/{page}/"
            
            soup = self.get_soup(url)
            if not soup:
                break
            
            videos = self._extract_videos_from_page(soup)
            all_videos.extend(videos)
            
            print(f"  📄 Sahifa {page}: {len(videos)} ta video")
            
            # Keyingi sahifa borligini tekshirish
            pagination = soup.find('div', class_='pagination')
            if not pagination:
                break
            
            time.sleep(0.5)
        
        print(f"  ✅ Jami: {len(all_videos)} ta video")
        return all_videos
    
    def parse_photos_page(self, page=1):
        """Foto albomlarni olish"""
        print(f"\n📷 Foto albomlar - {page}-bet")
        url = f"{self.base_url}/photos/" if page == 1 else f"{self.base_url}/photos/{page}/"
        
        soup = self.get_soup(url)
        if not soup:
            return []
        
        photos = []
        items = soup.find_all('div', class_='item')
        
        for item in items:
            link = item.find('a', class_='link')
            if not link:
                continue
            
            img_holder = item.find('div', class_='img-holder')
            models_title = item.find('div', class_='models-title')
            info_div = item.find('div', class_='info')
            categor_holder = item.find('div', class_='categor-holder')
            
            photo = {
                'title': '',
                'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                'thumbnail': '',
                'date': '',
                'views': '',
                'photo_count': '',
                'rating': '',
                'likes': '',
                'studio': '',
                'models': []
            }
            
            if models_title:
                model_span = models_title.find('span', class_='model')
                if model_span:
                    photo['title'] = model_span.text.strip()
            
            if img_holder:
                img = img_holder.find('img', class_='img')
                if img:
                    photo['thumbnail'] = img.get('data-src', img.get('src', ''))
            
            if info_div:
                infos = info_div.find_all('div', class_='item-info')
                for info in infos:
                    text = info.find('span', class_='text')
                    icon = info.find('i')
                    if text and icon:
                        icon_class = ' '.join(icon.get('class', []))
                        if 'icon-calendar' in icon_class:
                            photo['date'] = text.text.strip()
                        elif 'icon-eye' in icon_class:
                            photo['views'] = text.text.strip()
                        elif 'icon-camera' in icon_class:
                            photo['photo_count'] = text.text.strip()
                        elif 'icon-star' in icon_class:
                            photo['rating'] = text.text.strip()
                        elif 'icon-like' in icon_class:
                            photo['likes'] = text.text.strip()
            
            if categor_holder:
                rows = categor_holder.find_all('div', class_='row')
                for row in rows:
                    row_title = row.find('p', class_='row-title')
                    if row_title and 'Студия' in row_title.text:
                        studio_item = row.find('span', class_='row-item')
                        if studio_item:
                            photo['studio'] = studio_item.text.strip()
                    elif row_title and 'Модели' in row_title.text:
                        model_items = row.find_all('span', class_='row-item')
                        photo['models'] = [m.text.strip() for m in model_items]
            
            photos.append(photo)
        
        print(f"  ✅ {len(photos)} ta albom topildi")
        return photos
    
    def parse_models_page(self, url=None):
        """Modellarni olish"""
        if url is None:
            url = f"{self.base_url}/actresses/"
        
        print(f"\n👤 Modellar: {url}")
        soup = self.get_soup(url)
        if not soup:
            return []
        
        models = []
        items = soup.find_all('div', class_='item')
        
        for item in items:
            link = item.find('a', class_='link')
            if not link:
                continue
            
            img_holder = item.find('div', class_='img-holder')
            info_holder = item.find('div', class_='info-holder')
            
            model = {
                'name': '',
                'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                'image': '',
                'country': '',
                'video_count': '',
                'rating': '',
            }
            
            # Rasm
            if img_holder:
                img = img_holder.find('img', class_='img')
                if img:
                    model['image'] = img.get('data-src', img.get('src', ''))
                
                # Mamlakat
                country_img = img_holder.find('span', class_='country_img')
                if country_img:
                    flag_img = country_img.find('img')
                    if flag_img:
                        model['country'] = flag_img.get('title', '')
            
            # Ma'lumotlar
            if info_holder:
                title = info_holder.find('p', class_='title')
                if title:
                    model['name'] = title.text.strip()
                
                quantity = info_holder.find('span', class_='quantity')
                if quantity:
                    model['video_count'] = quantity.text.strip()
                
                rating_span = info_holder.find('span', class_='rating')
                if rating_span:
                    model['rating'] = rating_span.text.strip()
            
            models.append(model)
        
        print(f"  ✅ {len(models)} ta model topildi")
        return models
    
    def parse_video_page(self, video_url):
        """Alohida video sahifasini to'liq olish"""
        print(f"  🎬 Video: {video_url}")
        soup = self.get_soup(video_url)
        if not soup:
            return None
        
        details = {
            'url': video_url,
            'title': '',
            'description': '',
            'tags': [],
            'models': [],
            'categories': [],
            'views': '',
            'rating': '',
            'likes': '',
            'dislikes': '',
            'comments': []
        }
        
        # Sarlavha
        title_elem = soup.find('h1', class_='title')
        if title_elem:
            details['title'] = title_elem.text.strip()
        
        # Ko'rishlar
        view_elem = soup.find('p', class_='view-video')
        if view_elem:
            bold = view_elem.find('span', class_='bold')
            if bold:
                details['views'] = bold.text.strip()
        
        # Kategoriyalar
        cat_holder = soup.find('div', class_='categor-holder')
        if cat_holder:
            cat_links = cat_holder.find_all('a')
            for cat in cat_links:
                details['categories'].append({
                    'title': cat.text.strip(),
                    'url': urljoin(self.base_url, cat.get('href', ''))
                })
        
        # Like/Dislike
        rating_fav = soup.find('div', class_='rating-fav')
        if rating_fav:
            likes_btn = rating_fav.find('a', class_='like')
            dislikes_btn = rating_fav.find('a', class_='dislike')
            
            if likes_btn:
                quantity = likes_btn.find('span', class_='quantity')
                if quantity:
                    details['likes'] = quantity.text.strip()
            
            if dislikes_btn:
                quantity = dislikes_btn.find('span', class_='quantity')
                if quantity:
                    details['dislikes'] = quantity.text.strip()
        
        # Tavsif
        desc_elem = soup.find('p', class_='description')
        if desc_elem:
            desc_text = desc_elem.text.strip()
            
            # Teglar va modellarni ajratish
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
        
        # Kommentariyalar (agar mavjud bo'lsa)
        comment_items = soup.find_all('div', class_='comment-item')
        for comment in comment_items:
            user_name = comment.find('span', class_='user-name')
            comment_text = comment.find('div', class_='text')
            if user_name and comment_text:
                details['comments'].append({
                    'user': user_name.text.strip(),
                    'text': comment_text.text.strip()
                })
        
        return details
    
    def _extract_videos_from_page(self, soup):
        """Sahifadan videolarni ajratib olish (yordamchi metod)"""
        videos = []
        items = soup.find_all('div', class_='item')
        
        for item in items:
            link = item.find('a', class_='link')
            if not link:
                continue
            
            img_holder = item.find('div', class_='img-holder')
            info_holder = item.find('div', class_='info-holder')
            title_item = item.find('div', class_='title-item')
            
            video = {
                'title': '',
                'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                'thumbnail': '',
                'duration': '',
                'date_added': '',
                'views': '',
                'rating': '',
                'is_premium': False,
                'has_russian_audio': False,
            }
            
            if title_item:
                title_p = title_item.find('p', class_='title')
                if title_p:
                    video['title'] = title_p.text.strip()
            
            if img_holder:
                img = img_holder.find('img', class_='thumb')
                if img:
                    video['thumbnail'] = img.get('data-src', img.get('src', ''))
                
                # Premium tekshirish
                premium_icons = img_holder.find('div', class_='premium-icons')
                if premium_icons:
                    diamond = premium_icons.find('img', src=lambda x: x and 'diamond' in x)
                    if diamond:
                        video['is_premium'] = True
                    
                    russian_audio = premium_icons.find('div', string='Русская озвучка')
                    if russian_audio:
                        video['has_russian_audio'] = True
            
            if info_holder:
                infos = info_holder.find_all('div', class_='item-info')
                for info in infos:
                    text = info.find('span', class_='text')
                    icon = info.find('i')
                    if text and icon:
                        icon_class = ' '.join(icon.get('class', []))
                        if 'icon-clock' in icon_class:
                            video['duration'] = text.text.strip()
                        elif 'icon-calendar' in icon_class:
                            video['date_added'] = text.text.strip()
                        elif 'icon-eye' in icon_class:
                            video['views'] = text.text.strip().replace('\u2009', '')
                        elif 'icon-like' in icon_class:
                            video['rating'] = text.text.strip()
            
            videos.append(video)
        
        return videos
    
    def parse_studios_page(self):
        """Studiyalarni olish"""
        print("\n🏢 Studiyalar yuklanmoqda...")
        url = f"{self.base_url}/studios/"
        
        soup = self.get_soup(url)
        if not soup:
            return []
        
        studios = []
        items = soup.find_all('div', class_='item')
        
        for item in items:
            link = item.find('a', class_='link')
            if not link:
                continue
            
            img_holder = item.find('div', class_='img-holder')
            title_item = item.find('div', class_='title-item')
            
            studio = {
                'name': '',
                'url': urljoin(self.base_url, link.get('href')) if link.get('href') else '',
                'image': '',
                'video_count': '',
            }
            
            if title_item:
                title = title_item.find('p', class_='title')
                if title:
                    studio['name'] = title.text.strip()
                
                quantity = title_item.find('span', class_='quantity')
                if quantity:
                    studio['video_count'] = quantity.text.strip()
            
            if img_holder:
                img = img_holder.find('img', class_='img')
                if img:
                    studio['image'] = img.get('data-src', img.get('src', ''))
            
            studios.append(studio)
        
        print(f"✅ {len(studios)} ta studiya topildi")
        return studios
    
    def save_json(self, data, filename):
        """JSON faylga saqlash"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 Saqlandi: {filename}")
    
    def save_csv(self, data, filename):
        """CSV faylga saqlash"""
        if not data:
            return
        
        import csv
        # Barcha kalitlarni yig'ish
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        
        # Ro'yxatlarni string ga o'tkazish
        flat_data = []
        for item in data:
            flat_item = {}
            for key, value in item.items():
                if isinstance(value, list):
                    flat_item[key] = ', '.join(str(v) if isinstance(v, str) else str(v.get('title', v)) for v in value)
                else:
                    flat_item[key] = value
            flat_data.append(flat_item)
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(flat_data)
        print(f"💾 Saqlandi: {filename}")


def main():
    parser = SosalkinoBestParser()
    
    print("="*60)
    print("🚀 SOSALKINO.BEST PARSER")
    print("="*60)
    
    while True:
        print("\n" + "="*60)
        print("📋 MENYU:")
        print("="*60)
        print("1. Asosiy sahifadagi videolarni olish")
        print("2. Kategoriyalarni olish")
        print("3. Foto albomlarni olish")
        print("4. Modellarni olish")
        print("5. Studiyalarni olish")
        print("6. Kategoriya bo'yicha videolarni olish")
        print("7. Video tafsilotlarini olish")
        print("8. HAMMASINI bir vaqtda olish")
        print("0. Chiqish")
        
        choice = input("\nTanlang (0-8): ").strip()
        
        if choice == "1":
            max_pages = int(input("Nechta sahifa olinsin? (1-10): ") or "3")
            all_videos = []
            for page in range(1, max_pages + 1):
                videos = parser.parse_main_page(page)
                all_videos.extend(videos)
                time.sleep(0.5)
            
            if all_videos:
                parser.save_json(all_videos, 'main_page_videos.json')
                parser.save_csv(all_videos, 'main_page_videos.csv')
        
        elif choice == "2":
            categories = parser.parse_categories_alphabetical()
            if categories:
                parser.save_json(categories, 'categories.json')
                parser.save_csv(categories, 'categories.csv')
        
        elif choice == "3":
            max_pages = int(input("Nechta sahifa olinsin? (1-5): ") or "2")
            all_photos = []
            for page in range(1, max_pages + 1):
                photos = parser.parse_photos_page(page)
                all_photos.extend(photos)
                time.sleep(0.5)
            
            if all_photos:
                parser.save_json(all_photos, 'photos.json')
                parser.save_csv(all_photos, 'photos.csv')
        
        elif choice == "4":
            # Avval kategoriyalarni olish, keyin modellar
            url = input("Modellar URL (bo'sh qoldirilsa aktrisalar olinadi): ").strip()
            if not url:
                url = f"{parser.base_url}/actresses/"
            else:
                url = urljoin(parser.base_url, url) if not url.startswith('http') else url
            
            models = parser.parse_models_page(url)
            if models:
                parser.save_json(models, 'models.json')
                parser.save_csv(models, 'models.csv')
        
        elif choice == "5":
            studios = parser.parse_studios_page()
            if studios:
                parser.save_json(studios, 'studios.json')
                parser.save_csv(studios, 'studios.csv')
        
        elif choice == "6":
            cat_url = input("Kategoriya URL: ").strip()
            max_pages = int(input("Nechta sahifa? (1-5): ") or "2")
            
            if not cat_url.startswith('http'):
                cat_url = urljoin(parser.base_url, cat_url)
            
            videos = parser.parse_category_page(cat_url, max_pages)
            if videos:
                parser.save_json(videos, 'category_videos.json')
                parser.save_csv(videos, 'category_videos.csv')
        
        elif choice == "7":
            video_url = input("Video URL: ").strip()
            if not video_url.startswith('http'):
                video_url = urljoin(parser.base_url, video_url)
            
            details = parser.parse_video_page(video_url)
            if details:
                parser.save_json([details], 'video_details.json')
                
                print("\n" + "="*60)
                print("📋 VIDEO TAFSILOTLARI:")
                print("="*60)
                print(f"Sarlavha: {details['title']}")
                print(f"Ko'rishlar: {details['views']}")
                print(f"Like: {details['likes']} | Dislike: {details['dislikes']}")
                print(f"Kategoriyalar: {', '.join(c['title'] for c in details['categories'])}")
                print(f"Teglar: {', '.join(details['tags'][:5])}")
                print(f"Modellar: {', '.join(details['models'])}")
                print(f"Kommentariyalar: {len(details['comments'])} ta")
        
        elif choice == "8":
            print("\n🔄 HAMMASI OLINMOQDA...")
            
            # 1. Asosiy sahifa
            all_videos = []
            for page in range(1, 3):
                videos = parser.parse_main_page(page)
                all_videos.extend(videos)
                time.sleep(0.5)
            parser.save_json(all_videos, 'all_main_videos.json')
            
            # 2. Kategoriyalar
            categories = parser.parse_categories_alphabetical()
            parser.save_json(categories, 'all_categories.json')
            
            # 3. Fotosuratlar
            all_photos = []
            for page in range(1, 3):
                photos = parser.parse_photos_page(page)
                all_photos.extend(photos)
                time.sleep(0.5)
            parser.save_json(all_photos, 'all_photos.json')
            
            # 4. Modellar
            models = parser.parse_models_page()
            parser.save_json(models, 'all_models.json')
            
            # 5. Studiyalar
            studios = parser.parse_studios_page()
            parser.save_json(studios, 'all_studios.json')
            
            print(f"\n📊 JAMI:")
            print(f"  • Videolar: {len(all_videos)} ta")
            print(f"  • Kategoriyalar: {len(categories)} ta")
            print(f"  • Foto albomlar: {len(all_photos)} ta")
            print(f"  • Modellar: {len(models)} ta")
            print(f"  • Studiyalar: {len(studios)} ta")
        
        elif choice == "0":
            print("\n👋 Chiqish...")
            break
        
        else:
            print("❌ Noto'g'ri tanlov!")


if __name__ == "__main__":
    main()