"""Saytdagi admin panel uchun API (faqat o'qish).

Xavfsizlik: sayt Telegram WebApp'ning initData qiymatini yuboradi. Biz uni bot tokeni bilan
tekshiramiz (HMAC) va foydalanuvchi ID si ADMINS ro'yxatida bo'lsagina ma'lumot beramiz.
Tugmani yashirish yetarli emas — asosiy tekshiruv shu yerda, serverda.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from aiohttp import web

import config
import db
import services as sv


def verify_init_data(init_data: str) -> dict | None:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received = pairs.pop("hash", None)
        if not received:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > 86400:
            return None
        return json.loads(pairs["user"])
    except (ValueError, KeyError, TypeError):
        return None


def admin_user(request: web.Request) -> dict | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("tma "):
        return None
    user = verify_init_data(header[4:])
    return user if user and user.get("id") in config.ADMINS else None


def guard(handler):
    async def wrapper(request: web.Request):
        user = admin_user(request)
        if not user:
            return web.json_response({"error": "forbidden"}, status=403)
        return await handler(request)
    return wrapper


@web.middleware
async def cors(request: web.Request, handler):
    resp = web.Response(status=204) if request.method == "OPTIONS" else await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = config.ALLOWED_ORIGIN
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Vary"] = "Origin"
    return resp


async def health(_: web.Request):
    return web.json_response({"ok": True})


@guard
async def me(_: web.Request):
    return web.json_response({"admin": True})


@guard
async def overview(_: web.Request):
    return web.json_response(await db.stats())


@guard
async def appointments(request: web.Request):
    status = request.query.get("status") or None
    limit = min(int(request.query.get("limit", "50") or 50), 200)
    out = []
    for a in await db.list_appointments(status=status, limit=limit):
        u = await db.get_user(a["tg_id"]) or {}
        out.append({
            "id": a["id"], "name": a["name"], "phone": a["phone"], "username": u.get("username"),
            "doctor": config.DOCTORS.get(a["doctor"], {}).get("name", "—"),
            "stage": sv.STAGE_UZ.get(a["stage"], a["stage"]), "time": a["wanted_time"],
            "status": sv.STATUS_UZ.get(a["status"], a["status"]), "price": a["price"],
            "created": sv.to_local_str(a["created_at"]),
        })
    return web.json_response(out)


@guard
async def callbacks(_: web.Request):
    return web.json_response([{
        "id": x["id"], "name": x["name"], "phone": x["phone"],
        "status": "Yangi" if x["status"] == "new" else "Qo'ng'iroq qilindi",
        "created": sv.to_local_str(x["created_at"]), "by": x["handled_by"],
    } for x in await db.list_callbacks(limit=100)])


@guard
async def questions(_: web.Request):
    return web.json_response([{
        "id": q["id"], "name": q.get("full_name"), "username": q.get("username"), "phone": q.get("phone"),
        "question": q["question"], "answer": q["answer"], "created": sv.to_local_str(q["created_at"]),
    } for q in await db.list_questions(limit=50)])


@guard
async def users(_: web.Request):
    return web.json_response([{
        "id": u["tg_id"], "name": u["full_name"], "username": u["username"], "phone": u["phone"],
        "lang": u["lang"], "created": sv.to_local_str(u["created_at"]),
    } for u in await db.list_users(limit=100)])


def make_app() -> web.Application:
    app = web.Application(middlewares=[cors])
    app.add_routes([
        web.get("/", health), web.get("/health", health),
        web.get("/api/admin/me", me), web.get("/api/admin/overview", overview),
        web.get("/api/admin/appointments", appointments), web.get("/api/admin/callbacks", callbacks),
        web.get("/api/admin/questions", questions), web.get("/api/admin/users", users),
        web.route("OPTIONS", "/{tail:.*}", health),
    ])
    return app
