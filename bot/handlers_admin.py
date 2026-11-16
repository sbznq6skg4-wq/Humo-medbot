"""Admin tomoni: /admin paneli, ariza tugmalari (qabul/rad/vaqt/shifokor/javob),
rassilka, majburiy obuna sozlamasi, statistika, eksport, bloklash."""
import asyncio
import csv
import html
import io
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import config
import db
import actions
import services as sv
from keyboards import cb, kb, web_btn, webapp_url
from texts import tr

router = Router()
log = logging.getLogger("humo")

ADMIN_PENDING: dict[int, dict] = {}  # admin yozishi kutilayotgan amallar
BROADCAST: dict[int, tuple[int, int]] = {}  # rassilka uchun tayyorlangan xabar

BACK = lambda: kb([cb("⬅️ Admin panel", "adm:home")])  # noqa: E731
ICON = {"new": "🆕", "accepted": "✅", "confirmed": "✅", "time_changed": "🕒", "rejected": "❌"}


def is_admin(uid: int) -> bool:
    return uid in config.ADMINS


# ------------------------------------------------------------ admin panel
async def panel_markup():
    ai_on = await db.get_setting("ai_enabled", "1") == "1"
    return kb(
        [cb("📊 Statistika", "adm:stats"), cb("📅 Bugungi qabullar", "adm:today")],
        [cb("🆕 Yangi arizalar", "adm:new"), cb("📞 Qo'ng'iroq so'rovlari", "adm:calls")],
        [cb("❓ Savollar (AI)", "adm:qs"), cb("👥 Foydalanuvchilar", "adm:users")],
        [cb("📣 Rassilka", "adm:bc"), cb("🔒 Majburiy obuna", "adm:sub")],
        [cb("🤖 AI: yoqilgan ✅" if ai_on else "🤖 AI: o'chirilgan ⛔", "adm:ai"), cb("📤 CSV eksport", "adm:csv")],
        [cb("🚫 Bloklash", "adm:ban"), cb("♻️ Blokdan chiqarish", "adm:unban")],
        [web_btn("🌐 Saytdagi admin panel", webapp_url("uz"))],
    )


@router.message(Command("admin"))
async def cmd_admin(m: Message):
    if not is_admin(m.from_user.id):
        return  # boshqalarga umuman javob bermaymiz
    ADMIN_PENDING.pop(m.from_user.id, None)
    await m.answer("🛠 <b>Humo Med — admin panel</b>", reply_markup=await panel_markup())


@router.message(Command("cancel"))
async def cmd_cancel(m: Message):
    if ADMIN_PENDING.pop(m.from_user.id, None) is not None:
        await m.answer("Bekor qilindi.")


def app_line(a: dict) -> str:
    doc = config.DOCTORS.get(a["doctor"], {}).get("name", "—").split()[0]
    return (f"{ICON.get(a['status'], '•')} <b>#{a['id']}</b> {html.escape(a['name'] or '—')} · "
            f"{html.escape(a['phone'] or '—')} · {html.escape(a['wanted_time'] or '—')} · {html.escape(doc)}")


def apps_markup(apps: list[dict]):
    btns = [cb(f"#{a['id']}", f"app:show:{a['id']}") for a in apps[:12]]
    rows = [btns[i:i + 4] for i in range(0, len(btns), 4)]
    rows.append([cb("⬅️ Admin panel", "adm:home")])
    return kb(*rows)


