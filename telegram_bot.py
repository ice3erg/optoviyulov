import os
import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.exceptions import TelegramConflictError

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

DB_NAME = "products.db"

# Создание бота и диспетчера
BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Флаг для предотвращения повторного запуска
_is_running = False

SELLER_ID = 984066798  # Например, 123456789

async def is_admin_or_seller(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
                if await cursor.fetchone() is not None:
                    return True  # Пользователь является админом
        return user_id == SELLER_ID  # Пользователь является продавцом (вами)
    except Exception as e:
        logger.error(f"Error in is_admin_or_seller: {e}")
        return False

async def add_admin(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            logger.info(f"Attempting to add user {user_id} as admin")
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()
            logger.info(f"Successfully added user {user_id} as admin")
        return True
    except Exception as e:
        logger.error(f"Error in add_admin for user {user_id}: {e}")
        return False

async def init_db():
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            # Инициализация вас как продавца/админа
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SELLER_ID,))
            await db.commit()
            logger.info("Database initialized or already exists with seller as admin")
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать! Используйте /addadmin id, если вы админ или продавец.")

@dp.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    if not await is_admin_or_seller(message.from_user.id):
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
    if not await is_admin_or_seller(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM admins") as cursor:
                rows = await cursor.fetchall()
                ids = [str(row[0]) for row in rows]
        await message.answer("🧑‍💻 Список админов:\n" + "\n".join(ids))
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def send_order_notification(order: dict):
    try:
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
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_order_notification: {e}")

async def on_startup():
    logger.info("Бот запущен!")
    await init_db()

async def start_polling():
    global _is_running
    if not _is_running:
        _is_running = True
        try:
            logger.info("Starting bot polling...")
            await dp.start_polling(bot, on_startup=on_startup)
        except TelegramConflictError:
            logger.error("Another bot instance is running. Stopping polling.")
            _is_running = False
        except Exception as e:
            logger.error(f"Error in start_polling: {e}")
            _is_running = False
            raise
    else:
        logger.warning("Bot polling is already running!")

if __name__ == "__main__":
    raise RuntimeError("This module should not be run directly. Use server.py to start the bot.")
