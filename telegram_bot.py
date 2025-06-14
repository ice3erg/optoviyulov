import os
import json
import sqlite3
import logging
import asyncio
import threading
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# Токен бота и ID чата продавца из переменных окружения
BOT_TOKEN = ("7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E")
SELLER_CHAT_ID = ("984066798")

# Логирование полученных переменных
logger.info(f"Полученные переменные: TELEGRAM_BOT_TOKEN={'установлен' if BOT_TOKEN else 'не установлен'}, SELLER_CHAT_ID={'установлен' if SELLER_CHAT_ID else 'не установлен'}")

# Подключение к базе данных
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Создание или обновление таблиц
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
        logger.info("Попытка инициализации бота...")
        bot = Bot(token=BOT_TOKEN)
        application = Application.builder().token(BOT_TOKEN).build()
        logger.info("Telegram бот успешно инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации бота: {str(e)}")
        bot = None
        application = None
else:
    logger.warning(
        f"Telegram бот не запущен: "
        f"TELEGRAM_BOT_TOKEN={'установлен' if BOT_TOKEN else 'не установлен'}, "
        f"SELLER_CHAT_ID={'установлен' if SELLER_CHAT_ID else 'не установлен'}"
    )

# Проверка, является ли пользователь админом
def is_admin(chat_id):
    cursor.execute("SELECT 1 FROM admins WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone() is not None

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat_id)
    if not is_admin(chat_id):
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return
    keyboard = [
        [InlineKeyboardButton("Открыть админ-панель", callback_data='open_admin')],
        [InlineKeyboardButton("Добавить админа", callback_data='add_admin')],
        [InlineKeyboardButton("Посмотреть заказы", callback_data='view_orders')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    if not is_admin(chat_id):
        await query.edit_message_text("У вас нет доступа к этому боту.")
        return

    if query.data == 'open_admin':
        admin_url = "https://optoviyulov.onrender.com/admin"  # Замените на ваш URL
        await query.edit_message_text(f"Открыть админ-панель: [Нажмите здесь]({admin_url})", parse_mode='Markdown')
    elif query.data == 'add_admin':
        await query.edit_message_text("Введите chat_id нового админа")
        context.user_data['mode'] = 'add_admin'
    elif query.data == 'view_orders':
        cursor.execute("SELECT id, user_id, total_price, status, created_at FROM orders")
        orders = cursor.fetchall()
        if orders:
            message = "Список заказов:\n" + "\n".join([f"ID: {o[0]}, Пользователь: {o[1]}, Сумма: {o[2]} ₽, Статус: {o[3]}, Дата: {o[4]}" for o in orders])
        else:
            message = "Список заказов пуст."
        await query.edit_message_text(message)

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat_id)
    if not is_admin(chat_id) or 'mode' not in context.user_data:
        return
    text = update.message.text
    mode = context.user_data['mode']
    try:
        if mode == 'add_admin':
            new_admin_id = int(text.strip())
            cursor.execute("INSERT OR IGNORE INTO admins (chat_id) VALUES (?)", (new_admin_id,))
            conn.commit()
            await update.message.reply_text(f"Админ с chat_id {new_admin_id} добавлен успешно!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}. Проверьте формат данных.")
    finally:
        del context.user_data['mode']

async def send_order_notification(order_data):
    """Отправка уведомления о новом заказе продавцу."""
    if not bot or not SELLER_CHAT_ID:
        logger.warning("Уведомление не отправлено: бот не инициализирован или SELLER_CHAT_ID не установлен")
        return
    try:
        logger.info(f"Попытка отправки уведомления в чат {SELLER_CHAT_ID}")
        message = (
            f"Новый заказ!\n"
            f"ID: {order_data['id']}\n"
            f"Пользователь: {order_data['user_id']}\n"
            f"Товары: {json.dumps(order_data['products'], ensure_ascii=False)}\n"
            f"Сумма: {order_data['total_price']} ₽\n"
            f"Статус: {order_data['status']}\n"
            f"Дата: {order_data['created_at']}"
        )
        await bot.send_message(chat_id=SELLER_CHAT_ID, text=message)
        logger.info(f"Уведомление о заказе {order_data['id']} отправлено в чат {SELLER_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {str(e)}")

async def start_bot():
    """Запуск бота с polling."""
    if not application:
        logger.warning("Бот не запущен: application не инициализирован")
        return
    try:
        logger.info("Запуск бота с polling...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
        logger.info("Telegram бот запущен")
        await application.updater.idle()
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {str(e)}")

def run_bot_in_background():
    """Запуск бота в отдельном потоке."""
    if not application:
        logger.warning("Бот не запущен в фоновом режиме: application не инициализирован")
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())
    loop.run_forever()

if __name__ == "__main__":
    run_bot_in_background()
if __name__ == "__main__":
    run_bot_in_background()
