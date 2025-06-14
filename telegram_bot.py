import os
import json
import sqlite3
import logging
import asyncio
import threading
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# Конфигурация
BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"
SELLER_CHAT_ID = 984066798  # int, не строка

# Подключение к БД
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS admins (chat_id INTEGER PRIMARY KEY)''')
cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (SELLER_CHAT_ID,))
conn.commit()

# Инициализация бота
bot = None
application = None
if BOT_TOKEN and SELLER_CHAT_ID:
    try:
        logger.info("Инициализация бота...")
        bot = Bot(token=BOT_TOKEN)
        application = Application.builder().token(BOT_TOKEN).build()
    except Exception as e:
        logger.error(f"Ошибка инициализации: {str(e)}")
else:
    logger.warning("BOT_TOKEN или SELLER_CHAT_ID не установлен")

# Проверка на админа
def is_admin(chat_id):
    cursor.execute("SELECT 1 FROM admins WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone() is not None

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if not is_admin(chat_id):
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return
    keyboard = [
        [InlineKeyboardButton("📂 Открыть админ-панель", callback_data='open_admin')],
        [InlineKeyboardButton("➕ Добавить админа", callback_data='add_admin')],
        [InlineKeyboardButton("📦 Посмотреть заказы", callback_data='view_orders')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if not is_admin(chat_id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return

    if query.data == 'open_admin':
        admin_url = "https://optoviyulov.onrender.com/admin"
        await query.edit_message_text(f"Открыть админ-панель: [Нажмите здесь]({admin_url})", parse_mode='Markdown')
    elif query.data == 'add_admin':
        await query.edit_message_text("Введите chat_id нового админа:")
        context.user_data['mode'] = 'add_admin'
    elif query.data == 'view_orders':
        cursor.execute("SELECT id, user_id, total_price, status, created_at FROM orders")
        orders = cursor.fetchall()
        if orders:
            message = "Список заказов:\n" + "\n".join([
                f"🆔 {o[0]} | 👤 {o[1]} | 💰 {o[2]}₽ | 📌 {o[3]} | 📅 {o[4]}"
                for o in orders
            ])
        else:
            message = "Список заказов пуст."
        await query.edit_message_text(message)

# Ввод текста
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if not is_admin(chat_id) or 'mode' not in context.user_data:
        return
    text = update.message.text.strip()
    mode = context.user_data['mode']
    try:
        if mode == 'add_admin':
            new_admin_id = int(text)
            cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (new_admin_id,))
            conn.commit()
            await update.message.reply_text(f"✅ Админ с chat_id {new_admin_id} добавлен!")
        else:
            await update.message.reply_text("⚠️ Неизвестный режим.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        del context.user_data['mode']

# /admins — список админов
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if not is_admin(chat_id):
        await update.message.reply_text("⛔ У вас нет доступа.")
        return
    cursor.execute("SELECT chat_id FROM admins")
    admins = cursor.fetchall()
    message = "👑 Список админов:\n" + "\n".join([f"- {a[0]}" for a in admins]) if admins else "Список админов пуст."
    await update.message.reply_text(message)

# Отправка уведомлений всем админам
async def send_order_notification(order_data):
    if not bot:
        logger.warning("❗ Бот не инициализирован — уведомление не отправлено")
        return

    message = (
        f"📦 *Новый заказ!*\n\n"
        f"*ID:* {order_data['id']}\n"
        f"*Пользователь:* {order_data['user_id']}\n"
        f"*Товары:* `{json.dumps(order_data['products'], ensure_ascii=False)}`\n"
        f"*Сумма:* {order_data['total_price']} ₽\n"
        f"*Статус:* {order_data['status']}\n"
        f"*Дата:* {order_data['created_at']}"
    )

    try:
        cursor.execute("SELECT chat_id FROM admins")
        admins = cursor.fetchall()
        for admin in admins:
            try:
                await bot.send_message(chat_id=admin[0], text=message, parse_mode='Markdown')
                logger.info(f"Уведомление отправлено админу {admin[0]}")
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение админу {admin[0]}: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при рассылке уведомлений: {str(e)}")

# Запуск бота
async def start_bot():
    if not application:
        logger.warning("❗ Application не инициализирован")
        return
    try:
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admins", list_admins))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("✅ Бот запущен")
        await application.updater.idle()
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {str(e)}")

# Фоновый запуск
def run_bot_in_background():
    if not application:
        logger.warning("⛔ Application не инициализирован")
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())
    loop.run_forever()

# Запуск
if __name__ == "__main__":
    run_bot_in_background()
