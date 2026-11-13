"""Mini ilova (veb-sayt) uchun API.

Xavfsizlik: sayt Telegram WebApp'ning initData qiymatini "Authorization: tma <initData>" sarlavhasida yuboradi.
Server uni bot tokeni bilan tekshiradi (HMAC) va ID bo'yicha ruxsat beradi:
  user  — hamma botdan foydalanuvchilar (qabul, qo'ng'iroq, AI, ovoz, support)
  admin — config.ADMINS (arizalar, qo'ng'iroqlar, savollar, rassilka...)
  owner — config.OWNER_ID (rasm/video yuklash, e'lon)
Tugmani yashirish yetarli emas — asosiy tekshiruv shu yerda, serverda.
"""
import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import time
from urllib.parse import parse_qsl

from aiohttp import web

import actions
import config
import db
import media_store
import services as sv
from texts import tr

log = logging.getLogger("humo")
WEB_HISTORY: dict[int, list[dict]] = {}
TTS_DIR = os.path.join(os.path.dirname(config.DB_PATH) or ".", "tts")
DOCTOR_KEYS = tuple(config.DOCTORS)


# ------------------------------------------------------------ autentifikatsiya
def verify_init_data(init_data: str) -> dict | None:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received = pairs.pop("hash", None)
        if not received:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), received):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > 86400:
            return None
        return json.loads(pairs["user"])
    except (ValueError, KeyError, TypeError):
        return None


def err(code: str, status: int = 400, **extra) -> web.Response:
    return web.json_response({"error": code, **extra}, status=status)


def guard(level: str = "user"):
    def deco(handler):
        async def wrapper(request: web.Request):
            header = request.headers.get("Authorization", "")
            tgu = verify_init_data(header[4:]) if header.startswith("tma ") else None
            if not tgu:
                return err("unauthorized", 401)
            uid = tgu["id"]
            if (level in ("admin", "owner") and uid not in config.ADMINS) or (level == "owner" and uid != config.OWNER_ID):
                return err("forbidden", 403)
            tgu["full_name"] = " ".join(x for x in (tgu.get("first_name"), tgu.get("last_name")) if x) or "—"
            await db.upsert_user(uid, tgu.get("username"), tgu["full_name"])
            request["tg"] = tgu
            return await handler(request)
        return wrapper
    return deco


