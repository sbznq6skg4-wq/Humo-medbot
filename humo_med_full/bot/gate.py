"""Kirish nazorati: bloklangan foydalanuvchilar va (yoqilgan bo'lsa) majburiy obuna."""
import logging
import time

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message

import config
import db
from keyboards import cb, kb, url_btn
from texts import tr

log = logging.getLogger("humo")
_ok_cache: dict[tuple[int, int], float] = {}


async def is_member(bot: Bot, channel_id: int, uid: int) -> bool:
    hit = _ok_cache.get((channel_id, uid))
    if hit and time.time() - hit < 60:
        return True
    try:
        member = await bot.get_chat_member(channel_id, uid)
        ok = member.status in ("member", "administrator", "creator")
    except Exception as e:  # noqa: BLE001
        # Kanal yoki bot sozlamasida muammo bo'lsa, foydalanuvchini to'smaymiz
        log.error("Obuna tekshiruvi xatosi (kanal %s): %s", channel_id, e)
        return True
    if ok:
        _ok_cache[(channel_id, uid)] = time.time()
    return ok


class Gate(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or user.id in config.ADMINS:
            return await handler(event, data)

        u = await db.get_user(user.id)
        if u and u["banned"]:
            return None
        if isinstance(event, CallbackQuery) and event.data == "sub:check":
            return await handler(event, data)

        if await db.get_setting("sub_enabled", "0") == "1":
            channel = await db.get_setting("sub_channel")
            bot: Bot = data["bot"]
            if channel and not await is_member(bot, int(channel), user.id):
                lang = (u or {}).get("lang") or "uz"
                url = await db.get_setting("sub_url", "")
                rows = []
                if url:
                    rows.append([url_btn(tr(lang, "sub_join"), url)])
                rows.append([cb(tr(lang, "sub_check"), "sub:check")])
                chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
                await bot.send_message(chat_id, tr(lang, "sub_need"), reply_markup=kb(*rows))
                if isinstance(event, CallbackQuery):
                    await event.answer()
                return None
        return await handler(event, data)
