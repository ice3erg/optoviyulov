import os
import json
import sqlite3
import logging
import asyncio
import threading
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

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

# Создание таблицы admins, если она не существует
cursor.execute('''CREATE TABLE IF NOT EXISTS admins (chat_id INTEGER PRIMARY KEY)''')
# Добавление начального админа (SELLER_CHAT_ID)
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
        [InlineKeyboardButton("Добавить товар", callback_data='add_product')],
        [InlineKeyboardButton("Обновить товар", callback_data='update_product')],
        [InlineKeyboardButton("Удалить товар", callback_data='delete_product')],
        [InlineKeyboardButton("Просмотр товаров", callback_data='list_products')],
        [InlineKeyboardButton("Добавить админа", callback_data='add_admin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Админ-панель бота. Выберите действие:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    if not is_admin(chat_id):
        await query.edit_message_text("У вас нет доступа к этому боту.")
        return

    if query.data == 'add_product':
        await query.edit_message_text("Введите данные товара в формате: имя, цена, категория (через запятую)")
        context.user_data['mode'] = 'add_product'
    elif query.data == 'update_product':
        await query.edit_message_text("Введите ID товара и новую цену (через запятую)")
        context.user_data['mode'] = 'update_product'
    elif query.data == 'delete_product':
        await query.edit_message_text("Введите ID товара для удаления")
        context.user_data['mode'] = 'delete_product'
    elif query.data == 'list_products':
        cursor.execute("SELECT id, name, price, category FROM products")
        products = cursor.fetchall()
        if products:
            message = "Список товаров:\n" + "\n".join([f"ID: {p[0]}, Название: {p[1]}, Цена: {p[2]} ₽, Категория: {p[3]}" for p in products])
        else:
            message = "Список товаров пуст."
        await query.edit_message_text(message)
    elif query.data == 'add_admin':
        await query.edit_message_text("Введите chat_id нового админа")
        context.user_data['mode'] = 'add_admin'

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat_id)
    if not is_admin(chat_id) or 'mode' not in context.user_data:
        return
    text = update.message.text
    mode = context.user_data['mode']
    try:
        if mode == 'add_product':
            name, price, category = text.split(',', 2)
            price = float(price.strip())
            cursor.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (name.strip(), price, category.strip()))
            conn.commit()
            await update.message.reply_text(f"Товар {name} добавлен успешно!")
        elif mode == 'update_product':
            product_id, new_price = text.split(',', 1)
            new_price = float(new_price.strip())
            cursor.execute("UPDATE products SET price = ? WHERE id = ?", (new_price, int(product_id.strip())))
            conn.commit()
            await update.message.reply_text(f"Цена товара с ID {product_id} обновлена на {new_price} ₽.")
        elif mode == 'delete_product':
            product_id = int(text.strip())
            cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
            await update.message.reply_text(f"Товар с ID {product_id} удалён.")
        elif mode == 'add_admin':
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
