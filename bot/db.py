"""Ma'lumotlar bazasi (SQLite, aiosqlite).

Jadvallar: users, appointments, app_msgs, callbacks, questions, settings, reminders.
Vaqtlar bazada UTC ISO ko'rinishida saqlanadi, ko'rsatishda Toshkent vaqtiga o'giriladi.
"""
import os
from datetime import datetime, timedelta, timezone

import aiosqlite

from config import DB_PATH, TZ

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    tg_id INTEGER PRIMARY KEY,
    username TEXT, full_name TEXT, phone TEXT, lang TEXT,
    referred_by INTEGER, bonus_used INTEGER DEFAULT 0, intro_sent INTEGER DEFAULT 0,
    banned INTEGER DEFAULT 0, blocked_bot INTEGER DEFAULT 0,
    created_at TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS appointments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER, name TEXT, phone TEXT, doctor TEXT, stage TEXT,
    wanted_time TEXT, scheduled_at TEXT, status TEXT DEFAULT 'new',
    price INTEGER, used_bonus INTEGER DEFAULT 0, ref_discount INTEGER DEFAULT 0,
    handled_by TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS app_msgs(app_id INTEGER, chat_id INTEGER, message_id INTEGER);
CREATE TABLE IF NOT EXISTS callbacks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER, name TEXT, phone TEXT, status TEXT DEFAULT 'new',
    handled_by TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS questions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER, question TEXT, answer TEXT, audio_file_id TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS reminders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER, remind_at TEXT, kind TEXT, sent INTEGER DEFAULT 0
);
"""

SCHEMA += """
CREATE TABLE IF NOT EXISTS media(
    id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT, title TEXT, kind TEXT,
    file TEXT, status TEXT DEFAULT 'processing', created_at TEXT
);
"""

_conn: aiosqlite.Connection | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def day_bounds_utc() -> tuple[str, str]:
    """Toshkent vaqti bo'yicha bugungi kunning UTC chegaralari."""
    n = datetime.now(TZ)
    start = n.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    f = lambda d: d.astimezone(timezone.utc).isoformat(timespec="seconds")
    return f(start), f(end)


async def init() -> None:
    global _conn
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.executescript(SCHEMA)
    await _conn.commit()


async def close() -> None:
    if _conn:
        await _conn.close()


async def _exec(sql: str, args: tuple = ()) -> int:
    cur = await _conn.execute(sql, args)
    await _conn.commit()
    last = cur.lastrowid
    await cur.close()
    return last


async def _one(sql: str, args: tuple = ()):
    cur = await _conn.execute(sql, args)
    row = await cur.fetchone()
    await cur.close()
    return dict(row) if row else None


async def _all(sql: str, args: tuple = ()) -> list[dict]:
    cur = await _conn.execute(sql, args)
    rows = await cur.fetchall()
    await cur.close()
    return [dict(r) for r in rows]


async def _update(table: str, key_col: str, key, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)  # kalitlar kod ichidan keladi, foydalanuvchidan emas
    await _exec(f"UPDATE {table} SET {cols} WHERE {key_col}=?", (*fields.values(), key))


