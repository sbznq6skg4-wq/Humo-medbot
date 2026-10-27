"""
Humo Med — TEST bot (Aiogram 3.x)
Maqsad: file_id lar to'g'ri ishlashini, menyu va qabul oqimini tekshirish.

Ishga tushirish:
    pip install -r requirements.txt
    .env faylga BOT_TOKEN yozing (.env.example ga qarang)
    python test_bot.py

Test buyruqlari:
    /start        — to'liq oqim (kontakt -> til -> kirish videosi -> menyu)
    /test_media   — (faqat admin) barcha media ID larni birma-bir yuborib, xatolarini ko'rsatadi
    Admin botga rasm/video yuborsa — bot uning file_id sini qaytaradi
"""
import asyncio
import logging
import os
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from dotenv import load_dotenv

load_dotenv()

# ======================= SOZLAMALAR =======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # sayt tayyor bo'lganda .env ga yozasiz (https://...)
ADMINS = {8196942761, 663593026}
ORDERS_CHAT_ID = -1004466442357  # qabullar boradigan kanal/guruh
CLINIC_PHONE = "+998979921111"  # TEKSHIRING: 979921111 raqami +998 bilan yozildi
MAP_URL = "https://maps.app.goo.gl/DhSA68hzcFURT8Hx6?g_st=ic"

PRICE_NORMAL = "70 000"
PRICE_BOT = "50 000"

# ======================= MEDIA (file_id) =======================
# "BAAC..." bilan boshlansa — video, "AgAC..." bilan boshlansa — rasm (avtomatik aniqlanadi)
MEDIA = {
    "intro_video": "BAACAgIAAxkBAAMUatoq6czKj2y4lhz-7vkwma6mszcAAlCoAAIcrthKQyzOA3DQknI9BA",
    "location_video": "BAACAgIAAxkBAAMWatorBfi345N7z4IldNjbqT4kjigAAlyoAAIcrthKEgyGhJAf3eA9BA",
    "extra_video_AAMM": "BAACAgIAAxkBAAMMatoqnuTvZJaXFRoEoqmbKJ9Ti3AAAjyoAAIcrthK1rtwOZNcgy49BA",
    "doctor_hasan": "AgACAgIAAxkBAAMcauD5aMYAAX8Ge1uPDjBO-xgFrZkUAAJyJWsbZygJSw7qKYIyPvXNAQADAgADeQADPQQ",
    "doctor_zuhriddin": "AgACAgIAAxkBAAMaauD5ZLz-YLWoqL1VGutAx4-kLesAAnAlaxtnKAlL2agHXmfmbecBAAMCAAN4AAM9BA",
    "certificates": "AgACAgIAAxkBAAMsatoxL0QvTWnvtyettY8Lh1lbs9EAAsYgaxtgKdBKPApuiEZDi4cBAAMCAAN3AAM9BA",
    "surgery_photo": "AgACAgIAAxkBAAMqatoww-tDc6nHNM5YaKlO38XhPgoAAnghaxtittFKWlRCVzSJ4LUBAAMCAAN3AAM9BA",
    "work_video": "BAACAgIAAxkBAAMiatovbTL7vQHU_Ovuj9zC619-9AoAAvmtAAJittFK9KQZ9pOFeSE9BA",
    "patients_video": "BAACAgIAAxkBAAMmatowaZl_RBzpcGg7LauU57t8DkQAAvWoAAIcrthKV4y1hoi1_kg9BA",
    "hemorrhoid_1": "BAACAgIAAxkBAAMgatovP-exDO-gc_ywUb3-POwAAbceAAL2rQACYrbRSnIVT8N3ITDpPQQ",
    "hemorrhoid_2": "BAACAgIAAxkBAAMaatot825AQb5K92VBaSkAAa8TeIK0AALnrQACYrbRSjPJvgnnHPCnPQQ",
    "laser_video_1": "BAACAgIAAxkBAAMKatoqimDCtgYhIMqx2k7ubus2YT0AAkGoAAIcrthKkZF_VOm29r89BA",
    "laser_video_2": "BAACAgIAAxkBAAMeauEAAcrVwl70Utjcnf-5dtYYPE6uAAK9rwACZygJSxveoS0BTAWXPQQ",
    "laser_photo": "AgACAgIAAxkBAAMgauEDa9NJexCPkeHJr3xgUyUG0eEAAqwlaxtnKAlLUzJPiFS35_EBAAMCAAN3AAM9BA",
    "ward_normal_video": "BAACAgIAAxkBAAMWauD5J6YoltiURR3E3gO-Y_mQHzkAAnevAAJnKAlLGczRX0RrfSo9BA",
    "ward_normal_photo": "AgACAgIAAxkBAAMiauEGZ8QixIoj-QplLOmHV5DuWIAAAsUlaxtnKAlLoTsP_gABzyGZAQADAgADdwADPQQ",
    "ward_lux2_video": "BAACAgIAAxkBAAMYauD5OHbPbhlXWLXpGN0rRe-gU5EAAnivAAJnKAlLjNRkdvfvT809BA",
    "ward_lux2_photo": "AgACAgIAAxkBAAMkauEKmcQ5LyCIfG669Qrt7VrEha4AAtUlaxtnKAlLqkqJyCX7XbgBAAMCAAN3AAM9BA",
    "ward_lux3_video": "BAACAgIAAxkBAAMUauD5DCKZJ2jHasn1geg4ahLBCf8AAnWvAAJnKAlLBJs2Gvw2g249BA",
    "ward_lux3_photo": "AgACAgIAAxkBAAMmauELbFeX2mzyi6WTid-XVfntZ6cAAtolaxtnKAlLDEVAnA4jMIQBAAMCAAN3AAM9BA",
    "ward_bathroom": "AgACAgIAAxkBAAMoauEMFpJz5QO4YmkS9XQ8NPmBQycAAtslaxtnKAlL3H8IhT-sld8BAAMCAAN3AAM9BA",
    "logo": "AgACAgIAAxkBAAMqauEMn3Ey7Lh2_lJnD4RMkUaQATgAAuAlaxtnKAlLY8tvNFkMwToBAAMCAAN4AAM9BA",
}

