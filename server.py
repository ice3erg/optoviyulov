from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import json
import asyncio
import aiosqlite
import logging
import telegram_bot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

# Создание необходимых директорий
os.makedirs("static", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация базы данных
DB_PATH = "products.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES categories(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL,
                images TEXT DEFAULT '["/static/placeholder.jpg"]',
                category_id INTEGER,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                products TEXT,
                total_price REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# Обслуживание статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Корневой путь
@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

@app.get("/admin")
async def serve_admin():
    return FileResponse("static/admin.html")

@app.get("/profile")
async def serve_profile():
    return FileResponse("static/profile.html")

@app.get("/cart")
async def serve_cart():
    return FileResponse("static/cart.html")

# API для получения категорий
@app.get("/api/categories")
async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, parent_id FROM categories") as cursor:
            categories = [{"id": row[0], "name": row[1], "parent_id": row[2]} for row in await cursor.fetchall()]
    return categories

# API для создания категории
@app.post("/api/admin/create_category")
async def create_category(name: str = Form(...), parent_id: str = Form(None)):
    logger.info(f"Received data: name={name}, parent_id={parent_id}")
    try:
        if not name or not name.strip():
            raise HTTPException(status_code=422, detail="Название категории обязательно")
        parent_id = int(parent_id) if parent_id and parent_id != "null" else None
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name.strip(), parent_id))
            await db.commit()
        return {"status": "success", "message": "Категория создана"}
    except ValueError:
        raise HTTPException(status_code=422, detail="parent_id должен быть числом, если указан")
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        raise HTTPException(status_code=422, detail="Ошибка создания категории")

# API для получения товаров
@app.get("/api/products")
async def get_products(category_id: int = None, search: str = None):
    query = 'SELECT p.id, p.name, p.description, p.price, p.images, c.name AS category FROM products p JOIN categories c ON p.category_id = c.id WHERE 1=1'
    params = []
    if category_id is not None:
        query += ' AND p.category_id = ?'
        params.append(category_id)
    if search is not None and search.strip():
        query += ' AND p.name LIKE ?'
        params.append(f"%{search.strip()}%")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    products = [
        {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "images": json.loads(row[4]), "category": row[5]}
        for row in rows
    ]
    logger.info(f"Returning {len(products)} products")
    return products

# API для получения одного товара по id
@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "images": json.loads(row[4]), "category_id": row[5]}

# API для добавления товара с множественными изображениями
@app.post("/api/admin/upload")
async def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    images: list[UploadFile] = File(...)
):
    try:
        image_paths = []
        if images:
            for image in images:
                filename = f"static/uploads/{image.filename}"
                with open(filename, "wb") as buffer:
                    shutil.copyfileobj(image.file, buffer)
                image_paths.append(f"/static/uploads/{image.filename}")
        image_json = json.dumps(image_paths) if image_paths else '["/static/placeholder.jpg"]'

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT INTO products (name, description, price, images, category_id) VALUES (?, ?, ?, ?, ?)',
                (name, description, price, image_json, category_id)
            )
            await db.commit()
        logger.info(f"Product '{name}' added successfully")
        return {"status": "success", "message": "Товар добавлен"}
    except Exception as e:
        logger.error(f"Error adding product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

# API для удаления товара
@app.delete("/api/admin/delete_product/{product_id}")
async def delete_product(product_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await db.commit()
        if db.rowcount == 0:
            raise HTTPException(status_code=404, detail="Товар не найден")
        logger.info(f"Product with ID {product_id} deleted successfully")
        return {"status": "success", "message": "Товар удалён"}
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# API для создания заказа
@app.post("/api/orders")
async def create_order(user_id: str = Form(...), products: str = Form(...), total_price: float = Form(...)):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT INTO orders (user_id, products, total_price) VALUES (?, ?, ?)',
                (user_id, products, total_price)
            )
            await db.commit()
            await db.execute("SELECT * FROM orders WHERE id = (SELECT last_insert_rowid())")
            order = await db.fetchone()
        order_data = {
            "id": order[0],
            "user_id": order[1],
            "products": json.loads(order[2]),
            "total_price": order[3],
            "status": order[4],
            "created_at": order[5]
        }
        await telegram_bot.send_order_notification(order_data)
        logger.info(f"Order created for user_id={user_id}")
        return {"status": "success", "message": "Заказ создан"}
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# API для получения заказов пользователя
@app.get("/api/orders")
async def get_orders(user_id: str = None):
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID required")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM orders WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
    orders = [{"id": row[0], "user_id": row[1], "products": json.loads(row[2]), "total_price": row[3], "status": row[4], "created_at": row[5]} for row in rows]
    return orders

# Запуск бота при старте приложения
@app.on_event("startup")
async def startup_event():
    import os
    port = os.getenv("PORT", "8000")  # Явная проверка порта
    logger.info(f"Starting server on port {port}")
    await init_db()
    logger.info("Starting bot polling...")
    await telegram_bot.start_polling()
