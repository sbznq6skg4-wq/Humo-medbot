# Humo Med — bot + sayt

Papkalar: `humo_med_full/bot/` (Telegram bot, API, baza) va root'dagi sayt fayllari (`index.html`, `config.js`, `img/`, `video/`).

## 1. Kompyuterda ishga tushirish (VS Code)
1. Python 3.10+ o'rnating. VS Code'da `bot` papkasini oching.
2. `env.example.txt` ni **`.env`** deb nomlang va to'ldiring:
   - `BOT_TOKEN` — @BotFather'dan **yangi** token (eskisi chatda ochiq qolgan, `/revoke` qiling)
   - `GEMINI_API_KEY` — Google AI Studio'dan **yangi** kalit (eskisini o'chiring)
   - `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` (Jessica), `ELEVENLABS_MODEL` (saytda sinagan modelingiz)
3. Terminal:
   ```
   python -m venv venv
   venv\Scripts\activate        (Mac: source venv/bin/activate)
   pip install -r requirements.txt
   python main.py
   ```
4. Telegramda `/start`. Sinash: `/admin`.

## 2. Telegramdagi sozlamalar
- Adminlarning har biri botga bir marta `/start` bossin (aks holda bot ularga yoza olmaydi).
- Bot **kanalda admin** bo'lishi kerak (arizalar -1004466442357 ga tushadi, tugmalar ishlashi uchun xabarlarni tahrirlash huquqi kerak).
- `file_id` lar faqat **shu token egasi botga** ishlaydi. Yangi rasm/video ID kerak bo'lsa, admin botga rasm/video yuborsa, bot ID ni qaytaradi.
- `bot/config.py` dagi `MEDIA["work_video"]` bo'sh: ish jarayoni videosining ID sini shu yerga qo'ying.

## 3. Sayt (GitHub Pages)
1. `config.js` ichidagi `window.HUMO_API` qiymatini Render manzilingizga almashtiring.
2. GitHub repozitoriy sozlamalaridagi **Pages** bo'limidan `main` branch va `/(root)` ni tanlang.
3. Rasm va videolarni `img/` va `video/` ichida saqlang.
3. Saytning admin paneli faqat adminlarga ko'rinadi: server Telegram `initData` ni tekshiradi.

## 4. Render
- Turi: **Web Service**. Build: `pip install -r requirements.txt`. Start: `python main.py` (ildiz papka: `bot`).
- Environment: `.env` dagi qiymatlar. **Disk** ulang (`/data`) va `DB_PATH=/data/humo.db` qo'ying, aks holda baza har deployda o'chadi.
- Bepul tarif 15 daqiqada uxlaydi: `https://<manzil>/health` ni UptimeRobot bilan har 5 daqiqada tekshirtiring yoki pullik tarifni oling (24/7 klinika uchun tavsiya).

## 5. Nimalar bor
Til tanlash (uz/ru/en), kirish videosi, shifokorlar, palatalar, klinika haqida, gemorroy testi, manzil, "menga telefon qiling",
qabulga yozilish (kanalga + adminlarga tugmalar bilan: qabul / rad / vaqt / shifokor / javob), eslatmalar (1 kun va 2 soat oldin),
AI maslahatchi (Gemini) + 🔊 ovozli javob (ElevenLabs), do'st taklifi (har do'stga 1%, ko'pi bilan 10%),
admin panel (`/admin`): statistika, bugungi qabullar, arizalar, qo'ng'iroqlar, savollar, foydalanuvchilar, rassilka,
majburiy obuna (kanalni o'rnatish + yoqish/o'chirish), AI yoqish/o'chirish, CSV eksport, bloklash.

Eslatma: eslatma ishlashi uchun qabul vaqti `15.12.2026 15:00` ko'rinishida bo'lishi kerak. Boshqacha yozilsa, admin
"🕒 Vaqtni o'zgartirish" orqali aniq vaqtni kiritadi.