router = Router()
USERS: dict[int, dict] = {}  # TEST uchun xotirada; asl botda bazaga yoziladi


# ======================= YORDAMCHI FUNKSIYALAR =======================
def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """rows: [[(matn, callback_data), ...], ...]"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
        ]
    )


def back_kb() -> InlineKeyboardMarkup:
    return kb([[("⬅️ Bosh menyu", "menu:main")]])


async def send_media(target: Message, key: str, caption: str | None = None, markup=None) -> bool:
    """file_id ni yuboradi. Xato bo'lsa matn bilan ogohlantiradi va False qaytaradi."""
    fid = MEDIA[key]
    try:
        if fid.startswith("BAAC"):
            await target.answer_video(fid, caption=caption, reply_markup=markup)
        else:
            await target.answer_photo(fid, caption=caption, reply_markup=markup)
        return True
    except TelegramBadRequest as e:
        logging.error("MEDIA XATO [%s]: %s", key, e)
        await target.answer(f"⚠️ Media yuborilmadi: <code>{key}</code>\n{caption or ''}", reply_markup=markup)
        return False


def main_menu() -> InlineKeyboardMarkup:
    return kb(
        [
            [("📅 Qabulga yozilish", "book")],
            [("🩺 Shifokorlar", "menu:doctors"), ("🛏 Palatalar", "menu:wards")],
            [("🏥 Klinika haqida", "menu:about"), ("📘 Gemorroy haqida", "menu:hemorrhoid")],
            [("📍 Manzil", "menu:location"), ("📞 Qo'ng'iroq", "menu:call")],
            [("🌐 Veb-sayt", "menu:web"), ("❓ Savol-javob", "menu:faq")],
            [("🌍 Tilni o'zgartirish", "menu:lang")],
        ]
    )


def lang_kb() -> InlineKeyboardMarkup:
    return kb([[("🇺🇿 O'zbekcha", "lang:uz"), ("🇷🇺 Русский", "lang:ru"), ("🇬🇧 English", "lang:en")]])


# ======================= /start, KONTAKT, TIL =======================
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    if m.from_user.id in USERS and USERS[m.from_user.id].get("phone"):
        await m.answer("Tilni tanlang / Выберите язык / Choose language:", reply_markup=lang_kb())
        return
    kb_contact = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await m.answer(
        "Assalomu alaykum! 👋\n<b>Humo Med</b> klinikasi botiga xush kelibsiz.\n\n"
        "Davom etish uchun pastdagi tugma orqali telefon raqamingizni yuboring.",
        reply_markup=kb_contact,
    )


