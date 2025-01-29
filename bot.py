from loguru import logger
import cv2
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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


@dp.message_handler(commands=["start"])
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


async def get_photo_from_rtsp():
    logger.info("Подключение к RTSP потоку...")
    cap = cv2.VideoCapture(config.rtsp_url)
    if not cap.isOpened():
        logger.error("Не удалось открыть RTSP поток.")
        raise Exception("Не удалось открыть RTSP поток.")

    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise Exception("Не удалось получить кадр из потока.")

    photo_path = "photo.jpg"
    cv2.imwrite(photo_path, frame)
    cap.release()

    return photo_path


@dp.message_handler(F.text == "Получить фото 📸")
async def handle_photo_request(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Запрос фото от пользователя: {user_id} ({username})")
    if await sql_operations.check_user_access(user_id):
        try:
            photo_path = await get_photo_from_rtsp()
            with open(photo_path, 'rb') as photo:
                await message.answer_photo(photo)
            logger.info(f"Фото отправлено пользователю: {user_id} ({username})")
        except Exception as e:
            await message.reply("Не удалось получить фото с камеры.")
            logger.warning(f"Не удалось отправить фото пользователю: {user_id} ({username}). Ошибка: {e}")
    else:
        await message.reply("У вас нет доступа к фото.")
        logger.warning(f"Пользователь {user_id} ({username}) запросил фото, но не имеет доступа.")


@dp.message_handler(commands=["add_user"])
async def add_user_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /add_user от администратора: {user_id} ({username})")
    if user_id == config.admin_telegram_id:
        if message.get_args():
            try:
                new_user_id = int(message.get_args())
                if await sql_operations.add_user(new_user_id):
                    await message.reply(f"Пользователь {new_user_id} добавлен.")
                    logger.info(f"Пользователь {new_user_id} добавлен в список доступа.")
                else:
                    await message.reply("Этот пользователь уже есть в базе.")
                    logger.info(f"Пользователь {new_user_id} уже был в списке.")
            except ValueError:
                await message.reply("Пожалуйста, укажите корректный ID пользователя.")
        else:
            await message.reply("Используйте: /add_user <id>")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка добавления пользователя от {user_id} ({username})")


@dp.message_handler(commands=["remove_user"])
async def remove_user_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /remove_user от администратора: {user_id} ({username})")
    if user_id == config.admin_telegram_id:
        if message.get_args():
            try:
                del_user_id = int(message.get_args())
                if await sql_operations.remove_user(del_user_id):
                    await message.reply(f"Пользователь {del_user_id} удален.")
                    logger.info(f"Пользователь {del_user_id} удален из списка доступа.")
                else:
                    await message.reply("Этот пользователь не найден.")
                    logger.info(f"Пользователь {del_user_id} не найден в списке.")
            except ValueError:
                await message.reply("Пожалуйста, укажите корректный ID пользователя.")
        else:
            await message.reply("Используйте: /remove_user <id>")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка удаления пользователя от {user_id} ({username})")


@dp.message_handler(commands=["list_users"])
async def list_users_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Команда /list_users от администратора: {user_id} ({username})")
    if user_id == config.admin_telegram_id:
        users = await sql_operations.get_all_users()
        if users:
            user_list = "\n".join([str(user.get('telegram_id')) for user in users])
            await message.reply(f"Список пользователей:\n{user_list}")
            logger.info(f"Администратор запросил список пользователей. Количество: {len(users)}")
        else:
            await message.reply("Список пользователей пуст.")
            logger.info("Список пользователей пуст.")
    else:
        await message.reply("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка запроса списка пользователей от {user_id} ({username})")


if __name__ == "__main__":
    # Ожидаем, пока база данных не станет доступна
    wait_for_db()
    logger.info("Бот запущен.")

    # Запуск бота через Dispatcher
    import asyncio

    asyncio.run(dp.start_polling())
