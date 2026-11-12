"""Xizmatlar: media yuborish, Gemini AI, ElevenLabs ovoz, ariza xabarlari, eslatmalar."""
import asyncio
import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InputMediaPhoto

import config
import db
from ai_prompt import SYSTEM_INSTRUCTION
from keyboards import cb, kb
from texts import tr

log = logging.getLogger("humo")

# ------------------------------------------------------------------ media
async def send_media(bot: Bot, chat_id: int, key: str, caption: str | None = None, markup=None) -> bool:
    """file_id bo'yicha rasm/videoni yuboradi. ID bo'sh yoki xato bo'lsa, jim o'tib ketadi."""
    fid = config.MEDIA.get(key, "")
    if not fid:
        if caption or markup:
            await bot.send_message(chat_id, caption or "👇", reply_markup=markup)
        return False
    try:
        if fid.startswith("BAAC"):
            await bot.send_video(chat_id, fid, caption=caption, reply_markup=markup)
        else:
            await bot.send_photo(chat_id, fid, caption=caption, reply_markup=markup)
        return True
    except TelegramBadRequest as e:
        log.error("MEDIA XATO [%s]: %s", key, e)
        if caption or markup:
            await bot.send_message(chat_id, caption or "👇", reply_markup=markup)
        return False


async def send_album(bot: Bot, chat_id: int, keys: list[str], caption: str | None = None) -> None:
    """Bir nechta rasmni albom qilib yuboradi (birinchisiga izoh)."""
    ids = [config.MEDIA.get(k, "") for k in keys if config.MEDIA.get(k, "")]
    if not ids:
        if caption:
            await bot.send_message(chat_id, caption)
        return
    if len(ids) == 1:
        await send_media(bot, chat_id, keys[0], caption)
        return
    media = [InputMediaPhoto(media=fid, caption=caption if i == 0 else None) for i, fid in enumerate(ids)]
    try:
        await bot.send_media_group(chat_id, media)
    except TelegramBadRequest as e:
        log.error("ALBOM XATO %s: %s", keys, e)
        if caption:
            await bot.send_message(chat_id, caption)


# ----------------------------------------------------------- tezlik limiti
class Limiter:
    def __init__(self, n: int, per: int):
        self.n, self.per, self.hits = n, per, {}

    def allow(self, key) -> bool:
        t = time.time()
        lst = [x for x in self.hits.get(key, []) if t - x < self.per]
        ok = len(lst) < self.n
        if ok:
            lst.append(t)
        self.hits[key] = lst
        return ok


AI_LIMIT = Limiter(15, 3600)  # soatiga 15 savol
TTS_LIMIT = Limiter(10, 86400)  # kuniga 10 ta ovozli javob

# ----------------------------------------------------------------- HTTP
_http: aiohttp.ClientSession | None = None


def http() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
    return _http


async def close_http() -> None:
    if _http and not _http.closed:
        await _http.close()


# ---------------------------------------------------------------- Gemini
async def ask_gemini(history: list[dict], text: str) -> str:
    """Gemini'ga savol yuboradi. history: [{"role": "user"/"model", "parts": [{"text": ...}]}]"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [*history, {"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500},
    }
    async with http().post(url, json=body, headers={"x-goog-api-key": config.GEMINI_API_KEY}) as r:
        data = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"Gemini {r.status}: {str(data)[:300]}")
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Gemini bo'sh javob: {str(data)[:300]}")
    answer = "".join(p.get("text", "") for p in parts).strip()
    if not answer:
        raise RuntimeError("Gemini bo'sh matn qaytardi")
    return answer


# ------------------------------------------------------------ ElevenLabs
def clean_for_tts(text: str, limit: int = 1100) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


async def eleven_tts(text: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVEN_VOICE_ID}"
    body = {"text": text, "model_id": config.ELEVEN_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}
    headers = {"xi-api-key": config.ELEVEN_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    async with http().post(url, params={"output_format": "mp3_44100_128"}, json=body, headers=headers) as r:
        if r.status != 200:
            raise RuntimeError(f"ElevenLabs {r.status}: {(await r.text())[:300]}")
        return await r.read()


# ------------------------------------------------------------ vaqt yordamchilari
_DT = re.compile(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\s+(\d{1,2})[:.](\d{2})")


def parse_dt(text: str) -> datetime | None:
    """'15.12.2026 15:00' yoki '15.12 15:00' ni UTC datetime'ga aylantiradi. Topilmasa None."""
    m = _DT.search(text or "")
    if not m:
        return None
    d, mo, y, h, mi = m.groups()
    now_local = datetime.now(config.TZ)
    year = int(y) if y else now_local.year
    if year < 100:
        year += 2000
    try:
        local = datetime(year, int(mo), int(d), int(h), int(mi), tzinfo=config.TZ)
    except ValueError:
        return None
    if not y and local < now_local:
        local = local.replace(year=year + 1)
    return local.astimezone(timezone.utc)


def to_local_str(utc_iso: str | None) -> str:
    if not utc_iso:
        return "—"
    return datetime.fromisoformat(utc_iso).astimezone(config.TZ).strftime("%d.%m.%Y %H:%M")


