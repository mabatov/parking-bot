import functools
from loguru import logger
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram import F

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

# Пул потоков для работы с OpenCV
executor = ThreadPoolExecutor(max_workers=1)


async def start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /start от {user_id} ({username})")

    if await sql_operations.check_user_access(user_id):
        await message.reply("Добро пожаловать! Нажмите на кнопку ниже, чтобы получить фото.",
                            reply_markup=USER_KEYBOARD)
    else:
        await message.reply("У вас нет доступа к этому боту.")


dp.message.register(start, Command("start"))


def async_decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loops = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=5) as pool:
            return await loops.run_in_executor(pool, func, *args)

    return wrapper

@async_decorator
def get_photo_from_rtsp_sync():
    """Синхронная функция для получения кадра из RTSP-потока"""
    logger.info("Подключение к RTSP потоку...")
    cap = cv2.VideoCapture(config.rtsp_url)

    if not cap.isOpened():
        logger.error("Не удалось открыть RTSP поток.")
        cap.release()
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret:
        logger.error("Не удалось получить кадр из потока.")
        return None

    photo_path = "photo.jpg"
    cv2.imwrite(photo_path, frame)
    return photo_path


async def get_photo_from_rtsp():
    """Асинхронный вызов синхронной функции с OpenCV"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, get_photo_from_rtsp_sync)


async def handle_photo_request(message: types.Message):
    """Обработчик кнопки 'Получить фото 📸'"""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Запрос фото от {user_id} ({username})")

    if await sql_operations.check_user_access(user_id):
        try:
            photo_path = await get_photo_from_rtsp()
            if photo_path:
                with open(photo_path, 'rb') as photo:
                    await message.answer_photo(photo)
                logger.info(f"Фото отправлено пользователю: {user_id} ({username})")
            else:
                await message.reply("Ошибка при получении фото.")
        except Exception as e:
            logger.error(f"Ошибка при отправке фото: {e}")
            await message.reply("Не удалось получить фото с камеры.")
    else:
        await message.reply("У вас нет доступа к фото.")
        logger.warning(f"Пользователь {user_id} ({username}) запросил фото, но не имеет доступа.")


dp.message.register(handle_photo_request, F.text == "Получить фото 📸")


async def add_user_command(message: types.Message):
    """Обработчик команды /add_user"""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /add_user от {user_id} ({username})")

    if user_id == config.admin_telegram_id:
        args = message.text.split()
        if len(args) > 1:
            try:
                new_user_id = int(args[1])
                if await sql_operations.add_user(new_user_id):
                    await message.reply(f"Пользователь {new_user_id} добавлен.")
                    logger.info(f"Пользователь {new_user_id} добавлен в список доступа.")
                else:
                    await message.reply("Этот пользователь уже есть в базе.")
            except ValueError:
                await message.reply("Пожалуйста, укажите корректный ID пользователя.")
        else:
            await message.reply("Используйте: /add_user <id>")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")


dp.message.register(add_user_command, Command("add_user"))


async def remove_user_command(message: types.Message):
    """Обработчик команды /remove_user"""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /remove_user от {user_id} ({username})")

    if user_id == config.admin_telegram_id:
        args = message.text.split()
        if len(args) > 1:
            try:
                del_user_id = int(args[1])
                if await sql_operations.remove_user(del_user_id):
                    await message.reply(f"Пользователь {del_user_id} удален.")
                    logger.info(f"Пользователь {del_user_id} удален из списка доступа.")
                else:
                    await message.reply("Этот пользователь не найден.")
            except ValueError:
                await message.reply("Пожалуйста, укажите корректный ID пользователя.")
        else:
            await message.reply("Используйте: /remove_user <id>")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")


dp.message.register(remove_user_command, Command("remove_user"))


async def list_users_command(message: types.Message):
    """Обработчик команды /list_users"""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /list_users от {user_id} ({username})")

    if user_id == config.admin_telegram_id:
        users = await sql_operations.get_all_users()
        if users:
            user_list = "\n".join([str(user.get('telegram_id')) for user in users])
            await message.reply(f"Список пользователей:\n{user_list}")
        else:
            await message.reply("Список пользователей пуст.")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")


dp.message.register(list_users_command, Command("list_users"))


async def main():
    """Основная асинхронная функция"""
    wait_for_db()
    logger.info("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
