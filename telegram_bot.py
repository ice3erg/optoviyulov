import aiosqlite, logging, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

# Создание бота и диспетчера (глобальные объекты для использования в server.py)
BOT_TOKEN = "7794423659:AAEhrbYTbdOciv-KKbayauY5qPmoCmNt4-E"  # Замените на свой токен!
DB_NAME = "products.db"

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
logger = logging.getLogger("bot")

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        r = await db.execute_fetchone("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return r is not None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Используй /admins, /addadmin <id>")

@dp.message(Command("addadmin"))
async def add_admin_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        return await message.answer("Нет доступа.")
    try:
        uid = int(message.text.split()[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,))
            await db.commit()
        await message.answer(f"✅ {uid} добавлен как админ.")
    except: await message.answer("Ошибка.")

@dp.message(Command("admins"))
async def list_admins(message: types.Message):
    if not await is_admin(message.from_user.id):
        return await message.answer("Нет доступа.")
    async with aiosqlite.connect(DB_NAME) as db:
        rows = await db.execute_fetchall("SELECT user_id FROM admins")
        ids = [str(row[0]) for row in rows]
    await message.answer("Админы:\n" + "\n".join(ids))

async def send_order_notification(order: dict):
    text = f"🛒 Новый заказ:\nID: {order['id']}\nПользователь: {order['user_id']}\nСумма: {order['total_price']} ₽\n\nТовары:\n"
    for p in order["products"]:
        text += f"- {p['name']} x{p['quantity']}\n"
    async with aiosqlite.connect(DB_NAME) as db:
        rows = await db.execute_fetchall("SELECT user_id FROM admins")
    for row in rows:
        try:
            await bot.send_message(row[0], text)
        except Exception as e:
            logger.error(f"Ошибка отправки админу {row[0]}: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