@router.message(F.contact)
async def got_contact(m: Message):
    if m.contact.user_id != m.from_user.id:
        await m.answer("Iltimos, o'zingizning raqamingizni tugma orqali yuboring.")
        return
    USERS[m.from_user.id] = {"phone": m.contact.phone_number, "lang": "uz"}
    await m.answer("✅ Rahmat!", reply_markup=ReplyKeyboardRemove())
    await m.answer("Tilni tanlang / Выберите язык / Choose language:", reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def choose_lang(cb: CallbackQuery):
    await cb.answer()
    USERS.setdefault(cb.from_user.id, {})["lang"] = cb.data.split(":")[1]
    # TEST: hozircha barcha matnlar o'zbekcha. Asl botda 3 tilda bo'ladi.
    await send_media(
        cb.message,
        "intro_video",
        caption="🏥 <b>Humo Med</b> — 8 yillik tajriba, 24/7 xizmat.",
    )
    await cb.message.answer("🏠 Bosh menyu", reply_markup=main_menu())


@router.callback_query(F.data == "menu:lang")
async def menu_lang(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("Tilni tanlang / Выберите язык / Choose language:", reply_markup=lang_kb())


@router.callback_query(F.data == "menu:main")
async def menu_main(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("🏠 Bosh menyu", reply_markup=main_menu())


# ======================= PALATALAR =======================
@router.callback_query(F.data == "menu:wards")
async def menu_wards(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🛏 <b>Palatalar</b>\nQaysi turini ko'rmoqchisiz?",
        reply_markup=kb(
            [
                [("🛏 Oddiy palata — 200 000", "ward:normal")],
                [("⭐ Lyuks 2 kishilik — 250 000", "ward:lux2")],
                [("⭐ Lyuks 3 kishilik — 250 000", "ward:lux3")],
                [("⬅️ Bosh menyu", "menu:main")],
            ]
        ),
    )


@router.callback_query(F.data == "ward:normal")
async def ward_normal(cb: CallbackQuery):
    await cb.answer()
    await send_media(
        cb.message, "ward_normal_photo",
        "🛏 <b>Oddiy palata</b>\n👥 2–4 kishilik\n📶 Wi-Fi, 📺 TV\n💰 Narxi: <b>200 000 so'm</b>\n🍽 3 mahal parhez ovqat",
    )
    await send_media(cb.message, "ward_normal_video", markup=kb([[("📅 Qabulga yozilish", "book")], [("⬅️ Palatalar", "menu:wards")]]))


@router.callback_query(F.data == "ward:lux2")
async def ward_lux2(cb: CallbackQuery):
    await cb.answer()
    await send_media(
        cb.message, "ward_lux2_photo",
        "⭐ <b>Lyuks palata (2 kishilik)</b>\n📶 Wi-Fi, 📺 TV, 🚿 shaxsiy hammom\n💰 Narxi: <b>250 000 so'm</b>\n🍽 3 mahal parhez ovqat",
    )
    await send_media(cb.message, "ward_bathroom", "🚿 Hammom")
    await send_media(cb.message, "ward_lux2_video", markup=kb([[("📅 Qabulga yozilish", "book")], [("⬅️ Palatalar", "menu:wards")]]))


@router.callback_query(F.data == "ward:lux3")
async def ward_lux3(cb: CallbackQuery):
    await cb.answer()
    await send_media(
        cb.message, "ward_lux3_photo",
        "⭐ <b>Lyuks palata (3 kishilik)</b>\n📶 Wi-Fi, 📺 TV, ❄️ konditsioner, 🚿 shaxsiy hammom\n💰 Narxi: <b>250 000 so'm</b>\n🍽 3 mahal parhez ovqat",
    )
    await send_media(cb.message, "ward_bathroom", "🚿 Hammom")
    await send_media(cb.message, "ward_lux3_video", markup=kb([[("📅 Qabulga yozilish", "book")], [("⬅️ Palatalar", "menu:wards")]]))


# ======================= SHIFOKORLAR =======================
@router.callback_query(F.data == "menu:doctors")
async def menu_doctors(cb: CallbackQuery):
    await cb.answer()
    await send_media(
        cb.message, "doctor_hasan",
        "👨‍⚕️ <b>Sulaymonov Hasanjon Tohirjonovich</b>\n📅 1992 yil\n🏅 7 yillik tajriba\n🩺 Proktolog\n"
        "🌍 Rossiya, Turkiya, Ozarbayjon va Qozog'iston davlatlarida malaka oshirgan",
    )
    await send_media(
        cb.message, "doctor_zuhriddin",
        "👨‍⚕️ <b>Xolikov Zuhriddin Muhiddin o'g'li</b>\n📅 1995 yil\n🏅 4 yillik tajriba",
        markup=kb([[("📅 Qabulga yozilish", "book")], [("⬅️ Bosh menyu", "menu:main")]]),
    )


# ======================= KLINIKA HAQIDA =======================
@router.callback_query(F.data == "menu:about")
async def menu_about(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "🏥 <b>Humo Med</b>\n\n✅ 8 yillik tajriba\n✅ 24/7 ishlaydi, dam olish kunisiz\n"
        "✅ Bemorlar uchun 3 mahal mazali va parhez ovqat\n"
        f"✅ Konsultatsiya: {PRICE_NORMAL} so'm (bot orqali yozilsangiz — <b>{PRICE_BOT} so'm</b>)",
        reply_markup=kb(
            [
                [("⚙️ Ish jarayoni", "about:work"), ("🔬 Lazer xonasi", "about:laser")],
                [("🏆 Sertifikatlar", "about:certs"), ("❤️ Bemorlar fikri", "about:patients")],
                [("⬅️ Bosh menyu", "menu:main")],
            ]
        ),
    )


@router.callback_query(F.data == "about:work")
async def about_work(cb: CallbackQuery):
    await cb.answer()
    await send_media(cb.message, "surgery_photo", "⚙️ Ish jarayonimiz")
    await send_media(cb.message, "work_video", markup=back_kb())


@router.callback_query(F.data == "about:laser")
async def about_laser(cb: CallbackQuery):
    await cb.answer()
    await send_media(cb.message, "laser_photo", "🔬 Lazer xonasi")
    await send_media(cb.message, "laser_video_1")
    await send_media(cb.message, "laser_video_2", markup=back_kb())


@router.callback_query(F.data == "about:certs")
async def about_certs(cb: CallbackQuery):
    await cb.answer()
    await send_media(cb.message, "certificates", "🏆 Shifokorlarimiz sertifikatlari", markup=back_kb())


@router.callback_query(F.data == "about:patients")
async def about_patients(cb: CallbackQuery):
    await cb.answer()
    await send_media(cb.message, "patients_video", "❤️ Bemorlarimiz fikri", markup=back_kb())


# ======================= GEMORROY HAQIDA =======================
@router.callback_query(F.data == "menu:hemorrhoid")
async def menu_hemorrhoid(cb: CallbackQuery):
    await cb.answer()
    await send_media(cb.message, "hemorrhoid_1", "📘 Gemorroy haqida qisqacha")
    await send_media(cb.message, "hemorrhoid_2", markup=kb([[("📅 Qabulga yozilish", "book")], [("⬅️ Bosh menyu", "menu:main")]]))


# ======================= MANZIL / QO'NG'IROQ / SAYT / FAQ =======================
@router.callback_query(F.data == "menu:location")
async def menu_location(cb: CallbackQuery):
    await cb.answer()
    await send_media(
        cb.message, "location_video", "📍 Bizni topish juda oson",
        markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🗺 Xaritada ochish", url=MAP_URL)],
                [InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="menu:main")],
            ]
        ),
    )


