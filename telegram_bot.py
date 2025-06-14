import os
import json
import sqlite3
import logging
import asyncio
import threading
from telegram import Bot
from telegram.ext import Application, CommandHandler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# Токен бота и ID чата продавца из переменных окружения
BOT_TOKEN = os.getenv("7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E")
SELLER_CHAT_ID = os.getenv("984066798")

# Подключение к базе данных
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Инициализация бота
bot = None
application = None
if BOT_TOKEN and SELLER_CHAT_ID:
    try:
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

async def start(update, context):
    """Временная команда для получения chat_id."""
    chat_id = update.message.chat.id
    await update.message.reply_text(f"Бот работает! Ваш chat_id: {chat_id}")

async def send_order_notification(order_data):
    """Отправка уведомления о новом заказе продавцу."""
    if not bot or not SELLER_CHAT_ID:
        logger.warning("Уведомление не отправлено: бот не инициализирован или SELLER_CHAT_ID не установлен")
        return
    try:
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
        # Временная команда для получения chat_id
        application.add_handler(CommandHandler("start", start))
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
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
