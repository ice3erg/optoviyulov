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

# Ваш seller_id
SELLER_ID = 984066798  # Убедитесь, что это ваш реальный user_id

async def is_admin_or_seller(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
                if await cursor.fetchone() is not None:
                    logger.info(f"User {user_id} is an admin")
                    return True
            if user_id == SELLER_ID:
                logger.info(f"User {user_id} is the seller")
                return True
        logger.info(f"User {user_id} is neither admin nor seller")
        return False
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
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SELLER_ID,))
            await db.commit()
            logger.info(f"Database initialized with seller ID {SELLER_ID} as admin")
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if await is_admin_or_seller(user_id):
        await message.answer("Добро пожаловать! Вы админ или продавец. Используйте <code>/addadmin id</code>.")
    else:
        await message.answer("Добро пожаловать! У вас нет прав админа или продавца.")

@dp.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    if not await is_admin_or_seller(message.from_user.id):
        await message.answer("У вас нет прав добавлять админов.")
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer("Использование: <code>/addadmin <user_id></code>")
            return
        new_admin_id = int(parts[1])
        if await add_admin(new_admin_id):
            await message.answer(f"✅ Пользователь <code>{new_admin_id}</code> теперь админ.")
        else:
            await message.answer(f"Пользователь <code>{new_admin_id}</code> уже админ.")
    except ValueError:
        await message.answer("Ошибка: user_id должен быть числом.")
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

@dp.message(Command("admins"))
async def cmd_admins_list(message: types.Message):
    if not await is_admin_or_seller(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM admins") as cursor:
                rows = await cursor.fetchall()
                ids = [f"<code>{row[0]}</code>" for row in rows]
        await message.answer("🧑‍💻 Список админов:\n" + "\n".join(ids))
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

async def send_order_notification(order: dict):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM admins") as cursor:
                rows = await cursor.fetchall()
                admin_ids = [row[0] for row in rows]

        # Экранируем данные для безопасной вставки
        safe_id = str(order.get('id', 'N/A'))
        safe_user_id = str(order.get('user_id', 'N/A'))
        safe_price = str(order.get('total_price', 'N/A'))

        text = (f"🛒 Новый заказ:\n\n"
                f"ID: <code>{safe_id}</code>\n"
                f"Пользователь: <code>{safe_user_id}</code>\n"
                f"Сумма: <code>{safe_price}</code> ₽\n\n"
                "Товары:\n")
        for p in order.get('products', []):
            safe_name = str(p.get('name', 'N/A'))
            quantity = str(p.get('quantity', 'N/A'))
            text += f"- <code>{safe_name}</code> x{quantity}\n"

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
            await dp.start_polling(bot, on_startup=on_startup, skip_updates=True)
        except TelegramConflictError:
            logger.error("Another bot instance is running. Stopping polling and attempting to close.")
            _is_running = False
            await bot.close()
            await asyncio.sleep(5)  # Дополнительная задержка перед выходом
        except Exception as e:
            logger.error(f"Error in start_polling: {e}")
            _is_running = False
            raise
    else:
        logger.warning("Bot polling is already running!")

if __name__ == "__main__":
    raise RuntimeError("This module should not be run directly. Use server.py to start the bot.")