@router.callback_query(F.data == "menu:call")
async def menu_call(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer_contact(phone_number=CLINIC_PHONE, first_name="Humo Med", last_name="Klinika")
    await cb.message.answer(f"📞 Telefon: <b>{CLINIC_PHONE}</b>\nKontaktni bosib qo'ng'iroq qiling.", reply_markup=back_kb())


@router.callback_query(F.data == "menu:web")
async def menu_web(cb: CallbackQuery):
    await cb.answer()
    if WEBAPP_URL:
        await cb.message.answer(
            "🌐 Saytimizni oching:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🌐 Ochish", web_app=WebAppInfo(url=WEBAPP_URL))]]
            ),
        )
    else:
        await cb.message.answer("🌐 Sayt tez orada qo'shiladi.", reply_markup=back_kb())


@router.callback_query(F.data == "menu:faq")
async def menu_faq(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "❓ <b>Ko'p beriladigan savollar</b>\n\n"
        "<b>Qabul vaqti?</b>\nBiz 24/7 ishlaymiz, dam olish kunisiz.\n\n"
        f"<b>Konsultatsiya narxi?</b>\n{PRICE_NORMAL} so'm. Bot orqali yozilsangiz — {PRICE_BOT} so'm (bir marta).\n\n"
        "<b>Do'stimni taklif qilsam?</b>\nTaklif qilgan do'stingiz uchun konsultatsiyadan 1% chegirma beriladi.\n\n"
        "<b>Ovqat bormi?</b>\nHa, bemorlar uchun 3 mahal parhez ovqat.",
        reply_markup=back_kb(),
    )


