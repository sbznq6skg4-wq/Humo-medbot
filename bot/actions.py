"""Ariza va murojaat amallari.

Bot tugmalari ham, mini ilova (sayt) ham SHU funksiyalardan foydalanadi: bitta joyda tuzatsangiz,
ikkalasida ishlaydi. Har bir amal (ok, xabar) juftligini qaytaradi.
"""
import asyncio
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

import config
import db
import services as sv
from keyboards import cb, kb
from texts import tr

log = logging.getLogger("humo")
STAGES = ("bleed", "start", "unknown")


async def lang_of(uid: int) -> str:
    u = await db.get_user(uid)
    return (u or {}).get("lang") or "uz"


async def tell_patient(bot: Bot, a: dict, key: str, markup=None, **kw) -> bool:
    lang = await lang_of(a["tg_id"])
    doctor = config.DOCTORS.get(a["doctor"], {}).get("name") or tr(lang, "b_any")
    args = {"id": a["id"], "time": html.escape(a["wanted_time"] or "—"), "doctor": html.escape(doctor),
            "map": config.MAP_URL, "reason": ""}
    args.update(kw)
    return await sv.safe_send(bot, a["tg_id"], tr(lang, key, **args), markup)


# ------------------------------------------------------------------ arizani boshqarish
async def accept(bot: Bot, aid: int, who: str) -> tuple[bool, str]:
    a = await db.get_appointment(aid)
    if not a:
        return False, "Ariza topilmadi"
    if a["status"] != "new":
        return False, "Bu ariza allaqachon ko'rib chiqilgan"
    await db.update_appointment(aid, status="accepted", handled_by=who)
    await sv.schedule_reminders(aid, a["scheduled_at"])
    await tell_patient(bot, await db.get_appointment(aid), "p_accepted")
    await sv.refresh_app_messages(bot, aid)
    return True, "✅ Qabul qilindi, bemorga xabar yuborildi"


async def reject(bot: Bot, aid: int, reason: str | None, who: str) -> tuple[bool, str]:
    a = await db.get_appointment(aid)
    if not a:
        return False, "Ariza topilmadi"
    if a["status"] == "rejected":
        return False, "Bu ariza allaqachon rad etilgan"
    await db.update_appointment(aid, status="rejected", handled_by=who)
    await db.clear_reminders(aid)
    if a["used_bonus"]:  # bot narxi kuyib ketmasin
        await db.update_user(a["tg_id"], bonus_used=0)
    lang = await lang_of(a["tg_id"])
    reason_txt = tr(lang, "p_reason", reason=html.escape(reason)) if reason else ""
    await tell_patient(bot, await db.get_appointment(aid), "p_rejected", reason=reason_txt)
    await sv.refresh_app_messages(bot, aid)
    return True, "✅ Ariza rad etildi, bemorga xabar yuborildi"


async def change_time(bot: Bot, aid: int, text: str, who: str) -> tuple[bool, str]:
    a = await db.get_appointment(aid)
    if not a:
        return False, "Ariza topilmadi"
    if a["status"] == "rejected":
        return False, "Rad etilgan arizada vaqtni o'zgartirib bo'lmaydi"
    dt = sv.parse_dt(text)
    iso = dt.isoformat(timespec="seconds") if dt else None
    wanted = sv.to_local_str(iso) if dt else text.strip()[:100]
    await db.update_appointment(aid, wanted_time=wanted, status="time_changed", handled_by=who, scheduled_at=iso)
    await db.clear_reminders(aid)
    a = await db.get_appointment(aid)
    lang = await lang_of(a["tg_id"])
    await tell_patient(bot, a, "p_time", markup=kb(
        [cb(tr(lang, "t_yes"), f"tconf:{aid}:yes"), cb(tr(lang, "t_no"), f"tconf:{aid}:no")]))
    await sv.refresh_app_messages(bot, aid)
    warn = "" if dt else "\n⚠️ Format tanilmadi, eslatma ishlamaydi (DD.MM.YYYY HH:MM yozing)."
    return True, "✅ Yangi vaqt bemorga yuborildi." + warn


async def change_doctor(bot: Bot, aid: int, key: str, who: str) -> tuple[bool, str]:
    a = await db.get_appointment(aid)
    if not a or key not in config.DOCTORS:
        return False, "Ariza yoki shifokor topilmadi"
    await db.update_appointment(aid, doctor=key, handled_by=who)
    await tell_patient(bot, await db.get_appointment(aid), "p_doctor")
    await sv.refresh_app_messages(bot, aid)
    return True, "👨‍⚕️ Shifokor almashtirildi, bemorga xabar yuborildi"


