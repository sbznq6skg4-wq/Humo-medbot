"""Yaratuvchi (owner) uchun: texnik yordam/hamkorlik murojaatlari va tashxis buyruqlari.

Foydalanuvchi bosh menyudagi "🛠 Texnik yordam" tugmasini bosadi, murojaatini yozadi — u OWNER_ID ga boradi.
Owner tugma orqali javob yozadi, javob "Texnik yordam markazidan" nomidan foydalanuvchiga yetadi.

Owner buyruqlari:  /status  /aitest  /ttstest
"""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import config
import db
import actions
import services as sv
from keyboards import cb, kb
from texts import tr

router = Router()
log = logging.getLogger("humo")

SUPPORT_PENDING: set[int] = set()  # murojaat yozishi kutilayotgan foydalanuvchilar
OWNER_PENDING: dict[int, int] = {}  # owner -> javob beriladigan foydalanuvchi ID si


async def _lang(uid: int) -> str:
    u = await db.get_user(uid)
    return (u or {}).get("lang") or "uz"


# ------------------------------------------------------------ foydalanuvchi tomoni
@router.callback_query(F.data == "support_help")
async def support_start(c: CallbackQuery):
    await c.answer()
    SUPPORT_PENDING.add(c.from_user.id)
    await c.bot.send_message(c.message.chat.id, tr(await _lang(c.from_user.id), "sp_ask"))


def _support_pending(m: Message) -> bool:
    return bool(m.text) and not m.text.startswith("/") and m.from_user.id in SUPPORT_PENDING


@router.message(_support_pending)
async def support_message(m: Message, bot: Bot):
    SUPPORT_PENDING.discard(m.from_user.id)
    lang = await _lang(m.from_user.id)
    ok = await actions.send_support(bot, m.from_user.id, m.from_user.full_name, m.from_user.username, m.text)
    await m.answer(tr(lang, "sp_sent" if ok else "sp_err"))


# ------------------------------------------------------------ owner tomoni
@router.callback_query(F.data.startswith("reply_sup_"))
async def owner_reply_start(c: CallbackQuery):
    if c.from_user.id != config.OWNER_ID:
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    target = int(c.data.split("_")[2])
    OWNER_PENDING[c.from_user.id] = target
    await c.answer()
    await c.bot.send_message(c.from_user.id, f"✍️ Mijozga (ID: <code>{target}</code>) yuboriladigan javobni yozing.\nBekor qilish: /cancel")


def _owner_pending(m: Message) -> bool:
    return bool(m.text) and not m.text.startswith("/") and m.from_user.id in OWNER_PENDING


@router.message(_owner_pending)
async def owner_reply_send(m: Message, bot: Bot):
    target = OWNER_PENDING.pop(m.from_user.id)
    lang = await _lang(target)
    ok = await sv.safe_send(bot, target, tr(lang, "sp_from", text=html.escape(m.text.strip())),
                            kb([cb(tr(lang, "sp_reply"), "support_help")]))
    await m.answer("✅ Javob mijozga yetkazildi!" if ok else "❌ Mijozga xabar ketmadi (botni bloklagan bo'lishi mumkin).")


@router.message(Command("cancel"), F.from_user.id == config.OWNER_ID)
async def owner_cancel(m: Message):
    OWNER_PENDING.pop(m.from_user.id, None)
    SUPPORT_PENDING.discard(m.from_user.id)
    # handlers_admin dagi /cancel ham ishlashi uchun hodisani to'xtatmaymiz
    from handlers_admin import ADMIN_PENDING
    ADMIN_PENDING.pop(m.from_user.id, None)
    await m.answer("Bekor qilindi.")


# ------------------------------------------------------------ tashxis buyruqlari (faqat owner)
@router.message(Command("status"), F.from_user.id == config.OWNER_ID)
async def cmd_status(m: Message):
    s = await db.stats()
    yes = lambda v: "✅" if v else "❌"  # noqa: E731
    await m.answer(
        "🩺 <b>Bot holati</b>\n\n"
        f"👥 Foydalanuvchilar: {s['users']} · 📋 Arizalar: {s['apps_total']} · ❓ AI savollar: {s['questions']}\n"
        f"{yes(config.BOT_TOKEN)} BOT_TOKEN\n{yes(config.GEMINI_API_KEY)} GEMINI_API_KEY (model: <code>{html.escape(config.GEMINI_MODEL)}</code>)\n"
        f"{yes(config.ELEVEN_API_KEY)} ELEVENLABS_API_KEY (model: <code>{html.escape(config.ELEVEN_MODEL)}</code>)\n"
        f"Ishlayotgan Gemini yo'li: {html.escape(sv.GEMINI_WORKING or 'hali sinalmagan, /aitest ni bosing')}\n"
        f"Baza: <code>{html.escape(config.DB_PATH)}</code>\n"
        f"ish jarayoni videosi ID: {yes(config.MEDIA.get('work_video'))}")


@router.message(Command("aitest"), F.from_user.id == config.OWNER_ID)
async def cmd_aitest(m: Message):
    await m.answer("⏳ Gemini tekshirilmoqda...")
    try:
        answer = await sv.ask_gemini([], "Salom! Humo Med klinikasi haqida bir jumla ayt.")
    except Exception as e:  # noqa: BLE001
        await m.answer(f"❌ Gemini ishlamadi:\n<code>{html.escape(str(e)[:3500])}</code>")
        return
    await m.answer(f"✅ Gemini ishladi ({html.escape(sv.GEMINI_WORKING or '?')}):\n\n{html.escape(answer[:1500])}")


@router.message(Command("ttstest"), F.from_user.id == config.OWNER_ID)
async def cmd_ttstest(m: Message, bot: Bot):
    await m.answer("⏳ ElevenLabs tekshirilmoqda...")
    try:
        audio = await sv.eleven_tts("Assalomu alaykum! Humo Med klinikasiga xush kelibsiz.")
    except Exception as e:  # noqa: BLE001
        await m.answer(f"❌ ElevenLabs ishlamadi:\n<code>{html.escape(str(e)[:3500])}</code>")
        return
    await bot.send_audio(m.chat.id, BufferedInputFile(audio, filename="test.mp3"), title="Humo Med test")
