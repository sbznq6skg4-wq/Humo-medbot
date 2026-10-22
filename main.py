import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# Sening bot tokening
TOKEN = "8831226197:AAEI0WJO9qpYlfe-TW_xSBESCiYaenGXvc8"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# /start buyruqi kelganda ishlaydi
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Salom! Menga barcha promo-videolaringni yubor, men senga ularning File ID kodlarini chiqarib beraman.")

# Botga video yuborilganda ishlaydigan qism
@dp.message(F.video)
async def get_video_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"Mana bu videoning File ID kodi:\n\n`{file_id}`", parse_mode="Markdown")

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