@router.callback_query(F.data.startswith("adm:"))
async def admin_callbacks(c: CallbackQuery, bot: Bot):
    if not is_admin(c.from_user.id):
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    act = c.data.split(":")[1]
    uid = c.from_user.id
    chat = c.message.chat.id
    await c.answer()

    if act == "home":
        await bot.send_message(chat, "🛠 <b>Humo Med — admin panel</b>", reply_markup=await panel_markup())

    elif act == "stats":
        s = await db.stats()
        await bot.send_message(chat, (
            "📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b> (bugun +{s['users_today']})\n"
            f"📋 Jami arizalar: <b>{s['apps_total']}</b>\n"
            f"🆕 Yangi: {s['apps_new']}\n✅ Qabul qilingan: {s['apps_accepted']}\n"
            f"🕒 Vaqt kelishilmoqda: {s['apps_time_changed']}\n❌ Rad etilgan: {s['apps_rejected']}\n"
            f"📅 Bugungi qabullar: {s['apps_today']}\n"
            f"📞 Javobsiz qo'ng'iroq so'rovlari: {s['calls_new']}\n❓ AI savollari: {s['questions']}"), reply_markup=BACK())

    elif act in ("today", "new"):
        apps = await db.list_appointments(status="new" if act == "new" else None, today=(act == "today"), limit=15)
        title = "🆕 Yangi arizalar" if act == "new" else "📅 Bugungi qabullar"
        body = "\n".join(app_line(a) for a in apps) or "Hozircha yo'q."
        await bot.send_message(chat, f"<b>{title}</b>\n\n{body}\n\nTugmani bosib arizani ochasiz:", reply_markup=apps_markup(apps))

    elif act == "calls":
        calls = await db.list_callbacks(limit=15)
        lines = [f"{'🆕' if x['status'] == 'new' else '✅'} <b>#{x['id']}</b> {html.escape(x['name'] or '—')} · "
                 f"{html.escape(x['phone'] or '—')} · {sv.to_local_str(x['created_at'])}" for x in calls]
        await bot.send_message(chat, "<b>📞 Qo'ng'iroq so'rovlari</b>\n\n" + ("\n".join(lines) or "Hozircha yo'q."), reply_markup=BACK())

    elif act == "qs":
        qs = await db.list_questions(limit=8)
        parts = []
        for q in qs:
            who = f"@{q['username']}" if q.get("username") else (q.get("full_name") or q["tg_id"])
            parts.append(f"👤 {html.escape(str(who))} · {html.escape(q.get('phone') or '—')}\n"
                         f"❓ {html.escape((q['question'] or '')[:200])}")
        await bot.send_message(chat, "<b>❓ So'nggi savollar</b>\n\n" + ("\n\n".join(parts) or "Hozircha yo'q."), reply_markup=BACK())

    elif act == "users":
        users = await db.list_users(limit=15)
        total = (await db.stats())["users"]
        lines = [f"• {html.escape(u['full_name'] or '—')} {('@' + u['username']) if u['username'] else ''} · "
                 f"{html.escape(u['phone'] or '—')}" for u in users]
        await bot.send_message(chat, f"<b>👥 Foydalanuvchilar: {total}</b>\n\nSo'nggilari:\n" + "\n".join(lines), reply_markup=BACK())

    elif act == "bc":
        ADMIN_PENDING[uid] = {"kind": "bc"}
        await bot.send_message(chat, "📣 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring (matn, rasm yoki video).\nBekor qilish: /cancel")

    elif act == "ai":
        on = await db.get_setting("ai_enabled", "1") == "1"
        await db.set_setting("ai_enabled", "0" if on else "1")
        await bot.send_message(chat, "🤖 AI maslahatchi " + ("o'chirildi ⛔" if on else "yoqildi ✅"), reply_markup=await panel_markup())

    elif act == "csv":
        apps = await db.list_appointments(limit=100000)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "ism", "telefon", "shifokor", "holat", "vaqt", "narx", "status", "yaratilgan"])
        for a in apps:
            w.writerow([a["id"], a["name"], a["phone"], config.DOCTORS.get(a["doctor"], {}).get("name", ""),
                        sv.STAGE_UZ.get(a["stage"], a["stage"]), a["wanted_time"], a["price"], a["status"],
                        sv.to_local_str(a["created_at"])])
        await bot.send_document(chat, BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename="arizalar.csv"))

    elif act in ("ban", "unban"):
        ADMIN_PENDING[uid] = {"kind": act}
        await bot.send_message(chat, "Foydalanuvchi Telegram ID sini yuboring.\nBekor qilish: /cancel")

    elif act in ("sub", "subtoggle", "subset"):
        if act == "subtoggle":
            on = await db.get_setting("sub_enabled", "0") == "1"
            if not on and not await db.get_setting("sub_channel"):
                await bot.send_message(chat, "Avval kanalni o'rnating.", reply_markup=BACK())
                return
            await db.set_setting("sub_enabled", "0" if on else "1")
        if act == "subset":
            ADMIN_PENDING[uid] = {"kind": "subch"}
            await bot.send_message(chat, "Kanal username'ini (@kanal) yoki ID sini yuboring. Bot o'sha kanalda <b>admin</b> bo'lishi shart.\nBekor qilish: /cancel")
            return
        on = await db.get_setting("sub_enabled", "0") == "1"
        title = await db.get_setting("sub_title", "—")
        await bot.send_message(chat, f"🔒 <b>Majburiy obuna</b>\n\nHolati: {'yoqilgan ✅' if on else 'o‘chirilgan ⛔'}\nKanal: {html.escape(title or '—')}",
                               reply_markup=kb([cb("🔁 Yoqish / o'chirish", "adm:subtoggle")],
                                               [cb("📢 Kanalni o'rnatish", "adm:subset")],
                                               [cb("⬅️ Admin panel", "adm:home")]))