async def body(request: web.Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


bot_of = lambda r: r.app["bot"]  # noqa: E731


@web.middleware
async def cors(request: web.Request, handler):
    resp = web.Response(status=204) if request.method == "OPTIONS" else await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = config.ALLOWED_ORIGIN
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Vary"] = "Origin"
    return resp


async def health(_: web.Request):
    return web.json_response({"ok": True})


# ------------------------------------------------------------ foydalanuvchi
@guard()
async def me(request):
    uid = request["tg"]["id"]
    u = await db.get_user(uid)
    refs = await db.ref_count(uid)
    return web.json_response({
        "admin": uid in config.ADMINS, "owner": uid == config.OWNER_ID, "lang": u["lang"], "name": u["full_name"],
        "phone": bool(u["phone"]), "first_price": not u["bonus_used"], "refs": refs,
        "disc": min(refs * config.REF_DISCOUNT_PER_FRIEND, config.MAX_REF_DISCOUNT),
        "banner": await db.get_setting("banner", ""), "link": f"https://t.me/{config.BOT_USERNAME}?start=ref{uid}",
        "ai": bool(config.GEMINI_API_KEY) and await db.get_setting("ai_enabled", "1") == "1",
        "tts": bool(config.ELEVEN_API_KEY), "tel": config.CLINIC_PHONE, "map": config.MAP_URL, "bot": config.BOT_USERNAME,
    })


@guard()
async def set_lang(request):
    lang = (await body(request)).get("lang")
    if lang in ("uz", "ru", "en"):
        await db.update_user(request["tg"]["id"], lang=lang)
    return web.json_response({"ok": True})


@guard()
async def media_list(_):
    return web.json_response([{"id": m["id"], "section": m["section"], "title": m["title"], "kind": m["kind"],
                               "url": f"/media/{m['file']}"} for m in await db.list_media()])


@guard()
async def book(request):
    d, tgu = await body(request), request["tg"]
    wanted = str(d.get("time") or "").strip()[:100]
    ok, res = await actions.create_booking(bot_of(request), tgu["id"], str(d.get("name") or tgu["full_name"]),
                                           d.get("doctor"), d.get("stage"), wanted)
    if not ok:
        return err(res)
    lang = res["lang"]
    note = (tr(lang, "b_note_bonus") if res["used_bonus"] else "") + (tr(lang, "b_note_ref", disc=res["refs"]) if res["refs"] else "")
    await sv.safe_send(bot_of(request), tgu["id"], tr(lang, "b_done", id=res["id"], time=html.escape(wanted),
                       doctor=res["doctor"], price=config.fmt_price(res["price"]), note=note))
    return web.json_response({"id": res["id"], "price": res["price"], "used_bonus": res["used_bonus"]})


@guard()
async def callback(request):
    uid = request["tg"]["id"]
    status, _ = await actions.create_callback_request(bot_of(request), uid)
    if status == "ok":
        u = await db.get_user(uid)
        await sv.safe_send(bot_of(request), uid, tr(u["lang"] or "uz", "c_ok", phone_user=u["phone"]))
    return web.json_response({"status": status})


@guard()
async def support(request):
    text, tgu = str((await body(request)).get("text") or "").strip(), request["tg"]
    if not text:
        return err("empty")
    ok = await actions.send_support(bot_of(request), tgu["id"], tgu["full_name"], tgu.get("username"), text)
    return web.json_response({"ok": ok})


@guard()
async def ai(request):
    tgu, text = request["tg"], str((await body(request)).get("text") or "").strip()[:1000]
    uid = tgu["id"]
    if not text:
        return err("empty")
    if not config.GEMINI_API_KEY or await db.get_setting("ai_enabled", "1") != "1":
        return err("ai_off", 503)
    if not sv.AI_LIMIT.allow(uid):
        return err("limit", 429)
    qid = await db.add_question(uid, text)
    hist = WEB_HISTORY.setdefault(uid, [])
    try:
        answer = await sv.ask_gemini(hist[-8:], text)
    except Exception as e:  # noqa: BLE001
        log.error("Gemini xatosi (mini ilova): %s", e)
        await sv.notify_owner(bot_of(request), "Gemini xatosi (mini ilova)", str(e))
        return err("ai_error", 502, detail=str(e)[:600] if uid in config.ADMINS else "")
    hist.extend([{"role": "user", "parts": [{"text": text}]}, {"role": "model", "parts": [{"text": answer}]}])
    WEB_HISTORY[uid] = hist[-10:]
    await db.update_question(qid, answer=answer)
    return web.json_response({"answer": answer, "qid": qid})


@guard()
async def tts(request):
    uid = request["tg"]["id"]
    try:
        q = await db.get_question(int(str((await body(request)).get("qid"))))
    except ValueError:
        return err("bad_input")
    if not q or q["tg_id"] != uid or not q["answer"] or not config.ELEVEN_API_KEY:
        return err("not_found", 404)
    path = os.path.join(TTS_DIR, f"{q['id']}.mp3")
    if not os.path.exists(path):  # bir marta yaratib, keyin diskdan beramiz (qayta pul to'lamaymiz)
        if not sv.TTS_LIMIT.allow(uid):
            return err("limit", 429)
        try:
            audio = await sv.eleven_tts(sv.clean_for_tts(q["answer"]))
        except Exception as e:  # noqa: BLE001
            log.error("ElevenLabs xatosi (mini ilova): %s", e)
            await sv.notify_owner(bot_of(request), "ElevenLabs xatosi (mini ilova)", str(e))
            return err("tts_error", 502, detail=str(e)[:500] if uid in config.ADMINS else "")
        with open(path, "wb") as f:
            f.write(audio)
    return web.FileResponse(path, headers={"Content-Type": "audio/mpeg"})


# ------------------------------------------------------------ admin
@guard("admin")
async def overview(_):
    return web.json_response({**await db.stats(), "ai": await db.get_setting("ai_enabled", "1") == "1"})


@guard("admin")
async def appointments(request):
    status = request.query.get("status") or None
    out = []
    for a in await db.list_appointments(status=status, limit=min(int(request.query.get("limit", "60") or 60), 200)):
        u = await db.get_user(a["tg_id"]) or {}
        out.append({
            "id": a["id"], "name": a["name"], "phone": a["phone"], "username": u.get("username"),
            "doctor": config.DOCTORS.get(a["doctor"], {}).get("name", "Farqi yo'q"), "doctor_key": a["doctor"],
            "stage": sv.STAGE_UZ.get(a["stage"], a["stage"]), "time": a["wanted_time"], "st": a["status"],
            "status": sv.STATUS_UZ.get(a["status"], a["status"]), "price": a["price"],
            "created": sv.to_local_str(a["created_at"]),
        })
    return web.json_response(out)


@guard("admin")
async def app_action(request):
    d, tgu = await body(request), request["tg"]
    try:
        aid = int(d.get("id"))
    except (TypeError, ValueError):
        return err("bad_input")
    act, val, bot = d.get("action"), str(d.get("value") or "").strip(), bot_of(request)
    who = tgu["full_name"]
    if act == "ok":
        ok, msg = await actions.accept(bot, aid, who)
    elif act == "no":
        ok, msg = await actions.reject(bot, aid, val[:300] or None, who)
    elif act == "time" and val:
        ok, msg = await actions.change_time(bot, aid, val, who)
    elif act == "doctor" and val in DOCTOR_KEYS:
        ok, msg = await actions.change_doctor(bot, aid, val, who)
    elif act == "reply" and val:
        ok, msg = await actions.reply_patient(bot, aid, val)
    else:
        return err("bad_input")
    return web.json_response({"ok": ok, "msg": msg})


@guard("admin")
async def callbacks(_):
    return web.json_response([{
        "id": x["id"], "name": x["name"], "phone": x["phone"], "done": x["status"] != "new",
        "created": sv.to_local_str(x["created_at"]), "by": x["handled_by"]} for x in await db.list_callbacks(limit=100)])


@guard("admin")
async def callback_done(request):
    try:
        await db.update_callback(int((await body(request)).get("id")), status="done", handled_by=request["tg"]["full_name"])
    except (TypeError, ValueError):
        return err("bad_input")
    return web.json_response({"ok": True})


@guard("admin")
async def questions(_):
    return web.json_response([{
        "id": q["id"], "name": q.get("full_name"), "username": q.get("username"), "phone": q.get("phone"),
        "question": q["question"], "answer": q["answer"], "created": sv.to_local_str(q["created_at"])}
        for q in await db.list_questions(limit=50)])


@guard("admin")
async def users(_):
    return web.json_response([{
        "id": u["tg_id"], "name": u["full_name"], "username": u["username"], "phone": u["phone"],
        "lang": u["lang"], "created": sv.to_local_str(u["created_at"])} for u in await db.list_users(limit=100)])


@guard("admin")
async def broadcast(request):
    text = str((await body(request)).get("text") or "").strip()[:3500]
    if not text:
        return err("empty")
    asyncio.create_task(actions.broadcast_text(bot_of(request), request["tg"]["id"], text))
    return web.json_response({"ok": True, "users": len(await db.active_user_ids())})


@guard("admin")
async def ai_toggle(request):
    on = bool((await body(request)).get("on"))
    await db.set_setting("ai_enabled", "1" if on else "0")
    return web.json_response({"ai": on})


# ------------------------------------------------------------ owner
@guard("owner")
async def owner_media(_):
    return web.json_response([{"id": m["id"], "section": m["section"], "title": m["title"], "kind": m["kind"],
                               "status": m["status"], "url": f"/media/{m['file']}" if m["file"] else ""}
                              for m in await db.list_media(ready_only=False)])


@guard("owner")
async def owner_upload(request):
    reader = await request.multipart()
    section, title, tmp, kind = "gallery", "", None, None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "section":
            section = (await part.text()).strip()
        elif part.name == "title":
            title = (await part.text()).strip()[:80]
        elif part.name == "file":
            kind = media_store.kind_of(part.filename or "")
            if not kind:
                return err("bad_type")
            try:
                tmp, _ = await media_store.save_upload(part, part.filename)
            except ValueError:
                return err("too_big", 413)
            break
    if not tmp:
        return err("no_file")
    mid = await db.add_media(section if section in media_store.SECTIONS else "gallery", title, kind, "")
    asyncio.create_task(media_store.process(mid, tmp, kind))  # fonda optimallashtiriladi
    return web.json_response({"id": mid, "status": "processing"})


@guard("owner")
async def owner_media_delete(request):
    try:
        row = await db.get_media(int((await body(request)).get("id")))
    except (TypeError, ValueError):
        return err("bad_input")
    if row:
        await media_store.remove_files(row)
        await db.delete_media(row["id"])
    return web.json_response({"ok": True})


@guard("owner")
async def owner_banner(request):
    await db.set_setting("banner", str((await body(request)).get("text") or "").strip()[:300])
    return web.json_response({"ok": True})


# ------------------------------------------------------------ ilova
def make_app(bot) -> web.Application:
    app = web.Application(middlewares=[cors])
    app["bot"] = bot
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    os.makedirs(TTS_DIR, exist_ok=True)
    g, p = web.get, web.post
    app.add_routes([
        g("/", health), g("/health", health),
        g("/api/me", me), p("/api/lang", set_lang), g("/api/media", media_list),
        p("/api/book", book), p("/api/callback", callback), p("/api/support", support),
        p("/api/ai", ai), p("/api/tts", tts),
        g("/api/admin/overview", overview), g("/api/admin/appointments", appointments), p("/api/admin/app", app_action),
        g("/api/admin/callbacks", callbacks), p("/api/admin/callback_done", callback_done),
        g("/api/admin/questions", questions), g("/api/admin/users", users),
        p("/api/admin/broadcast", broadcast), p("/api/admin/ai", ai_toggle),
        g("/api/owner/media", owner_media), p("/api/owner/media", owner_upload),
        p("/api/owner/media_delete", owner_media_delete), p("/api/owner/banner", owner_banner),
        web.route("OPTIONS", "/{tail:.*}", health),
    ])
    app.router.add_static("/media", config.MEDIA_DIR)
    return app
