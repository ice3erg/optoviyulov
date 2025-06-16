import os
import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command

BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"  # <-- Замени на свой токен!
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

DB_NAME = "products.db"

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def add_admin(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать! Используйте /addadmin <id>, если вы админ.")

@dp.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав добавлять админов.")
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer("Использование: /addadmin <user_id>")
            return
        new_admin_id = int(parts[1])
        if await add_admin(new_admin_id):
            await message.answer(f"✅ Пользователь {new_admin_id} теперь админ.")
        else:
            await message.answer("Этот пользователь уже админ.")
    except ValueError:
        await message.answer("Ошибка: user_id должен быть числом.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("admins"))
async def cmd_admins_list(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM admins") as cursor:
            rows = await cursor.fetchall()
            ids = [str(row[0]) for row in rows]
    await message.answer("🧑‍💻 Список админов:\n" + "\n".join(ids))

async def send_order_notification(order: dict):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM admins") as cursor:
            rows = await cursor.fetchall()
            admin_ids = [row[0] for row in rows]

    text = (f"🛒 Новый заказ:\n\n"
            f"ID: {order['id']}\n"
            f"Пользователь: {order['user_id']}\n"
            f"Сумма: {order['total_price']} ₽\n\n"
            "Товары:\n")
    for p in order["products"]:
        text += f"- {p['name']} x{p['quantity']}\n"

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")

async def on_startup():
    logging.info("Бот запущен!")
    await init_db()

def run_bot():
    asyncio.run(dp.start_polling(bot, on_startup=on_startup))

if __name__ == "__main__":
    run_bot()