# ------------------------------------------------------------ qo'ng'iroq so'rovi tugmasi
@router.callback_query(F.data.startswith("cb:done:"))
async def callback_done(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    cid = int(c.data.split(":")[2])
    items = [x for x in await db.list_callbacks(limit=1000) if x["id"] == cid]
    if not items or items[0]["status"] != "new":
        await c.answer("Bu so'rov allaqachon yopilgan", show_alert=True)
        return
    await db.update_callback(cid, status="done", handled_by=c.from_user.full_name)
    await c.answer("✅ Belgilandi")
    try:
        await c.message.edit_text((c.message.html_text or "") + f"\n\n✅ Qo'ng'iroq qilindi — {html.escape(c.from_user.full_name)}")
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------ ariza tugmalari
async def ask_admin(c: CallbackQuery, bot: Bot, kind: str, aid: int, prompt: str) -> None:
    uid = c.from_user.id
    try:
        await bot.send_message(uid, f"<b>Ariza #{aid}</b>\n{prompt}\nBekor qilish: /cancel")
    except Exception:  # noqa: BLE001
        await c.answer(f"Avval @{config.BOT_USERNAME} ga kirib /start bosing, keyin qayta urining.", show_alert=True)
        return
    ADMIN_PENDING[uid] = {"kind": kind, "app": aid}
    await c.answer("Shaxsiy chatga yozildi ✍️")


@router.callback_query(F.data.startswith("app:"))
async def app_action(c: CallbackQuery, bot: Bot):
    if not is_admin(c.from_user.id):
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    parts = c.data.split(":")
    act, aid = parts[1], int(parts[2])
    a = await db.get_appointment(aid)
    if not a:
        await c.answer("Ariza topilmadi", show_alert=True)
        return
    who = c.from_user.full_name

    if act == "show":
        m = await bot.send_message(c.message.chat.id, await sv.app_text(a), reply_markup=sv.app_kb(a))
        await db.add_app_msg(aid, m.chat.id, m.message_id)
        await c.answer()

    elif act == "ok":
        ok, msg = await actions.accept(bot, aid, who)
        await c.answer(msg, show_alert=not ok)

    elif act == "no":
        if a["status"] == "rejected":
            await c.answer("Bu ariza allaqachon rad etilgan", show_alert=True)
            return
        await ask_admin(c, bot, "no", aid, "❌ Rad etish sababini yozing (bemorga ko'rsatiladi) yoki «-» yuboring.")

    elif act == "time":
        await ask_admin(c, bot, "time", aid, "🕒 Yangi aniq vaqtni yozing: <b>DD.MM.YYYY HH:MM</b> (masalan 15.12.2026 15:00).")

    elif act == "reply":
        await ask_admin(c, bot, "reply", aid, "💬 Bemorga yuboriladigan xabarni yozing.")

    elif act == "doc":
        rows = [[cb(d["name"], f"app:docset:{aid}:{k}")] for k, d in config.DOCTORS.items()]
        rows.append([cb("⬅️ Orqaga", f"app:back:{aid}")])
        try:
            await c.message.edit_reply_markup(reply_markup=kb(*rows))
        except Exception:  # noqa: BLE001
            pass
        await c.answer()

    elif act == "docset":
        ok, msg = await actions.change_doctor(bot, aid, parts[3], who)
        await c.answer(msg, show_alert=not ok)

    elif act == "back":
        await sv.refresh_app_messages(bot, aid)
        await c.answer()


# ------------------------------------------------------------ admin matn kiritishi
def _pending(m: Message) -> bool:
    return (m.from_user is not None and m.from_user.id in ADMIN_PENDING
            and not (m.text and m.text.startswith("/")))


@router.message(_pending)
async def pending_input(m: Message, bot: Bot):
    uid = m.from_user.id
    p = ADMIN_PENDING[uid]
    kind = p["kind"]
    who = m.from_user.full_name

    if kind == "bc":  # rassilka: istalgan turdagi xabar
        ADMIN_PENDING.pop(uid)
        BROADCAST[uid] = (m.chat.id, m.message_id)
        total = len(await db.active_user_ids())
        await bot.copy_message(uid, m.chat.id, m.message_id)
        await m.answer(f"👆 Shu xabar <b>{total}</b> ta foydalanuvchiga yuboriladi. Tasdiqlaysizmi?",
                       reply_markup=kb([cb("✅ Yuborish", "bc:go"), cb("❌ Bekor", "bc:cancel")]))
        return

    if not m.text:
        await m.answer("Iltimos, matn yuboring.")
        return
    text = m.text.strip()
    ADMIN_PENDING.pop(uid)

    if kind in ("no", "time", "reply"):
        aid = p["app"]
        if kind == "no":
            ok, msg = await actions.reject(bot, aid, None if text == "-" else text[:300], who)
        elif kind == "time":
            ok, msg = await actions.change_time(bot, aid, text, who)
        else:
            ok, msg = await actions.reply_patient(bot, aid, text)
        await m.answer(msg)

    elif kind in ("ban", "unban"):
        if not text.lstrip("-").isdigit():
            await m.answer("ID faqat raqamlardan iborat bo'lishi kerak.")
            return
        target = int(text)
        if not await db.get_user(target):
            await m.answer("Bunday foydalanuvchi topilmadi.")
            return
        await db.update_user(target, banned=1 if kind == "ban" else 0)
        await m.answer("🚫 Bloklandi." if kind == "ban" else "♻️ Blokdan chiqarildi.")

    elif kind == "subch":
        ref = text.strip()
        try:
            chat = await bot.get_chat(int(ref) if ref.lstrip("-").isdigit() else ref)
            me = await bot.get_chat_member(chat.id, bot.id)
            if me.status not in ("administrator", "creator"):
                await m.answer("⚠️ Bot bu kanalda admin emas. Avval botni kanalga admin qiling.")
                return
            url = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or await bot.export_chat_invite_link(chat.id))
        except Exception as e:  # noqa: BLE001
            await m.answer(f"⚠️ Kanal topilmadi yoki bot kira olmadi: {html.escape(str(e))}")
            return
        await db.set_setting("sub_channel", str(chat.id))
        await db.set_setting("sub_url", url)
        await db.set_setting("sub_title", chat.title or ref)
        await m.answer(f"✅ Kanal o'rnatildi: <b>{html.escape(chat.title or ref)}</b>\nYoqish uchun: /admin → 🔒 Majburiy obuna.")