# ------------------------------------------------------------------ users
async def upsert_user(tg_id: int, username: str | None, full_name: str, referred_by: int | None = None) -> bool:
    """Yangi foydalanuvchi bo'lsa True qaytaradi."""
    if await _one("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,)):
        await _exec("UPDATE users SET username=?, full_name=?, last_seen=?, blocked_bot=0 WHERE tg_id=?",
                    (username, full_name, now(), tg_id))
        return False
    if referred_by == tg_id or not (referred_by and await get_user(referred_by)):
        referred_by = None
    await _exec("INSERT INTO users(tg_id,username,full_name,referred_by,created_at,last_seen) VALUES(?,?,?,?,?,?)",
                (tg_id, username, full_name, referred_by, now(), now()))
    return True


async def get_user(tg_id: int):
    return await _one("SELECT * FROM users WHERE tg_id=?", (tg_id,))


async def update_user(tg_id: int, **fields) -> None:
    await _update("users", "tg_id", tg_id, **fields)


async def ref_count(tg_id: int) -> int:
    r = await _one("SELECT COUNT(*) c FROM users WHERE referred_by=? AND phone IS NOT NULL", (tg_id,))
    return r["c"]


async def active_user_ids() -> list[int]:
    rows = await _all("SELECT tg_id FROM users WHERE banned=0 AND blocked_bot=0")
    return [r["tg_id"] for r in rows]


async def list_users(limit: int = 100) -> list[dict]:
    return await _all("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,))


# ------------------------------------------------------------ appointments
async def create_appointment(**f) -> int:
    f["created_at"] = f["updated_at"] = now()
    cols = ",".join(f)
    marks = ",".join("?" * len(f))
    return await _exec(f"INSERT INTO appointments({cols}) VALUES({marks})", tuple(f.values()))


async def get_appointment(app_id: int):
    return await _one("SELECT * FROM appointments WHERE id=?", (app_id,))


async def update_appointment(app_id: int, **fields) -> None:
    fields["updated_at"] = now()
    await _update("appointments", "id", app_id, **fields)


async def list_appointments(status: str | None = None, today: bool = False, limit: int = 20) -> list[dict]:
    where, args = [], []
    if status:
        where.append("status=?")
        args.append(status)
    if today:
        s, e = day_bounds_utc()
        where.append("((created_at>=? AND created_at<?) OR (scheduled_at>=? AND scheduled_at<?))")
        args += [s, e, s, e]
    sql = "SELECT * FROM appointments" + (" WHERE " + " AND ".join(where) if where else "")
    return await _all(sql + " ORDER BY id DESC LIMIT ?", (*args, limit))


async def add_app_msg(app_id: int, chat_id: int, message_id: int) -> None:
    await _exec("INSERT INTO app_msgs VALUES(?,?,?)", (app_id, chat_id, message_id))


async def app_msgs(app_id: int) -> list[dict]:
    return await _all("SELECT chat_id, message_id FROM app_msgs WHERE app_id=?", (app_id,))


# --------------------------------------------------------------- callbacks
async def open_callback(tg_id: int):
    return await _one("SELECT * FROM callbacks WHERE tg_id=? AND status='new'", (tg_id,))


async def create_callback(tg_id: int, name: str, phone: str) -> int:
    return await _exec("INSERT INTO callbacks(tg_id,name,phone,created_at) VALUES(?,?,?,?)",
                       (tg_id, name, phone, now()))


async def update_callback(cb_id: int, **fields) -> None:
    await _update("callbacks", "id", cb_id, **fields)


async def list_callbacks(status: str | None = None, limit: int = 20) -> list[dict]:
    if status:
        return await _all("SELECT * FROM callbacks WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
    return await _all("SELECT * FROM callbacks ORDER BY id DESC LIMIT ?", (limit,))


# --------------------------------------------------------------- questions
async def add_question(tg_id: int, question: str) -> int:
    return await _exec("INSERT INTO questions(tg_id,question,created_at) VALUES(?,?,?)", (tg_id, question, now()))


async def get_question(qid: int):
    return await _one("SELECT * FROM questions WHERE id=?", (qid,))


async def update_question(qid: int, **fields) -> None:
    await _update("questions", "id", qid, **fields)


async def list_questions(limit: int = 20) -> list[dict]:
    return await _all("""SELECT q.*, u.full_name, u.username, u.phone FROM questions q
                         LEFT JOIN users u ON u.tg_id=q.tg_id ORDER BY q.id DESC LIMIT ?""", (limit,))


# ---------------------------------------------------------------- settings
async def get_setting(key: str, default: str | None = None) -> str | None:
    r = await _one("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


async def set_setting(key: str, value: str) -> None:
    await _exec("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))


# --------------------------------------------------------------- reminders
async def clear_reminders(app_id: int) -> None:
    await _exec("DELETE FROM reminders WHERE app_id=? AND sent=0", (app_id,))


async def add_reminder(app_id: int, remind_at: str, kind: str) -> None:
    await _exec("INSERT INTO reminders(app_id,remind_at,kind) VALUES(?,?,?)", (app_id, remind_at, kind))


async def due_reminders() -> list[dict]:
    return await _all("""SELECT r.id rid, r.kind, a.* FROM reminders r JOIN appointments a ON a.id=r.app_id
                         WHERE r.sent=0 AND r.remind_at<=? AND a.status IN ('accepted','confirmed')""", (now(),))


async def mark_reminder_sent(rid: int) -> None:
    await _exec("UPDATE reminders SET sent=1 WHERE id=?", (rid,))


# ------------------------------------------------------------------- stats
async def stats() -> dict:
    s, e = day_bounds_utc()
    q = lambda sql, a=(): _one(sql, a)
    users = (await q("SELECT COUNT(*) c FROM users"))["c"]
    users_today = (await q("SELECT COUNT(*) c FROM users WHERE created_at>=? AND created_at<?", (s, e)))["c"]
    apps = await _all("SELECT status, COUNT(*) c FROM appointments GROUP BY status")
    by = {r["status"]: r["c"] for r in apps}
    apps_today = (await q("""SELECT COUNT(*) c FROM appointments WHERE
        (created_at>=? AND created_at<?) OR (scheduled_at>=? AND scheduled_at<?)""", (s, e, s, e)))["c"]
    calls_new = (await q("SELECT COUNT(*) c FROM callbacks WHERE status='new'"))["c"]
    questions = (await q("SELECT COUNT(*) c FROM questions"))["c"]
    return {
        "users": users, "users_today": users_today, "apps_total": sum(by.values()),
        "apps_new": by.get("new", 0), "apps_accepted": by.get("accepted", 0) + by.get("confirmed", 0),
        "apps_rejected": by.get("rejected", 0), "apps_time_changed": by.get("time_changed", 0),
        "apps_today": apps_today, "calls_new": calls_new, "questions": questions,
    }


# ------------------------------------------------------------------- media (saytga yuklangan fayllar)
async def add_media(section: str, title: str, kind: str, file: str) -> int:
    return await _exec("INSERT INTO media(section,title,kind,file,created_at) VALUES(?,?,?,?,?)",
                       (section, title, kind, file, now()))


async def get_media(mid: int):
    return await _one("SELECT * FROM media WHERE id=?", (mid,))


async def update_media(mid: int, **fields) -> None:
    await _update("media", "id", mid, **fields)


async def list_media(ready_only: bool = True) -> list[dict]:
    if ready_only:
        return await _all("SELECT * FROM media WHERE status='ready' ORDER BY id DESC")
    return await _all("SELECT * FROM media ORDER BY id DESC")


async def delete_media(mid: int) -> None:
    await _exec("DELETE FROM media WHERE id=?", (mid,))
