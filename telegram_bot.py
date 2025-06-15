
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# --- Конфигурация ---
BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"  # <-- Замени на свой токен!
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.reply("Добро пожаловать! Используйте /addadmin <id>, если вы админ.")

@dp.message_handler(commands=["addadmin"])
async def cmd_addadmin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав добавлять админов.")
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.reply("Использование: /addadmin <user_id>")
            return
        new_admin_id = int(parts[1])
        if add_admin(new_admin_id):
            await message.reply(f"✅ Пользователь {new_admin_id} теперь админ.")
        else:
            await message.reply("Этот пользователь уже админ.")
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

@dp.message_handler(commands=["admins"])
async def cmd_admins_list(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("Нет доступа.")
        return
    import sqlite3
    conn = sqlite3.connect("products.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    ids = [str(row[0]) for row in cur.fetchall()]
    conn.close()
    await message.reply("🧑‍💻 Список админов:\n" + "\n".join(ids))

async def send_order_notification(order: dict):
    import sqlite3
    conn = sqlite3.connect("products.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    admin_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    text = f"🛒 Новый заказ:\n\nID: {order['id']}\nПользователь: {order['user_id']}\nСумма: {order['total_price']} ₽\n\nТовары:\n"
    for p in order["products"]:
        text += f"- {p['name']} x{p['quantity']}\n"

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True)

