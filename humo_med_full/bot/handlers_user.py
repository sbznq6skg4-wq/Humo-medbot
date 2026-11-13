"""Foydalanuvchi tomoni: start, til, menyu, palatalar, shifokorlar, qabulga yozilish,
qo'ng'iroq so'rovi, AI maslahatchi, ovozli javob, do'st taklifi."""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BufferedInputFile, CallbackQuery, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)

import config
import db
import actions
import services as sv
from gate import is_member
from keyboards import (about_kb, back_kb, book_back_kb, cb, doctor_pick_kb, hem_kb, kb, lang_kb,
                       main_menu, stage_kb, url_btn, wards_kb)
from owner import SUPPORT_PENDING
from texts import tr

router = Router()
log = logging.getLogger("humo")

PATIENT_PENDING: dict[int, tuple[str, int]] = {}  # bemor yozishi kutilayotgan holatlar
HISTORY: dict[int, list[dict]] = {}  # AI suhbat tarixi (xotirada)


# ------------------------------------------------------------ yordamchilar
def guess_lang(code: str | None) -> str:
    code = (code or "")[:2]
    return code if code in ("ru", "en") else "uz"


async def lang_of(uid: int) -> str:
    u = await db.get_user(uid)
    return (u or {}).get("lang") or "uz"


async def ctx(c: CallbackQuery):
    """Callback uchun: (bot, chat_id, til). Yuklanish belgisini ham o'chiradi."""
    await c.answer()
    return c.bot, c.message.chat.id, await lang_of(c.from_user.id)


async def ask_contact(bot: Bot, chat_id: int, lang: str) -> None:
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=tr(lang, "btn_contact"), request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)
    await bot.send_message(chat_id, tr(lang, "ask_contact"), reply_markup=markup)


async def show_menu(bot: Bot, chat_id: int, lang: str) -> None:
    await bot.send_message(chat_id, tr(lang, "menu_title"), reply_markup=main_menu(lang, admin=chat_id in config.ADMINS))


# ------------------------------------------------------- /start, /menu, kontakt
@router.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject, state: FSMContext, bot: Bot):
    await state.clear()
    uid = m.from_user.id
    PATIENT_PENDING.pop(uid, None)
    SUPPORT_PENDING.discard(uid)
    ref = None
    if command.args and command.args.startswith("ref"):
        try:
            ref = int(command.args[3:])
        except ValueError:
            ref = None
    await db.upsert_user(uid, m.from_user.username, m.from_user.full_name, ref)
    u = await db.get_user(uid)
    if not u["phone"]:
        await ask_contact(bot, m.chat.id, u["lang"] or guess_lang(m.from_user.language_code))
    elif not u["lang"]:
        await m.answer(tr("uz", "choose_lang"), reply_markup=lang_kb())
    else:
        await show_menu(bot, m.chat.id, u["lang"])


