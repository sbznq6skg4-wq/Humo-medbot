"""Tugmalar (inline klaviaturalar)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

import config
from texts import tr


def cb(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


def web_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


def webapp_url(lang: str) -> str:
    sep = "&" if "?" in config.WEBAPP_URL else "?"
    return f"{config.WEBAPP_URL}{sep}lang={lang}"


def lang_kb() -> InlineKeyboardMarkup:
    return kb([cb("🇺🇿 O'zbekcha", "lang:uz"), cb("🇷🇺 Русский", "lang:ru"), cb("🇬🇧 English", "lang:en")])


def main_menu(lang: str, admin: bool = False) -> InlineKeyboardMarkup:
    t = lambda k: tr(lang, k)
    rows = [
        [web_btn(t("m_app"), webapp_url(lang))],
        [cb(t("m_book"), "book")],
        [cb(t("m_doctors"), "menu:doctors"), cb(t("m_wards"), "menu:wards")],
        [cb(t("m_about"), "menu:about"), cb(t("m_hem"), "menu:hem")],
        [cb(t("m_loc"), "menu:loc"), cb(t("m_call"), "menu:call")],
        [cb(t("m_ai"), "menu:ai"), cb(t("m_faq"), "menu:faq")],
        [cb(t("m_ref"), "menu:ref"), cb(t("m_support"), "support_help")],
        [cb(t("m_lang"), "menu:lang")],
    ]
    if admin:  # faqat adminlarga ko'rinadi
        rows.append([web_btn(t("m_admin"), webapp_url(lang))])
    return kb(*rows)


def back_kb(lang: str, extra: list[InlineKeyboardButton] | None = None) -> InlineKeyboardMarkup:
    rows = ([extra] if extra else []) + [[cb(tr(lang, "back"), "menu:main")]]
    return kb(*rows)


def book_back_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([cb(tr(lang, "m_book"), "book")], [cb(tr(lang, "back"), "menu:main")])


def wards_kb(lang: str) -> InlineKeyboardMarkup:
    return kb(
        [cb(tr(lang, "w_normal"), "ward:normal")],
        [cb(tr(lang, "w_lux2"), "ward:lux2")],
        [cb(tr(lang, "w_lux3"), "ward:lux3")],
        [cb(tr(lang, "back"), "menu:main")],
    )


def about_kb(lang: str) -> InlineKeyboardMarkup:
    t = lambda k: tr(lang, k)
    return kb(
        [cb(t("a_work"), "about:work"), cb(t("a_laser"), "about:laser")],
        [cb(t("a_certs"), "about:certs"), cb(t("a_patients"), "about:patients")],
        [cb(t("a_reception"), "about:reception")],
        [cb(t("m_book"), "book")],
        [cb(t("back"), "menu:main")],
    )


def hem_kb(lang: str) -> InlineKeyboardMarkup:
    return kb(
        [cb(tr(lang, "h_bleed"), "hem:bleed")],
        [cb(tr(lang, "h_start"), "hem:start")],
        [cb(tr(lang, "h_unknown"), "hem:unknown")],
        [cb(tr(lang, "back"), "menu:main")],
    )


def doctor_pick_kb(lang: str) -> InlineKeyboardMarkup:
    rows = [[cb(d["name"], f"bdoc:{k}")] for k, d in config.DOCTORS.items()]
    rows.append([cb(tr(lang, "b_any"), "bdoc:any")])
    return kb(*rows)


def stage_kb(lang: str) -> InlineKeyboardMarkup:
    return kb(
        [cb(tr(lang, "h_bleed"), "bstage:bleed")],
        [cb(tr(lang, "h_start"), "bstage:start")],
        [cb(tr(lang, "h_unknown"), "bstage:unknown")],
    )


def lang_names_for_doctor(key: str | None) -> str:
    if key and key in config.DOCTORS:
        return config.DOCTORS[key]["name"]
    return "—"
