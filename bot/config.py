"""Humo Med bot — barcha sozlamalar shu yerda.

Maxfiy kalitlar (token, API kalitlar) KODGA YOZILMAYDI — ular .env faylda turadi.
"""
import os
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# ---------- Maxfiy kalitlar (.env) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "cgSgspJ2msm6clMCkdW9")  # Jessica
ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_v3")

# ---------- Sayt (WebApp) va server ----------
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://sbznq6skg4-wq.github.io/Humo-medbot/")
_u = urlparse(WEBAPP_URL)
# CORS uchun faqat "sxema://host" kerak (yo'lsiz): https://sbznq6skg4-wq.github.io
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", f"{_u.scheme}://{_u.netloc}").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
DB_PATH = os.getenv("DB_PATH", "data/humo.db")  # Render'da Disk ulang: /data/humo.db
MEDIA_DIR = os.getenv("MEDIA_DIR", "data/media")  # saytga yuklangan rasm/videolar (Disk ichida bo'lsin)

# ---------- Adminlar ----------
OWNER_ID = 8196942761  # yaratuvchi: support murojaatlari, /status, /aitest, /ttstest, xato xabarlari
ADMINS = {5597701502, 663593026, 8196942761}  # to'liq huquq: /admin, arizalar, rassilka
ORDERS_CHAT_ID = -1004466442357  # arizalar tushadigan kanal

# ---------- Klinika ----------
CLINIC_PHONE = "+998979921111"
MAP_URL = "https://maps.app.goo.gl/DhSA68hzcFURT8Hx6?g_st=ic"
BOT_USERNAME = "humo_med_bot"
TZ = ZoneInfo("Asia/Tashkent")

PRICE_NORMAL = 70_000  # oddiy konsultatsiya
PRICE_BOT = 50_000  # bot orqali yozilganda (1 marta, 1 foydalanuvchi)
PRICE_WARD_NORMAL = 200_000
PRICE_WARD_LUX = 250_000
REF_DISCOUNT_PER_FRIEND = 1  # har bir taklif qilingan do'st uchun 1%
MAX_REF_DISCOUNT = 10  # ko'pi bilan 10% (soxta akkauntlardan himoya)

DOCTORS = {
    "hasan": {
        "name": "Sulaymonov Hasanjon Tohirjonovich",
        "photos": ["doctor_hasan", "doctor_hasan_2"],
    },
    "zuh": {
        "name": "Xolikov Zuhriddin Muhiddin o'g'li",
        "photos": ["doctor_zuh"],
    },
}

