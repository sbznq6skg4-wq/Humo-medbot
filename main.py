import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

TOKEN = "8831226197:AAEI0WJO9qpYlfe-TW_xSBESCiYaenGXvc8"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Salom! Menga video yoki rasmlaringni yubor, senga ularning File ID kodlarini chiqarib beraman.")

# Videolar uchun
@dp.message(F.video)
async def get_video_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"Videoning File ID kodi:\n\n`{file_id}`", parse_mode="Markdown")

# Rasmlar uchun (eng sifatli hajmini oladi)
@dp.message(F.photo)
async def get_photo_id(message: types.Message):
    file_id = message.photo[-1].file_id
    await message.answer(f" Rasmlarning File ID kodi:\n\n`{file_id}`", parse_mode="Markdown")

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
