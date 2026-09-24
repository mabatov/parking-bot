import asyncio
import io
import time

from loguru import logger
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from camera import CameraError, capture_frame
from config import config
from database.connection import wait_for_db, get_async_session_maker
from database.sql_operations import SqlOperations
from parking_analysis import AnalysisError, analyze_parking, prepare_image, render_result

# Клавиатура для пользователя
buttons = ["Получить фото 📸"]
if config.openai_api_key:
    buttons.append("Найти места 🅿️")
USER_KEYBOARD = ReplyKeyboardMarkup([buttons], resize_keyboard=True)
parking_lock = asyncio.Lock()
last_analysis_at = float("-inf")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username

    log_msg = f"Команда /start от пользователя: {user_id} @{username}"
    logger.info(log_msg)
    await send_log(log_msg)

    if await sql_operations.check_user_access(user_id):
        await update.message.reply_text(
            "Добро пожаловать! Можно получить фото или оценить занятость парковки.",
            reply_markup=USER_KEYBOARD
        )
    else:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        await send_log(f"У пользователя нет доступа: {user_id} @{username}")


async def handle_photo_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username

    log_msg = f"Запрос фото от пользователя: {user_id} @{username}"
    logger.info(log_msg)
    await send_log(log_msg)

    if not await sql_operations.check_user_access(user_id):
        await update.message.reply_text("У вас нет доступа к фото.")
        log_msg = f"Пользователь {user_id} @{username} запросил фото, но не имеет доступа."
        logger.warning(log_msg)
        await send_log(log_msg)
        return

    try:
        frame = await capture_frame(upscale=True)
        with io.BytesIO(frame) as photo:
            photo.name = "photo.jpg"
            await update.message.reply_photo(photo=photo)
    except CameraError as exc:
        await update.message.reply_text(str(exc))
        logger.warning("Ошибка камеры при отправке фото: {}", type(exc).__name__)
        return

    log_msg = f"Фото отправлено пользователю: {user_id} @{username}"
    logger.info(log_msg)
    await send_log(log_msg)


async def handle_parking_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global last_analysis_at

    user_id = update.effective_user.id
    if not await sql_operations.check_user_access(user_id):
        await update.message.reply_text("У вас нет доступа к снимкам парковки.")
        return
    if not config.openai_api_key:
        await update.message.reply_text("Анализ парковки ещё не настроен: нужен ключ OpenAI API.")
        return
    if parking_lock.locked():
        await update.message.reply_text("Сейчас обрабатывается другой кадр. Попробуйте чуть позже.")
        return

    async with parking_lock:
        remaining = config.parking_cooldown_seconds - (time.monotonic() - last_analysis_at)
        if remaining > 0:
            await update.message.reply_text(f"Новый анализ будет доступен через {int(remaining) + 1} с.")
            return
        await update.message.reply_text("Получаю кадр и проверяю парковку…")
        try:
            frame = await capture_frame()
            image = prepare_image(frame)
            last_analysis_at = time.monotonic()
            analysis = await analyze_parking(image, config.openai_api_key, config.openai_model)
            if not analysis.spaces:
                await update.message.reply_text("На этом кадре не удалось выделить парковочные места. Попробуйте другой ракурс или освещение.")
                return

            photo = render_result(image, analysis)
            free, occupied, unknown = (analysis.count(status) for status in ("free", "occupied", "unknown"))
            caption = (f"Оценка по кадру: 🟢 свободно {free}, "
                       f"🔴 занято {occupied}, 🟡 неясно {unknown}. "
                       "Проверьте подсвеченные места на снимке.")
            if analysis.note:
                caption += f"\n{analysis.note}"
            with io.BytesIO(photo) as output:
                output.name = "parking.jpg"
                await update.message.reply_photo(photo=output, caption=caption[:1000])
            await send_log(f"Анализ парковки для {user_id}: свободно {free}, занято {occupied}, неясно {unknown}")
        except (CameraError, AnalysisError) as exc:
            logger.warning("Анализ парковки завершился ошибкой: {}", type(exc).__name__)
            await update.message.reply_text(str(exc))


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
        log_msg = f"Несанкционированная попытка удаления пользователя от {user_id} @{username}"
        logger.warning(log_msg)
        await send_log(log_msg)


async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    log_msg = f"Команда /list_users от администратора: {user_id} @{username}"
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
        log_msg = f"Несанкционированная попытка запроса списка пользователей от {user_id} @{username}"
        logger.warning(log_msg)
        await send_log(log_msg)

async def send_log(message: str):
    log_bot = Bot(token=config.logging_bot_token)
    log_chat_id = config.admin_telegram_id
    try:
        await log_bot.send_message(chat_id=log_chat_id, text=f"[LOG] {message}")
    except Exception as e:
        logger.warning(f"Не удалось отправить лог в лог-бота: {e}")


if __name__ == "__main__":
    # Ожидаем, пока база данных не станет доступна
    wait_for_db()
    sql_operations = SqlOperations(session_maker=get_async_session_maker)

    app = ApplicationBuilder().token(config.bot_token).concurrent_updates(4).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("photo", handle_photo_request))
    app.add_handler(CommandHandler("parking", handle_parking_request))
    app.add_handler(CommandHandler("add_user", add_user_command))
    app.add_handler(CommandHandler("remove_user", remove_user_command))
    app.add_handler(CommandHandler("list_users", list_users_command))

    # Обработка кнопки "Получить фото"
    app.add_handler(MessageHandler(filters.Text("Получить фото 📸"), handle_photo_request))
    app.add_handler(MessageHandler(filters.Text("Найти места 🅿️"), handle_parking_request))

    logger.info("Бот запущен.")
    app.run_polling()
