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

    log_msg = f"Команда /start от пользователя: {user_id} {username}"
    logger.info(log_msg)
    await send_log(log_msg)

    if await sql_operations.check_user_access(user_id):
        await update.message.reply_text(
            "Добро пожаловать! Нажмите на кнопку ниже, чтобы получить фото.",
            reply_markup=USER_KEYBOARD
        )
    else:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        await send_log(f"У пользователя нет доступа: {user_id} {username}")


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

    log_msg = f"Запрос фото от пользователя: {user_id} {username}"
    logger.info(log_msg)
    await send_log(log_msg)

    if await sql_operations.check_user_access(user_id):
        photo_path = await get_photo_from_rtsp()
        if photo_path:
            await update.message.reply_photo(photo=open(photo_path, 'rb'))
            log_msg = f"Фото отправлено пользователю: {user_id} {username}"
            logger.info(log_msg)
            await send_log(log_msg)

        else:
            await update.message.reply_text("Не удалось получить фото с камеры.")
            log_msg = f"Не удалось отправить фото пользователю: {user_id} {username}"
            logger.warning(log_msg)
            await send_log(log_msg)
    else:
        await update.message.reply_text("У вас нет доступа к фото.")
        log_msg = f"Пользователь {user_id} {username} запросил фото, но не имеет доступа."
        logger.warning(log_msg)
        await send_log(log_msg)


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /add_user от администратора: {user_id}")
    if user_id == config.admin_telegram_id:
        if context.args:
            new_user_id = int(context.args[0])
            if await sql_operations.add_user(new_user_id):
                await update.message.reply_text(f"Пользователь {new_user_id} добавлен.")
                log_msg = f"Пользователь {new_user_id} добавлен в список доступа."
                logger.info(log_msg)
                await send_log(log_msg)
            else:
                await update.message.reply_text("Этот пользователь уже есть в базе.")
                log_msg = f"Пользователь {new_user_id} уже был в списке."
                logger.info(log_msg)
                await send_log(log_msg)
        else:
            await update.message.reply_text("Используйте: /add_user <id>")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        log_msg = f"Несанкционированная попытка добавления пользователя от {user_id}"
        logger.warning(log_msg)
        await send_log(log_msg)


async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /remove_user от администратора: {user_id}")
    if user_id == config.admin_telegram_id:
        if context.args:
            del_user_id = int(context.args[0])
            if await sql_operations.remove_user(del_user_id):
                await update.message.reply_text(f"Пользователь {del_user_id} удален.")
                log_msg = f"Пользователь {del_user_id} удален из списка доступа."
                logger.info(log_msg)
                await send_log(log_msg)
            else:
                await update.message.reply_text("Этот пользователь не найден.")
                log_msg = f"Пользователь {del_user_id} не найден в списке."
                logger.info(log_msg)
                await send_log(log_msg)
        else:
            await update.message.reply_text("Используйте: /remove_user <id>")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        log_msg = f"Несанкционированная попытка удаления пользователя от {user_id} {username}"
        logger.warning(log_msg)
        await send_log(log_msg)


async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    log_msg = f"Команда /list_users от администратора: {user_id} {username}"
    logger.info(log_msg)
    await send_log(log_msg)
    if user_id == config.admin_telegram_id:
        users = await sql_operations.get_all_users()
        if users:
            user_list = "\n".join([str(user.get('telegram_id')) for user in users])
            await update.message.reply_text(f"Список пользователей:\n{user_list}")
            log_msg = f"Администратор запросил список пользователей. Количество: {len(users)}"
            logger.info(log_msg)
            await send_log(log_msg)
        else:
            await update.message.reply_text("Список пользователей пуст.")
            log_msg = f"Список пользователей пуст."
            logger.info(log_msg)
            await send_log(log_msg)
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        log_msg = f"Несанкционированная попытка запроса списка пользователей от {user_id} {username}"
        logger.warning(log_msg)
        await send_log(log_msg)

async def send_log(message: str):
    log_bot = config.logging_bot_token
    log_chat_id = config.admin_telegram_id
    try:
        await log_bot.send_message(chat_id=log_chat_id, text=f"[LOG] {message}")
    except Exception as e:
        logger.warning(f"Не удалось отправить лог в лог-бота: {e}")


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