async def _lang(uid: int) -> str:
    u = await db.get_user(uid)
    return (u or {}).get("lang") or "uz"


# ------------------------------------------------------------ rassilka
@router.callback_query(F.data.startswith("bc:"))
async def broadcast_cb(c: CallbackQuery, bot: Bot):
    if not is_admin(c.from_user.id):
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    uid = c.from_user.id
    msg = BROADCAST.pop(uid, None)
    if c.data == "bc:cancel" or not msg:
        await c.answer("Bekor qilindi")
        return
    await c.answer("Yuborish boshlandi")
    asyncio.create_task(run_broadcast(bot, uid, *msg))


async def run_broadcast(bot: Bot, admin_id: int, from_chat: int, msg_id: int) -> None:
    ids = await db.active_user_ids()
    sent = failed = 0
    for tg_id in ids:
        for attempt in range(2):
            try:
                await bot.copy_message(tg_id, from_chat, msg_id)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                await db.update_user(tg_id, blocked_bot=1)
                failed += 1
                break
            except Exception:  # noqa: BLE001
                failed += 1
                break
        await asyncio.sleep(0.05)
    await bot.send_message(admin_id, f"📣 Rassilka tugadi.\n✅ Yuborildi: {sent}\n❌ Yuborilmadi: {failed}")


# ------------------------------------------------------------ admin uchun file_id olish
def _admin_media(m: Message) -> bool:
    return (m.from_user is not None and is_admin(m.from_user.id)
            and m.from_user.id not in ADMIN_PENDING and bool(m.photo or m.video))


@router.message(_admin_media)
async def media_id(m: Message):
    fid = m.photo[-1].file_id if m.photo else m.video.file_id
    await m.answer(f"<code>{fid}</code>\n\nBu ID shu bot uchun ishlaydi (config.py dagi MEDIA ga qo'ying).")
