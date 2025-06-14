import os
import json
import sqlite3
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"
DEFAULT_ADMIN_ID = 984066798  # int, не строка

DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Таблицы
cursor.execute('''CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
    chat_id INTEGER PRIMARY KEY
)''')

cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (DEFAULT_ADMIN_ID,))
conn.commit()

# Проверка, админ ли пользователь
def is_admin(chat_id: int) -> bool:
    cursor.execute("SELECT 1 FROM admins WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone() is not None

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return

    keyboard = [
        [InlineKeyboardButton("Открыть админ-панель", callback_data='open_admin')],
        [InlineKeyboardButton("Добавить админа", callback_data='add_admin')],
        [InlineKeyboardButton("Показать админов", callback_data='list_admins')],
        [InlineKeyboardButton("Посмотреть заказы", callback_data='view_orders')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Обработка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if not is_admin(chat_id):
        await query.edit_message_text("У вас нет доступа к этому боту.")
        return

    if query.data == 'open_admin':
        await query.edit_message_text("Админ-панель: https://optoviyulov.onrender.com/admin")
    elif query.data == 'add_admin':
        await query.edit_message_text("Введите chat_id нового админа:")
        context.user_data['mode'] = 'add_admin'
    elif query.data == 'list_admins':
        cursor.execute("SELECT chat_id FROM admins")
        rows = cursor.fetchall()
        text = "Список админов:\n" + "\n".join([str(r[0]) for r in rows])
        await query.edit_message_text(text)
    elif query.data == 'view_orders':
        cursor.execute("SELECT id, user_id, total_price, status, created_at FROM orders")
        orders = cursor.fetchall()
        if orders:
            message = "\n".join([
                f"ID: {o[0]}, Пользователь: {o[1]}, Сумма: {o[2]} ₽, Статус: {o[3]}, Дата: {o[4]}"
                for o in orders
            ])
        else:
            message = "Список заказов пуст."
        await query.edit_message_text(message)

# Текстовые ответы (например, добавление админа)
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_admin(chat_id):
        return

    if 'mode' not in context.user_data:
        return

    mode = context.user_data['mode']
    text = update.message.text.strip()

    if mode == 'add_admin':
        try:
            new_id = int(text)
            cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (new_id,))
            conn.commit()
            await update.message.reply_text(f"✅ Админ {new_id} добавлен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
        finally:
            context.user_data.pop('mode', None)

# Уведомление всем админам о заказе
async def send_order_notification(order_data):
    try:
        cursor.execute("SELECT chat_id FROM admins")
        admin_ids = [row[0] for row in cursor.fetchall()]
        message = (
            f"🛒 Новый заказ!\n"
            f"ID: {order_data['id']}\n"
            f"Пользователь: {order_data['user_id']}\n"
            f"Товары: {json.dumps(order_data['products'], ensure_ascii=False)}\n"
            f"Сумма: {order_data['total_price']} ₽\n"
            f"Статус: {order_data['status']}\n"
            f"Дата: {order_data['created_at']}"
        )
        for admin_id in admin_ids:
            await bot.send_message(chat_id=admin_id, text=message)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {str(e)}")

# Основной запуск
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

async def main():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
