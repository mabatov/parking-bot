from loguru import logger
import cv2
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

from config import config
from database.connection import wait_for_db, async_session_maker
from database.sql_operations import SqlOperations

# Клавиатура для пользователя
USER_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Получить фото 📸")]], resize_keyboard=True
)

# Инициализация операций с базой данных
sql_operations = SqlOperations(session_maker=async_session_maker)

# Инициализация бота и диспетчера
bot = Bot(token=config.bot_token)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /start от пользователя: {user_id} ({username})")
    if await sql_operations.check_user_access(user_id):
        await message.reply(
            "Добро пожаловать! Нажмите на кнопку ниже, чтобы получить фото.",
            reply_markup=USER_KEYBOARD
        )
    else:
        await message.reply("У вас нет доступа к этому боту.")

# Синхронная функция получения фото
def capture_rtsp_frame():
    logger.info("Подключение к RTSP потоку...")
    cap = cv2.VideoCapture(config.rtsp_url)
    if not cap.isOpened():
        logger.error("Не удалось открыть RTSP поток.")
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret:
        logger.error("Не удалось получить кадр из потока.")
        return None

    photo_path = "photo.jpg"
    cv2.imwrite(photo_path, frame)
    return photo_path

# Асинхронный вызов синхронной функции
async def get_photo_from_rtsp():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, capture_rtsp_frame)

# Обработчик запроса фото
@dp.message(lambda message: message.text == "Получить фото 📸")
async def handle_photo_request(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Запрос фото от пользователя: {user_id} ({username})")
    if await sql_operations.check_user_access(user_id):
        try:
            photo_path = await get_photo_from_rtsp()
            if photo_path:
                with open(photo_path, 'rb') as photo:
                    await message.answer_photo(photo)
                logger.info(f"Фото отправлено пользователю: {user_id} ({username})")
            else:
                await message.reply("Не удалось получить фото с камеры.")
                logger.warning(f"Ошибка получения фото для {user_id} ({username})")
        except Exception as e:
            await message.reply("Не удалось получить фото с камеры.")
            logger.warning(f"Ошибка при отправке фото пользователю {user_id} ({username}): {e}")
    else:
        await message.reply("У вас нет доступа к фото.")
        logger.warning(f"Пользователь {user_id} ({username}) запросил фото, но не имеет доступа.")

if __name__ == "__main__":
    wait_for_db()
    logger.info("Бот запущен.")
    asyncio.run(dp.start_polling(bot))