async def schedule_reminders(app_id: int, when_utc_iso: str | None) -> None:
    """Qabulga 1 kun va 2 soat qolganda eslatma rejalashtiradi."""
    await db.clear_reminders(app_id)
    if not when_utc_iso:
        return
    when = datetime.fromisoformat(when_utc_iso)
    now = datetime.now(timezone.utc)
    for delta, kind in ((timedelta(days=1), "day"), (timedelta(hours=2), "hour")):
        at = when - delta
        if at > now:
            await db.add_reminder(app_id, at.isoformat(timespec="seconds"), kind)


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            for r in await db.due_reminders():
                user = await db.get_user(r["tg_id"])
                lang = (user or {}).get("lang") or "uz"
                key = "p_rem_day" if r["kind"] == "day" else "p_rem_hour"
                try:
                    await bot.send_message(r["tg_id"], tr(lang, key, time=to_local_str(r["scheduled_at"])))
                except TelegramForbiddenError:
                    await db.update_user(r["tg_id"], blocked_bot=1)
                except Exception as e:  # noqa: BLE001
                    log.error("Eslatma yuborilmadi: %s", e)
                await db.mark_reminder_sent(r["rid"])
        except Exception as e:  # noqa: BLE001
            log.error("reminder_loop: %s", e)
        await asyncio.sleep(60)


# ------------------------------------------------------- ariza xabarlari (xodimlar uchun)
STATUS_UZ = {
    "new": "🆕 Yangi",
    "accepted": "✅ Qabul qilindi",
    "confirmed": "✅ Vaqt tasdiqlandi",
    "time_changed": "🕒 Vaqt o'zgartirildi, bemor javobi kutilmoqda",
    "rejected": "❌ Rad etildi",
}
STAGE_UZ = {"bleed": "Qon ketishi bor", "start": "Endi boshlangan", "unknown": "Aniq bilmayman"}


def user_link(a: dict, user: dict | None) -> str:
    uname = (user or {}).get("username")
    if uname:
        return f"@{html.escape(uname)}"
    return f'<a href="tg://user?id={a["tg_id"]}">profil</a> (id {a["tg_id"]})'


async def app_text(a: dict) -> str:
    user = await db.get_user(a["tg_id"])
    doctor = config.DOCTORS.get(a["doctor"], {}).get("name", "Farqi yo'q")
    lines = [
        f"📋 <b>Ariza #{a['id']}</b> — {STATUS_UZ.get(a['status'], a['status'])}",
        "",
        f"👤 {html.escape(a['name'] or '—')}",
        f"📞 {html.escape(a['phone'] or '—')}",
        f"🔗 {user_link(a, user)}",
        f"👨‍⚕️ {html.escape(doctor)}",
        f"🩺 {html.escape(STAGE_UZ.get(a['stage'], a['stage'] or '—'))}",
        f"🕒 {html.escape(a['wanted_time'] or '—')}",
        f"💰 {config.fmt_price(a['price'] or 0)} so'm"
        + (" (bot narxi)" if a.get("used_bonus") else "")
        + (f", do'st chegirmasi {a['ref_discount']}%" if a.get("ref_discount") else ""),
    ]
    if a["status"] in ("accepted", "confirmed"):
        lines.append("⏰ Eslatma: " + ("yoqilgan" if a.get("scheduled_at") else "yo'q (aniq vaqt: 🕒 tugmasi)"))
    if a.get("handled_by"):
        lines.append(f"🧑‍💼 Ko'rib chiqdi: {html.escape(a['handled_by'])}")
    return "\n".join(lines)


def app_kb(a: dict):
    i, st = a["id"], a["status"]
    rows = []
    if st == "new":
        rows.append([cb("✅ Qabul qilish", f"app:ok:{i}"), cb("❌ Rad etish", f"app:no:{i}")])
    if st != "rejected":
        rows.append([cb("🕒 Vaqtni o'zgartirish", f"app:time:{i}"), cb("👨‍⚕️ Shifokorni almashtirish", f"app:doc:{i}")])
    if st in ("accepted", "confirmed", "time_changed"):
        rows.append([cb("❌ Rad etish", f"app:no:{i}")])
    rows.append([cb("💬 Javob yozish", f"app:reply:{i}")])
    return kb(*rows)


def staff_chats() -> list[int]:
    return [config.ORDERS_CHAT_ID, *sorted(config.ADMINS)]


async def notify_new_app(bot: Bot, app_id: int) -> None:
    a = await db.get_appointment(app_id)
    text, markup = await app_text(a), app_kb(a)
    for chat in staff_chats():
        try:
            m = await bot.send_message(chat, text, reply_markup=markup)
            await db.add_app_msg(app_id, chat, m.message_id)
        except Exception as e:  # noqa: BLE001
            log.error("Ariza #%s %s ga yuborilmadi: %s (admin botga /start bosganmi?)", app_id, chat, e)


async def refresh_app_messages(bot: Bot, app_id: int) -> None:
    """Kanal va adminlardagi barcha nusxalarni yangi holat bilan yangilaydi."""
    a = await db.get_appointment(app_id)
    if not a:
        return
    text, markup = await app_text(a), app_kb(a)
    for m in await db.app_msgs(app_id):
        try:
            await bot.edit_message_text(text, chat_id=m["chat_id"], message_id=m["message_id"], reply_markup=markup)
        except TelegramBadRequest as e:
            if "not modified" not in str(e):
                log.warning("Yangilanmadi %s: %s", m, e)
        except Exception as e:  # noqa: BLE001
            log.warning("Yangilanmadi %s: %s", m, e)


async def notify_staff(bot: Bot, text: str, markup=None) -> list[tuple[int, int]]:
    sent = []
    for chat in staff_chats():
        try:
            m = await bot.send_message(chat, text, reply_markup=markup)
            sent.append((chat, m.message_id))
        except Exception as e:  # noqa: BLE001
            log.error("Xodimga yuborilmadi %s: %s", chat, e)
    return sent


async def safe_send(bot: Bot, chat_id: int, text: str, markup=None) -> bool:
    try:
        await bot.send_message(chat_id, text, reply_markup=markup)
        return True
    except TelegramForbiddenError:
        await db.update_user(chat_id, blocked_bot=1)
    except Exception as e:  # noqa: BLE001
        log.error("Foydalanuvchiga yuborilmadi %s: %s", chat_id, e)
    return False
