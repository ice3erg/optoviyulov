import asyncio
import logging
import sqlite3
from fastapi import FastAPI
from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"
DB_PATH = "products.db"

# Инициализация БД
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    chat_id INTEGER PRIMARY KEY
)
""")
conn.commit()

# Добавим стартового админа, если нужно
START_ADMIN_ID = 984066798
cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (START_ADMIN_ID,))
conn.commit()

app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()


def is_admin(chat_id: int) -> bool:
    cursor.execute("SELECT 1 FROM admins WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone() is not None


# --- Хэндлеры бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("У вас нет доступа к боту.")
        return

    keyboard = [
        [InlineKeyboardButton("Открыть админ-панель", callback_data="open_admin")],
        [InlineKeyboardButton("Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton("Посмотреть всех админов", callback_data="list_admins")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    if not is_admin(chat_id):
        await query.answer()
        await query.edit_message_text("У вас нет доступа к боту.")
        return

    await query.answer()
    data = query.data

    if data == "open_admin":
        admin_url = "https://optoviyulov.onrender.com/admin"
        await query.edit_message_text(f"Открыть админ-панель: [Нажмите здесь]({admin_url})", parse_mode="Markdown")
    elif data == "add_admin":
        await query.edit_message_text("Введите chat_id нового админа")
        context.user_data["mode"] = "add_admin"
    elif data == "list_admins":
        cursor.execute("SELECT chat_id FROM admins")
        admins = cursor.fetchall()
        text = "Список админов:\n" + "\n".join(str(a[0]) for a in admins)
        await query.edit_message_text(text)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        return

    mode = context.user_data.get("mode")
    if mode == "add_admin":
        text = update.message.text.strip()
        try:
            new_admin_id = int(text)
            cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (new_admin_id,))
            conn.commit()
            await update.message.reply_text(f"Админ с chat_id {new_admin_id} успешно добавлен!")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при добавлении: {e}")
        finally:
            context.user_data.pop("mode", None)


async def send_order_notification(order_data: dict):
    """Отправить уведомление о новом заказе всем админам."""
    cursor.execute("SELECT chat_id FROM admins")
    admins = cursor.fetchall()
    message = (
        f"Новый заказ!\n"
        f"ID: {order_data.get('id')}\n"
        f"Пользователь: {order_data.get('user_id')}\n"
        f"Товары: {order_data.get('products')}\n"
        f"Сумма: {order_data.get('total_price')} ₽\n"
        f"Статус: {order_data.get('status')}\n"
        f"Дата: {order_data.get('created_at')}"
    )
    for (admin_chat_id,) in admins:
        try:
            await application.bot.send_message(chat_id=admin_chat_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору {admin_chat_id}: {e}")


# Добавляем хэндлеры
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))


# --- Запуск бота параллельно с FastAPI ---

async def run_bot():
    logger.info("Запускаем Telegram-бот...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram-бот запущен")
    # Ждём, чтобы не завершать таск
    await application.updater.idle()


@app.on_event("startup")
async def startup_event():
    # Запускаем бота в фоне
    asyncio.create_task(run_bot())


@app.get("/")
async def root():
    return {"message": "FastAPI с Telegram ботом работает"}


# Чтобы запустить:
# uvicorn main:app --host 0.0.0.0 --port 10000