# ======================= QABULGA YOZILISH (FSM) =======================
class Book(StatesGroup):
    name = State()
    stage = State()
    time = State()


STAGES = {"bleed": "Qon ketishi bor", "start": "Endi boshlangan", "unknown": "Aniq bilmayman"}


@router.callback_query(F.data == "book")
async def book_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(Book.name)
    await cb.message.answer("📅 <b>Qabulga yozilish</b>\n\nIsmingizni yozing:")


@router.message(Book.name, F.text)
async def book_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await state.set_state(Book.stage)
    await m.answer(
        "Holatingizga eng yaqin variantni tanlang:",
        reply_markup=kb([[(v, f"stage:{k}")] for k, v in STAGES.items()]),
    )


@router.callback_query(Book.stage, F.data.startswith("stage:"))
async def book_stage(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(stage=STAGES[cb.data.split(":")[1]])
    await state.set_state(Book.time)
    await cb.message.answer("🕒 Qaysi kun va soatda kelmoqchisiz? Masalan: <i>Ertaga 15:00</i>")


@router.message(Book.time, F.text)
async def book_time(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    phone = USERS.get(m.from_user.id, {}).get("phone", "—")
    uname = f"@{m.from_user.username}" if m.from_user.username else f"id: {m.from_user.id}"
    text = (
        "🆕 <b>Yangi qabul</b>\n\n"
        f"👤 Ism: {escape(data['name'])}\n"
        f"📞 Telefon: {escape(str(phone))}\n"
        f"🩺 Holat: {escape(data['stage'])}\n"
        f"🕒 Vaqt: {escape(m.text.strip())}\n"
        f"💰 Narx: {PRICE_BOT} so'm (bot orqali)\n"
        f"🔗 Telegram: {escape(uname)}"
    )
    try:
        await bot.send_message(ORDERS_CHAT_ID, text)
        await m.answer(
            f"✅ Arizangiz qabul qilindi! Tez orada siz bilan bog'lanamiz.\n💰 Konsultatsiya narxi: <b>{PRICE_BOT} so'm</b>",
            reply_markup=main_menu(),
        )
    except Exception as e:  # kanalga yuborib bo'lmasa
        logging.error("KANALGA YUBORILMADI: %s", e)
        await m.answer("⚠️ Arizani kanalga yuborib bo'lmadi. Bot kanalda admin ekanini tekshiring.")


# ======================= ADMIN TEST ASBOBLARI =======================
@router.message(Command("test_media"), F.from_user.id.in_(ADMINS))
async def test_media(m: Message):
    ok, bad = 0, []
    await m.answer(f"🔎 {len(MEDIA)} ta media tekshirilmoqda...")
    for key in MEDIA:
        if await send_media(m, key, caption=f"<code>{key}</code>"):
            ok += 1
        else:
            bad.append(key)
        await asyncio.sleep(0.6)
    report = f"✅ Ishladi: {ok}\n❌ Xato: {len(bad)}"
    if bad:
        report += "\n\n" + "\n".join(f"• {k}" for k in bad)
    await m.answer(report)


@router.message(F.from_user.id.in_(ADMINS), F.photo)
async def admin_photo_id(m: Message):
    await m.answer(f"<code>{m.photo[-1].file_id}</code>")


@router.message(F.from_user.id.in_(ADMINS), F.video)
async def admin_video_id(m: Message):
    await m.answer(f"<code>{m.video.file_id}</code>")


# ======================= ISHGA TUSHIRISH =======================
async def main():
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylga yozing.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