@router.message(Command("menu"))
async def cmd_menu(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    PATIENT_PENDING.pop(m.from_user.id, None)
    SUPPORT_PENDING.discard(m.from_user.id)
    await show_menu(bot, m.chat.id, await lang_of(m.from_user.id))


@router.message(F.contact)
async def got_contact(m: Message, bot: Bot):
    uid = m.from_user.id
    lang = await lang_of(uid)
    if m.contact.user_id != uid:
        await m.answer(tr(lang, "contact_wrong"))
        return
    phone = m.contact.phone_number
    await db.update_user(uid, phone=phone if phone.startswith("+") else "+" + phone)
    await m.answer(tr(lang, "thanks"), reply_markup=ReplyKeyboardRemove())
    u = await db.get_user(uid)
    if u["lang"]:
        await show_menu(bot, m.chat.id, u["lang"])
    else:
        await m.answer(tr("uz", "choose_lang"), reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def choose_lang(c: CallbackQuery):
    await c.answer()
    bot, chat, uid = c.bot, c.message.chat.id, c.from_user.id
    lang = c.data.split(":")[1]
    await db.update_user(uid, lang=lang)
    u = await db.get_user(uid)
    if not u["intro_sent"]:  # "Humo Med haqida" videosi faqat birinchi marta avtomatik chiqadi
        await sv.send_media(bot, chat, "intro_video", tr(lang, "intro_caption"))
        await db.update_user(uid, intro_sent=1)
    await show_menu(bot, chat, lang)


@router.callback_query(F.data == "menu:lang")
async def menu_lang(c: CallbackQuery):
    bot, chat, _ = await ctx(c)
    await bot.send_message(chat, tr("uz", "choose_lang"), reply_markup=lang_kb())


@router.callback_query(F.data == "menu:main")
async def menu_main(c: CallbackQuery, state: FSMContext):
    bot, chat, lang = await ctx(c)
    await state.clear()
    await show_menu(bot, chat, lang)


@router.callback_query(F.data == "sub:check")
async def sub_check(c: CallbackQuery):
    channel = await db.get_setting("sub_channel")
    if channel and not await is_member(c.bot, int(channel), c.from_user.id):
        await c.answer(tr(await lang_of(c.from_user.id), "sub_fail"), show_alert=True)
        return
    bot, chat, lang = await ctx(c)
    await show_menu(bot, chat, lang)


# ------------------------------------------------------------ shifokorlar
@router.callback_query(F.data == "menu:doctors")
async def menu_doctors(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    for key, d in config.DOCTORS.items():
        await sv.send_album(bot, chat, d["photos"], tr(lang, f"doc_{key}"))
    await bot.send_message(chat, "👇", reply_markup=book_back_kb(lang))


# ------------------------------------------------------------ palatalar
def wards_back(lang: str):
    return kb([cb(tr(lang, "m_book"), "book")], [cb(tr(lang, "m_wards"), "menu:wards")], [cb(tr(lang, "back"), "menu:main")])


@router.callback_query(F.data == "menu:wards")
async def menu_wards(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await bot.send_message(chat, tr(lang, "wards_title"), reply_markup=wards_kb(lang))


@router.callback_query(F.data == "ward:normal")
async def ward_normal(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_media(bot, chat, "ward_normal_photo", tr(lang, "wc_normal"))
    await sv.send_media(bot, chat, "ward_normal_video", markup=wards_back(lang))


@router.callback_query(F.data == "ward:lux2")
async def ward_lux2(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_media(bot, chat, "ward_lux2_photo", tr(lang, "wc_lux2"))
    await sv.send_media(bot, chat, "ward_lux_video")
    await sv.send_media(bot, chat, "ward_bath_video", tr(lang, "wc_bath"), wards_back(lang))


@router.callback_query(F.data == "ward:lux3")
async def ward_lux3(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_media(bot, chat, "ward_lux3_video_1", tr(lang, "wc_lux3"))
    await sv.send_media(bot, chat, "ward_lux3_video_2")
    await sv.send_media(bot, chat, "ward_bath_video", tr(lang, "wc_bath"), wards_back(lang))


# ------------------------------------------------------------ klinika haqida
def about_back(lang: str):
    return kb([cb(tr(lang, "m_about"), "menu:about")], [cb(tr(lang, "back"), "menu:main")])


@router.callback_query(F.data == "menu:about")
async def menu_about(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await bot.send_message(chat, tr(lang, "about_text"), reply_markup=about_kb(lang))


@router.callback_query(F.data == "about:work")
async def about_work(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_album(bot, chat, ["work_photo_1", "work_photo_2"], tr(lang, "cap_work"))
    await sv.send_media(bot, chat, "work_video", markup=about_back(lang))


@router.callback_query(F.data == "about:laser")
async def about_laser(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_media(bot, chat, "laser_photo", tr(lang, "cap_laser"))
    await sv.send_media(bot, chat, "laser_video_1")
    await sv.send_media(bot, chat, "laser_video_2", markup=about_back(lang))


@router.callback_query(F.data == "about:certs")
async def about_certs(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_album(bot, chat, ["cert_1", "cert_2"], tr(lang, "cap_certs"))
    await bot.send_message(chat, "👇", reply_markup=about_back(lang))


@router.callback_query(F.data == "about:patients")
async def about_patients(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_media(bot, chat, "patients_video", tr(lang, "cap_patients"), about_back(lang))


@router.callback_query(F.data == "about:reception")
async def about_reception(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_album(bot, chat, ["reception_1", "reception_2"], tr(lang, "cap_reception"))
    await bot.send_message(chat, "👇", reply_markup=about_back(lang))


# ------------------------------------------------------------ gemorroy + mini-test
@router.callback_query(F.data == "menu:hem")
async def menu_hem(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await sv.send_media(bot, chat, "hemorrhoid_1")
    await sv.send_media(bot, chat, "hemorrhoid_2")
    await bot.send_message(chat, tr(lang, "hem_q"), reply_markup=hem_kb(lang))


@router.callback_query(F.data.startswith("hem:"))
async def hem_result(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    key = c.data.split(":")[1]
    await bot.send_message(chat, tr(lang, f"hr_{key}"), reply_markup=book_back_kb(lang))


# ------------------------------------------------------------ manzil, qo'ng'iroq, sayt, FAQ, taklif
@router.callback_query(F.data == "menu:loc")
async def menu_loc(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    markup = kb([url_btn(tr(lang, "loc_btn"), config.MAP_URL)], [cb(tr(lang, "back"), "menu:main")])
    await sv.send_media(bot, chat, "location_video", tr(lang, "loc_caption"), markup)


@router.callback_query(F.data == "menu:call")
async def menu_call(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await bot.send_contact(chat, phone_number=config.CLINIC_PHONE, first_name="Humo Med")
    await bot.send_message(chat, tr(lang, "call_text"),
                           reply_markup=kb([cb(tr(lang, "c_req"), "call:req")], [cb(tr(lang, "back"), "menu:main")]))


@router.callback_query(F.data == "call:req")
async def call_request(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    status, _ = await actions.create_callback_request(bot, c.from_user.id)
    if status == "nophone":
        await ask_contact(bot, chat, lang)
    elif status == "dup":
        await bot.send_message(chat, tr(lang, "c_dup"), reply_markup=back_kb(lang))
    else:
        u = await db.get_user(c.from_user.id)
        await bot.send_message(chat, tr(lang, "c_ok", phone_user=u["phone"]), reply_markup=back_kb(lang))


@router.callback_query(F.data == "menu:faq")
async def menu_faq(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    await bot.send_message(chat, tr(lang, "faq"), reply_markup=book_back_kb(lang))


@router.callback_query(F.data == "menu:ref")
async def menu_ref(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    uid = c.from_user.id
    count = await db.ref_count(uid)
    disc = min(count * config.REF_DISCOUNT_PER_FRIEND, config.MAX_REF_DISCOUNT)
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref{uid}"
    await bot.send_message(chat, tr(lang, "ref_text", link=link, count=count, disc=disc), reply_markup=back_kb(lang))


# ------------------------------------------------------------ qabulga yozilish
class Book(StatesGroup):
    name = State()
    doctor = State()
    stage = State()
    time = State()


@router.callback_query(F.data == "book")
async def book_start(c: CallbackQuery, state: FSMContext):
    bot, chat, lang = await ctx(c)
    u = await db.get_user(c.from_user.id)
    if not u or not u["phone"]:
        await ask_contact(bot, chat, lang)
        return
    await state.clear()
    await state.set_state(Book.name)
    await bot.send_message(chat, tr(lang, "b_name"))


@router.message(Book.name, F.text)
async def book_name(m: Message, state: FSMContext):
    lang = await lang_of(m.from_user.id)
    await state.update_data(name=m.text.strip()[:80])
    await state.set_state(Book.doctor)
    await m.answer(tr(lang, "b_doctor"), reply_markup=doctor_pick_kb(lang))


@router.callback_query(Book.doctor, F.data.startswith("bdoc:"))
async def book_doctor(c: CallbackQuery, state: FSMContext):
    bot, chat, lang = await ctx(c)
    key = c.data.split(":")[1]
    await state.update_data(doctor=key if key in config.DOCTORS else None)
    await state.set_state(Book.stage)
    await bot.send_message(chat, tr(lang, "b_stage"), reply_markup=stage_kb(lang))


@router.callback_query(Book.stage, F.data.startswith("bstage:"))
async def book_stage(c: CallbackQuery, state: FSMContext):
    bot, chat, lang = await ctx(c)
    await state.update_data(stage=c.data.split(":")[1])
    await state.set_state(Book.time)
    await bot.send_message(chat, tr(lang, "b_time"))


@router.message(Book.time, F.text)
async def book_time(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    uid = m.from_user.id
    lang = await lang_of(uid)
    ok, res = await actions.create_booking(bot, uid, data.get("name"), data.get("doctor"), data.get("stage"), m.text)
    if not ok:
        await m.answer(tr(lang, "ai_error"))
        return
    note = (tr(lang, "b_note_bonus") if res["used_bonus"] else "") + (tr(lang, "b_note_ref", disc=res["refs"]) if res["refs"] else "")
    await m.answer(tr(lang, "b_done", id=res["id"], time=html.escape(m.text.strip()[:100]), doctor=res["doctor"],
                      price=config.fmt_price(res["price"]), note=note), reply_markup=main_menu(lang, admin=uid in config.ADMINS))


# ------------------------------------------------------------ bemorning javoblari (vaqt, xabar)
@router.callback_query(F.data.startswith("tconf:"))
async def time_confirm(c: CallbackQuery, bot: Bot):
    _, aid, ans = c.data.split(":")
    aid = int(aid)
    a = await db.get_appointment(aid)
    uid = c.from_user.id
    if not a or a["tg_id"] != uid or a["status"] != "time_changed":
        await c.answer()
        return
    lang = await lang_of(uid)
    await c.answer()
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    if ans == "yes":
        await db.update_appointment(aid, status="confirmed")
        await sv.schedule_reminders(aid, a["scheduled_at"])
        await bot.send_message(uid, tr(lang, "p_time_ok", time=html.escape(a["wanted_time"] or "")))
        await sv.refresh_app_messages(bot, aid)
    else:
        PATIENT_PENDING[uid] = ("newtime", aid)
        await bot.send_message(uid, tr(lang, "p_newtime_ask"))


@router.callback_query(F.data.startswith("preply:"))
async def patient_reply_start(c: CallbackQuery):
    aid = int(c.data.split(":")[1])
    a = await db.get_appointment(aid)
    if not a or a["tg_id"] != c.from_user.id:
        await c.answer()
        return
    bot, chat, lang = await ctx(c)
    PATIENT_PENDING[c.from_user.id] = ("reply", aid)
    await bot.send_message(chat, tr(lang, "r_ask"))


def _patient_pending(m: Message) -> bool:
    return bool(m.text) and not m.text.startswith("/") and m.from_user.id in PATIENT_PENDING


@router.message(_patient_pending)
async def patient_text(m: Message, bot: Bot):
    uid = m.from_user.id
    kind, aid = PATIENT_PENDING.pop(uid)
    a = await db.get_appointment(aid)
    lang = await lang_of(uid)
    if not a:
        return
    text = m.text.strip()[:500]
    if kind == "reply":
        await sv.notify_staff(
            bot, f"💬 <b>Bemordan</b> (ariza #{aid}, {html.escape(a['name'] or '—')}):\n{html.escape(text)}",
            kb([cb("💬 Javob yozish", f"app:reply:{aid}")]))
        await m.answer(tr(lang, "r_sent"))
        return
    dt = sv.parse_dt(text)
    await db.update_appointment(aid, wanted_time=text[:100], status="new", handled_by=None,
                                scheduled_at=dt.isoformat(timespec="seconds") if dt else None)
    await db.clear_reminders(aid)
    await sv.refresh_app_messages(bot, aid)
    await sv.notify_staff(bot, f"🔁 Bemor boshqa vaqt so'radi (ariza #{aid}): <b>{html.escape(text)}</b>",
                          kb([cb("💬 Javob yozish", f"app:reply:{aid}")]))
    await m.answer(tr(lang, "p_newtime_sent"))


# ------------------------------------------------------------ AI maslahatchi
class AI(StatesGroup):
    chat = State()


@router.callback_query(F.data == "menu:ai")
async def ai_start(c: CallbackQuery, state: FSMContext):
    bot, chat, lang = await ctx(c)
    if await db.get_setting("ai_enabled", "1") != "1" or not config.GEMINI_API_KEY:
        await bot.send_message(chat, tr(lang, "ai_off"), reply_markup=back_kb(lang))
        return
    await state.set_state(AI.chat)
    await bot.send_message(chat, tr(lang, "ai_intro"), reply_markup=kb([cb(tr(lang, "ai_exit_btn"), "ai:exit")]))


@router.callback_query(F.data == "ai:exit")
async def ai_exit(c: CallbackQuery, state: FSMContext):
    bot, chat, lang = await ctx(c)
    await state.clear()
    await show_menu(bot, chat, lang)


@router.message(AI.chat, F.text)
async def ai_message(m: Message, state: FSMContext, bot: Bot):
    uid = m.from_user.id
    lang = await lang_of(uid)
    if await db.get_setting("ai_enabled", "1") != "1":
        await state.clear()
        await m.answer(tr(lang, "ai_off"), reply_markup=back_kb(lang))
        return
    if not sv.AI_LIMIT.allow(uid):
        await m.answer(tr(lang, "ai_limit"))
        return
    text = m.text.strip()[:1000]
    await bot.send_chat_action(m.chat.id, "typing")
    qid = await db.add_question(uid, text)
    hist = HISTORY.setdefault(uid, [])
    try:
        answer = await sv.ask_gemini(hist[-8:], text)
    except Exception as e:  # noqa: BLE001
        log.error("Gemini xatosi: %s", e)
        await sv.notify_owner(bot, "Gemini xatosi", str(e))
        detail = f"\n\n<code>{html.escape(str(e)[:700])}</code>" if uid in config.ADMINS else ""
        await m.answer(tr(lang, "ai_error") + detail)
        return
    hist.extend([{"role": "user", "parts": [{"text": text}]}, {"role": "model", "parts": [{"text": answer}]}])
    HISTORY[uid] = hist[-10:]
    await db.update_question(qid, answer=answer)
    rows = []
    if config.ELEVEN_API_KEY:
        rows.append([cb(tr(lang, "tts_btn"), f"tts:{qid}")])
    rows.append([cb(tr(lang, "m_book"), "book")])
    rows.append([cb(tr(lang, "ai_exit_btn"), "ai:exit")])
    await m.answer(html.escape(answer[:3500]), reply_markup=kb(*rows))


@router.callback_query(F.data.startswith("tts:"))
async def tts_callback(c: CallbackQuery):
    bot, chat, lang = await ctx(c)
    uid = c.from_user.id
    q = await db.get_question(int(c.data.split(":")[1]))
    if not q or q["tg_id"] != uid or not q["answer"]:
        return
    if q["audio_file_id"]:  # avval yaratilgan ovoz — qayta pul to'lamaymiz
        await bot.send_audio(chat, q["audio_file_id"])
        return
    if not sv.TTS_LIMIT.allow(uid):
        await bot.send_message(chat, tr(lang, "tts_limit"))
        return
    await bot.send_chat_action(chat, "record_voice")
    try:
        audio = await sv.eleven_tts(sv.clean_for_tts(q["answer"]))
    except Exception as e:  # noqa: BLE001
        log.error("ElevenLabs xatosi: %s", e)
        await sv.notify_owner(bot, "ElevenLabs xatosi", str(e))
        detail = f"\n\n<code>{html.escape(str(e)[:500])}</code>" if uid in config.ADMINS else ""
        await bot.send_message(chat, tr(lang, "tts_error") + detail)
        return
    msg = await bot.send_audio(chat, BufferedInputFile(audio, filename="humo_med.mp3"), title="Humo Med")
    if msg.audio:
        await db.update_question(q["id"], audio_file_id=msg.audio.file_id)


# ------------------------------------------------------------ boshqa matnlar
@router.message(F.text)
async def fallback(m: Message, bot: Bot):
    u = await db.get_user(m.from_user.id)
    if not u or not u["phone"]:
        await ask_contact(bot, m.chat.id, guess_lang(m.from_user.language_code))
        return
    lang = u["lang"] or "uz"
    await m.answer(tr(lang, "fallback"), reply_markup=main_menu(lang, admin=m.from_user.id in config.ADMINS))
