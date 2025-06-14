import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import sqlite3
import json

# Токен бота (будет взят из переменной окружения)
BOT_TOKEN = os.getenv("7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E")

# Подключение к базе данных
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Я бот для уведомлений о заказах. Используй /get_orders, чтобы увидеть заказы.")

# Команда /get_orders для отправки состава заказа
async def get_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cursor.execute("SELECT * FROM orders")
    orders = cursor.fetchall()
    if orders:
        for order in orders:
            order_data = {
                "ID": order[0],
                "User ID": order[1],
                "Products": json.loads(order[2]),
                "Total Price": order[3],
                "Status": order[4],
                "Created At": order[5]
            }
            message = f"Новый заказ!\nID: {order_data['ID']}\nПользователь: {order_data['User ID']}\nТовары: {json.dumps(order_data['Products'], ensure_ascii=False)}\nСумма: {order_data['Total Price']} ₽\nСтатус: {order_data['Status']}\nДата: {order_data['Created At']}"
            await update.message.reply_text(message)
    else:
        await update.message.reply_text("Нет заказов.")

# Основная функция
def main() -> None:
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("get_orders", get_orders))

    # Запуск бота
    if os.name == "nt":  # Для Windows
        asyncio.run(application.run_polling())
    else:  # Для Emscripten (Render)
        application.run_polling()

if __name__ == "__main__":
    main()
