# Content Search Bot v2.0

## Tavsif
Bu bot foydalanuvchilarga SQLite ma'lumotlar bazasidan video kontentlarni qidirish va ularning ma'lumotlarini ko'rish imkonini beradi.

## Xususiyatlar
- ✅ Inline qidiruv (SQLite bazadan)
- ✅ Kategoriya bo'yicha ko'rish
- ✅ Top videolar
- ✅ Premium tizimi
- ✅ Foydalanuvchi roziligi
- ✅ Kanal majburiy obunasi
- ✅ Admin panel
- ✅ Xabar tarqatish
- ✅ Statistika

## O'rnatish

### 1. Talablar
```bash
pip install -r requirements.txt
```

### 2. Konfiguratsiya
`.env.example` faylini `.env` ga nusxa oling va qiymatlarni to'ldiring:
```bash
cp .env.example .env
nano .env
```

### 3. Ma'lumotlar bazasini yaratish
`xxx_contend.py` dasturini ishga tushiring va ma'lumotlarni yig'ing:
```bash
python xxx_contend.py --auto
```

### 4. Botni ishga tushirish
```bash
python main.py
```

## Foydalanish

### Foydalanuvchi komandalar
- `/start` - Botni ishga tushirish
- `/help` - Yordam
- `/search [so'rov]` - Video qidirish
- `/top` - Top videolar
- `/profile` - Shaxsiy profil

### Admin komandalar
- `/admin` - Admin panel
- `/stats` - Statistika
- `/users` - Foydalanuvchilar ro'yxati
- `/gcast` - Xabar tarqatish (reply bilan)
- `/addpremium [id] [kun]` - Premium berish

### Inline qidiruv
```
@botname qidiruv so'rovi
```

## Arxitektura
```
Content Bot
├── xxx_contend.py      # Ma'lumotlarni yig'ish
├── database.py         # SQLite boshqaruvi
├── config.py           # Konfiguratsiya
├── bot.py              # Asosiy bot
├── main.py             # Ishga tushirish
└── handlers/
    ├── start.py        # Start, rozilik
    ├── search.py       # Qidiruv
    ├── video.py        # Video ma'lumotlari
    └── admin.py        # Admin panel
```

## Xavfsizlik
- Tokenlar .env faylda saqlanadi
- SQL injection himoyasi
- Rate limiting
- Foydalanuvchi ma'lumotlari himoyasi

## Litsenziya
Bu bot faqat ta'lim maqsadlarida ishlatiladi.
