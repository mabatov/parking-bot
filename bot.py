from loguru import logger
import subprocess
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from config import config
from database.connection import wait_for_db, get_async_session_maker
from database.sql_operations import SqlOperations

# Клавиатура для пользователя
USER_KEYBOARD = ReplyKeyboardMarkup([["Получить фото 📸"]], resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /start от пользователя: {user_id}")
    if await sql_operations.check_user_access(user_id):
        await update.message.reply_text(
            "Добро пожаловать! Нажмите на кнопку ниже, чтобы получить фото.",
            reply_markup=USER_KEYBOARD
        )
    else:
        await update.message.reply_text("У вас нет доступа к этому боту.")


async def get_photo_from_rtsp():
    rtsp_url = config.rtsp_url
    output_path = "/photo.jpg"  # Путь к файлу
    try:
        logger.info("Подключение к RTSP потоку...")
        result = subprocess.run(
            [
                "ffmpeg", "-y", # Подтверждение перезаписи файла
                "-rtsp_transport", "tcp", # Захват RTSP-видеопотока по TCP
                "-i", rtsp_url,  # Подключаемся к камере
                "-frames:v", "1",  # Записываем только один кадр
                "-q:v", "1",  # Устанавливаем наилучшее качество JPEG (диапазон 1-31, где 1 — наилучшее)
                "-vf", "scale=iw*2:ih*2",  # Удваиваем разрешение для повышения детализации
                "-pix_fmt", "yuvj422p",  # Используем цветовое пространство с меньшим сжатием
                output_path  # Имя выходного файла
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return output_path
    except subprocess.CalledProcessError as e:
        raise Exception(f"Ошибка при получении кадра через ffmpeg: {e.stderr.decode()}")


async def handle_photo_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Запрос фото от пользователя: {user_id}")
    if await sql_operations.check_user_access(user_id):
        photo_path = await get_photo_from_rtsp()
        if photo_path:
            await update.message.reply_photo(photo=open(photo_path, 'rb'))
            logger.info(f"Фото отправлено пользователю: {user_id}")
        else:
            await update.message.reply_text("Не удалось получить фото с камеры.")
            logger.warning(f"Не удалось отправить фото пользователю: {user_id}")
    else:
        await update.message.reply_text("У вас нет доступа к фото.")
        logger.warning(f"Пользователь {user_id} запросил фото, но не имеет доступа.")


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /add_user от администратора: {user_id}")
    if user_id == config.admin_telegram_id:
        if context.args:
            new_user_id = int(context.args[0])
            if await sql_operations.add_user(new_user_id):
                await update.message.reply_text(f"Пользователь {new_user_id} добавлен.")
                logger.info(f"Пользователь {new_user_id} добавлен в список доступа.")
            else:
                await update.message.reply_text("Этот пользователь уже есть в базе.")
                logger.info(f"Пользователь {new_user_id} уже был в списке.")
        else:
            await update.message.reply_text("Используйте: /add_user <id>")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка добавления пользователя от {user_id}")


async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /remove_user от администратора: {user_id}")
    if user_id == config.admin_telegram_id:
        if context.args:
            del_user_id = int(context.args[0])
            if await sql_operations.remove_user(del_user_id):
                await update.message.reply_text(f"Пользователь {del_user_id} удален.")
                logger.info(f"Пользователь {del_user_id} удален из списка доступа.")
            else:
                await update.message.reply_text("Этот пользователь не найден.")
                logger.info(f"Пользователь {del_user_id} не найден в списке.")
        else:
            await update.message.reply_text("Используйте: /remove_user <id>")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка удаления пользователя от {user_id}")


async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /list_users от администратора: {user_id}")
    if user_id == config.admin_telegram_id:
        users = await sql_operations.get_all_users()
        if users:
            user_list = "\n".join([str(user.get('telegram_id')) for user in users])
            await update.message.reply_text(f"Список пользователей:\n{user_list}")
            logger.info(f"Администратор запросил список пользователей. Количество: {len(users)}")
        else:
            await update.message.reply_text("Список пользователей пуст.")
            logger.info("Список пользователей пуст.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка запроса списка пользователей от {user_id}")


if __name__ == "__main__":
    # Ожидаем, пока база данных не станет доступна
    wait_for_db()
    sql_operations = SqlOperations(session_maker=get_async_session_maker)

    app = ApplicationBuilder().token(config.bot_token).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_user", add_user_command))
    app.add_handler(CommandHandler("remove_user", remove_user_command))
    app.add_handler(CommandHandler("list_users", list_users_command))

    # Обработка кнопки "Получить фото"
    app.add_handler(MessageHandler(filters.Text("Получить фото 📸"), handle_photo_request))

    logger.info("Бот запущен.")
    app.run_polling()
