"""Humo Med bot — ishga tushirish: Telegram bot + sayt uchun API + eslatmalar bitta jarayonda."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiohttp import web

import api
import config
import db
import handlers_admin
import handlers_user
import owner
import services
from gate import Gate


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylga yozing (README.md ga qarang).")

    await db.init()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(Gate())
    dp.callback_query.outer_middleware(Gate())
    dp.include_router(owner.router)  # owner: support va tashxis buyruqlari
    dp.include_router(handlers_admin.router)  # admin avval: /admin, ariza tugmalari, kutilayotgan matnlar
    dp.include_router(handlers_user.router)

    # Sayt (admin panel) uchun API
    runner = web.AppRunner(api.make_app(bot))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.PORT).start()
    logging.info("API ishga tushdi: port %s", config.PORT)

    reminders = asyncio.create_task(services.reminder_loop(bot))
    await bot.set_my_commands([BotCommand(command="start", description="Boshlash / Start"),
                               BotCommand(command="menu", description="Menyu / Меню")])
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        await runner.cleanup()
        await services.close_http()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
