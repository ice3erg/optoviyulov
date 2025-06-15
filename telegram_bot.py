import asyncio
import logging
import sqlite3
from fastapi import FastAPI
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"  # <-- Замени на свой токен!
DB_PATH = "products.db"

# --- Инициализация базы данных ---
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    chat_id INTEGER PRIMARY KEY
)
""")
conn.commit()

START_ADMIN_ID = 984066798
cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (START_ADMIN_ID,))
conn.commit()

# --- FastAPI-приложение ---
app = FastAPI()
application = ApplicationBuilder().token(BOT_TOKEN).build()


def is_admin(chat_id: int) -> bool:
    cursor.execute("SELECT 1 FROM admins WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone() is not None


# --- Хэндлеры Telegram бота ---

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
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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
        url = "https://optoviyulov.onrender.com/admin"
        await query.edit_message_text(f"[Открыть админ-панель]({url})", parse_mode="Markdown")
    elif data == "add_admin":
        context.user_data["mode"] = "add_admin"
        await query.edit_message_text("Введите chat_id нового админа:")
    elif data == "list_admins":
        cursor.execute("SELECT chat_id FROM admins")
        admins = cursor.fetchall()
        msg = "Список админов:\n" + "\n".join(str(row[0]) for row in admins)
        await query.edit_message_text(msg)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        return

    mode = context.user_data.get("mode")
    if mode == "add_admin":
        try:
            new_admin = int(update.message.text.strip())
            cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (new_admin,))
            conn.commit()
            await update.message.reply_text(f"✅ Админ {new_admin} добавлен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
        finally:
            context.user_data.pop("mode", None)


# Функция уведомления админов о заказе
async def send_order_notification(order_data: dict):
    cursor.execute("SELECT chat_id FROM admins")
    admins = cursor.fetchall()
    msg = (
        f"📦 Новый заказ:\n"
        f"ID: {order_data.get('id')}\n"
        f"Пользователь: {order_data.get('user_id')}\n"
        f"Товары: {order_data.get('products')}\n"
        f"Сумма: {order_data.get('total_price')} ₽\n"
        f"Статус: {order_data.get('status')}\n"
        f"Дата: {order_data.get('created_at')}"
    )
    for (admin_id,) in admins:
        try:
            await application.bot.send_message(chat_id=admin_id, text=msg)
        except Exception as e:
            logger.error(f"Ошибка при уведомлении {admin_id}: {e}")


# --- Регистрация хэндлеров ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


# --- Интеграция Telegram бота с FastAPI ---
@app.on_event("startup")
async def startup():
    asyncio.create_task(application.run_polling())