# ---------- Media (file_id) ----------
# "BAAC..." — video, "AgAC..." — rasm. Bo'sh qator ("") bo'lsa, o'sha media o'tkazib yuboriladi.
# file_id faqat SHU token egasi bo'lgan bot uchun ishlaydi.
MEDIA = {
    "intro_video": "BAACAgIAAxkDAAIBE2r0-wujQC12yb9U4wbuTdIQIJQ_AAKxrwAC0ZWoSzY8JJzym6L-PQQ",
    "location_video": "BAACAgIAAxkDAAIBFGr1AAE60JNxR88v2SiP-8ZrcIx1twACta8AAtGVqEs-qTQwb4DkqD0E",
    "work_photo_1": "AgACAgIAAxkDAAODavR601Qn_o1Cgiz5Vk_XTu2eSHAAAmAbaxvRlahL6hVt01qvIKIBAAMCAAN3AAM9BA",
    "work_photo_2": "AgACAgIAAxkDAAOjavR7Gz3PCH5T6-EM4SeVTZFB17EAAnIbaxvRlahLSsVfmMp_h3IBAAMCAAN3AAM9BA",
    "work_video": "",  # <- ish jarayoni videosi ID sini shu yerga qo'ying
    "patients_video": "BAACAgIAAxkDAAIBF2r1Bh5H3ir82y-dL27bEBzpWjZOAAK5rwAC0ZWoS_JpHIijE3DhPQQ",
    "laser_photo": "AgACAgIAAxkDAAOWavR7AsqdmcxXRl2ns1S_d7DOzjcAAmcbaxvRlahLRzXvyt4zDxwBAAMCAAN3AAM9BA",
    "laser_video_1": "BAACAgIAAxkDAAIBFmr1Bh1UbfzOmvVKLWX8X1d6srDRAAK4rwAC0ZWoS3Aj364Z0Kn_PQQ",
    "laser_video_2": "BAACAgIAAxkDAAPVavTG713ECi9MHazG8VatHXZmZ4EAApKuAALRlahLz4CbpZnTXqk9BA",
    "hemorrhoid_1": "BAACAgIAAxkDAAP7avTlU3-vLr6qMGDAHyc__SsoIOIAAnCvAALRlahL9Yjvk5ZsuUo9BA",
    "hemorrhoid_2": "BAACAgIAAxkDAAP8avTmi-MUDwI2Y8zjygY_qX1XqGYAAnWvAALRlahLGJOY6U8L6io9BA",
    "cert_1": "AgACAgIAAxkDAAOeavR7E0--AmBUlyJsjbRThTbUrCsAAm0baxvRlahLUsj5L96Dy38BAAMCAAN3AAM9BA",
    "cert_2": "AgACAgIAAxkDAAOdavR7EjCh1vYM6SGoj_BxpyWFygYAAmwbaxvRlahLXrmbUePEphcBAAMCAAN3AAM9BA",
    "reception_1": "AgACAgIAAxkDAAOgavR7FvPv9VSfAAF5mBCsaiYZ2v25AAJvG2sb0ZWoS2tGOffKcN5WAQADAgADdwADPQQ",
    "reception_2": "AgACAgIAAxkDAAOfavR7FTaeaI8b8Wg8DHFKMdK44mgAAm4baxvRlahLIbz725MZxMYBAAMCAAN3AAM9BA",
    "doctor_zuh": "AgACAgIAAxkDAAOIavR62TPRVoDWU5a_66jpK4mOzgYAAmIbaxvRlahL6wmgyyAkeHABAAMCAAN4AAM9BA",
    "doctor_hasan": "AgACAgIAAxkDAAOOavR65KqzaFWr3NK6S6Mbf8HhsCYAAmQbaxvRlahL5hQURuEKcWoBAAMCAAN5AAM9BA",
    "doctor_hasan_2": "AgACAgIAAxkDAAOiavR7GYMxuAQ5GPP03aiaPC3Dgr0AAnEbaxvRlahLgJtmwGxCGlMBAAMCAAN3AAM9BA",
    "ward_normal_photo": "AgACAgIAAxkDAAOYavR7B7eVs4oyaPBOus-_CwWVqXAAAmkbaxvRlahLNhHeRINuBocBAAMCAAN3AAM9BA",
    "ward_normal_video": "BAACAgIAAxkDAAP4avTjci5zKZ07cPkTKvuFWdEoxMAAAmivAALRlahLpms-HvBwBUc9BA",
    "ward_lux2_photo": "AgACAgIAAxkDAAOXavR7Bn9Obj1TreHxTiPyYsE7UsUAAmgbaxvRlahLNcvqV1QvSzYBAAMCAAN3AAM9BA",
    "ward_lux_video": "BAACAgIAAxkDAAP3avTjcffMtgGqRXzsCs6QcsciJFYAAmevAALRlahLNhzi3gar-Us9BA",
    "ward_lux3_video_1": "BAACAgIAAxkDAAIBC2r09cwjXA74Pxe2Yu_U35wew9LMAAKhrwAC0ZWoSw9uv2pGLAT1PQQ",
    "ward_lux3_video_2": "BAACAgIAAxkDAAP2avTjb0MAASy3xGLU0Ins4yHxefQoAAJmrwAC0ZWoS7-MV8z7yZQmPQQ",
    "ward_bath_video": "BAACAgIAAxkDAAIBDmR09dKIUmtlvArHjMQSqwlBF9INAAKkrwAC0ZWoS3rwfRca6iXqPQQ",
    "logo": "AgACAgIAAxkDAAOFavR61Zr_LE_7-YibyXVueDhQ6rgAAmEbaxvRlahLsiEJg0-mZeYBAAMCAAN4AAM9BA",
    # Faqat sayt ichida ko'rsatiladigan "kirish videosi" botdan yuborilmaydi.
}


def fmt_price(n: int) -> str:
    return f"{n:,}".replace(",", " ")