async def reply_patient(bot: Bot, aid: int, text: str) -> tuple[bool, str]:
    a = await db.get_appointment(aid)
    if not a:
        return False, "Ariza topilmadi"
    lang = await lang_of(a["tg_id"])
    ok = await sv.safe_send(bot, a["tg_id"], tr(lang, "p_msg", text=html.escape(text.strip()[:1500])),
                            kb([cb(tr(lang, "r_btn"), f"preply:{aid}")]))
    return ok, "✅ Xabar bemorga yuborildi." if ok else "⚠️ Xabar yuborilmadi (bemor botni bloklagan bo'lishi mumkin)."


# ------------------------------------------------------------------ yangi ariza / qo'ng'iroq / support
async def create_booking(bot: Bot, uid: int, name: str, doctor: str | None, stage: str, wanted: str):
    """Qabulga yozilish (bot ham, mini ilova ham). (True, natija) yoki (False, xato_kodi)."""
    u = await db.get_user(uid)
    if not u or not u["phone"]:
        return False, "no_phone"
    name, wanted = (name or "").strip()[:80], (wanted or "").strip()[:100]
    if not name or not wanted or stage not in STAGES:
        return False, "bad_input"
    doctor = doctor if doctor in config.DOCTORS else None
    lang = u["lang"] or "uz"

    base = config.PRICE_BOT if not u["bonus_used"] else config.PRICE_NORMAL  # bot narxi: 1 marta
    refs = min(await db.ref_count(uid) * config.REF_DISCOUNT_PER_FRIEND, config.MAX_REF_DISCOUNT)
    price = int(base * (100 - refs) / 100)
    used_bonus = 1 if base == config.PRICE_BOT else 0
    dt = sv.parse_dt(wanted)
    app_id = await db.create_appointment(
        tg_id=uid, name=name, phone=u["phone"], doctor=doctor, stage=stage, wanted_time=wanted,
        scheduled_at=dt.isoformat(timespec="seconds") if dt else None,
        price=price, used_bonus=used_bonus, ref_discount=refs)
    if used_bonus:
        await db.update_user(uid, bonus_used=1)
    await sv.notify_new_app(bot, app_id)
    return True, {"id": app_id, "price": price, "used_bonus": bool(used_bonus), "refs": refs, "lang": lang,
                  "doctor": config.DOCTORS.get(doctor, {}).get("name") or tr(lang, "b_any")}


async def create_callback_request(bot: Bot, uid: int):
    """"Menga telefon qiling". ("ok"|"dup"|"nophone", id)."""
    u = await db.get_user(uid)
    if not u or not u["phone"]:
        return "nophone", None
    if await db.open_callback(uid):
        return "dup", None
    cid = await db.create_callback(uid, u["full_name"] or "—", u["phone"])
    text = (f"📞 <b>Qo'ng'iroq so'rovi #{cid}</b>\n\n👤 {html.escape(u['full_name'] or '—')}\n"
            f"📱 {html.escape(u['phone'])}\n🔗 {sv.user_link({'tg_id': uid}, u)}")
    await sv.notify_staff(bot, text, kb([cb("✅ Qo'ng'iroq qildim", f"cb:done:{cid}")]))
    return "ok", cid


async def send_support(bot: Bot, uid: int, full_name: str, username: str | None, text: str) -> bool:
    """Texnik yordam / hamkorlik murojaati owner'ga."""
    u = await db.get_user(uid) or {}
    uname = f"@{username}" if username else "—"
    msg = (f"🚨 <b>Yangi support murojaati</b>\n\n👤 {html.escape(full_name)} ({html.escape(uname)})\n"
           f"🆔 <code>{uid}</code>\n📞 {html.escape(u.get('phone') or '—')}\n🌍 {u.get('lang') or 'uz'}\n\n"
           f"💬 {html.escape(text.strip()[:3000])}")
    try:
        await bot.send_message(config.OWNER_ID, msg, reply_markup=kb([cb("✍️ Mijozga javob yozish", f"reply_sup_{uid}")]))
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Support murojaati owner'ga yetmadi: %s", e)
        return False


async def broadcast_text(bot: Bot, admin_id: int, text: str) -> None:
    """Hammaga matnli xabar (mini ilovadagi rassilka)."""
    sent = failed = 0
    for tg_id in await db.active_user_ids():
        for _ in range(2):
            try:
                await bot.send_message(tg_id, text)
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
    await sv.safe_send(bot, admin_id, f"📣 Rassilka tugadi.\n✅ Yuborildi: {sent}\n❌ Yuborilmadi: {failed}")
