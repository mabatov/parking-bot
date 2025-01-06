import os
import logging
import cv2
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import time
import psycopg2
from database import init_db, check_user_access, add_user, remove_user, get_all_users


def wait_for_db():
    while True:
        try:
            # Попытка подключиться к базе данных
            conn = psycopg2.connect(
                dbname="parking_bot",
                user="postgres",
                password="postgres",
                host="db",
                port="5432"
            )
            conn.close()  # Закрываем соединение, так как оно нам не нужно
            break  # Если соединение прошло успешно, выходим из цикла
        except psycopg2.OperationalError:
            print("Waiting for database...")
            time.sleep(5)  # Повторная попытка через 5 секунд

# Ожидаем, пока база данных не станет доступна
wait_for_db()

# Теперь можно инициализировать БД
init_db()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
RTSP_URL = os.getenv("RTSP_URL")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Клавиатура для пользователя
USER_KEYBOARD = ReplyKeyboardMarkup([["Получить фото 📸"]], resize_keyboard=True)


async def start(update: Update, context) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /start от пользователя: {user_id} ({username})")
    if check_user_access(user_id):
        await update.message.reply_text(
            "Добро пожаловать! Нажмите на кнопку ниже, чтобы получить фото.",
            reply_markup=USER_KEYBOARD
        )
    else:
        await update.message.reply_text("У вас нет доступа к этому боту.")


async def get_photo_from_rtsp() -> str:
    cap = cv2.VideoCapture(RTSP_URL)
    ret, frame = cap.read()
    if ret:
        photo_path = "current_parking.jpg"
        cv2.imwrite(photo_path, frame)
        # Отправка фото в чат
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(photo_path, 'rb'))
    else:
        await update.message.reply_text("Не удалось получить фото.")
    cap.release()


async def handle_photo_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Запрос фото от пользователя: {user_id} ({username})")
    if check_user_access(user_id):
        photo_path = await get_photo_from_rtsp()
        if photo_path:
            await update.message.reply_photo(photo=open(photo_path, 'rb'))
            logger.info(f"Фото отправлено пользователю: {user_id} ({username})")
        else:
            await update.message.reply_text("Не удалось получить фото с камеры.")
            logger.warning(f"Не удалось отправить фото пользователю: {user_id} ({username})")
    else:
        await update.message.reply_text("У вас нет доступа к фото.")
        logger.warning(f"Пользователь {user_id} ({username}) запросил фото, но не имеет доступа.")


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /add_user от администратора: {user_id} ({username})")
    if user_id == ADMIN_ID:
        if context.args:
            new_user_id = int(context.args[0])
            if add_user(new_user_id):
                await update.message.reply_text(f"Пользователь {new_user_id} добавлен.")
                logger.info(f"Пользователь {new_user_id} добавлен в список доступа.")
            else:
                await update.message.reply_text("Этот пользователь уже есть в базе.")
                logger.info(f"Пользователь {new_user_id} уже был в списке.")
        else:
            await update.message.reply_text("Используйте: /add_user <id>")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка добавления пользователя от {user_id} ({username})")


async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /remove_user от администратора: {user_id} ({username})")
    if user_id == ADMIN_ID:
        if context.args:
            del_user_id = int(context.args[0])
            if remove_user(del_user_id):
                await update.message.reply_text(f"Пользователь {del_user_id} удален.")
                logger.info(f"Пользователь {del_user_id} удален из списка доступа.")
            else:
                await update.message.reply_text("Этот пользователь не найден.")
                logger.info(f"Пользователь {del_user_id} не найден в списке.")
        else:
            await update.message.reply_text("Используйте: /remove_user <id>")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка удаления пользователя от {user_id} ({username})")


async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info(f"Команда /list_users от администратора: {user_id} ({username})")
    if user_id == ADMIN_ID:
        users = get_all_users()
        if users:
            user_list = "\n".join([str(user.telegram_id) for user in users])
            await update.message.reply_text(f"Список пользователей:\n{user_list}")
            logger.info(f"Администратор запросил список пользователей. Количество: {len(users)}")
        else:
            await update.message.reply_text("Список пользователей пуст.")
            logger.info("Список пользователей пуст.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        logger.warning(f"Несанкционированная попытка запроса списка пользователей от {user_id} ({username})")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_user", add_user_command))
    app.add_handler(CommandHandler("remove_user", remove_user_command))
    app.add_handler(CommandHandler("list_users", list_users_command))

    # Обработка кнопки "Получить фото"
    app.add_handler(MessageHandler(filters.Text("Получить фото 📸"), handle_photo_request))

    logger.info("Бот запущен.")
    app.run_polling()
