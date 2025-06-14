from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import logging
import os
import shutil
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

# Создание необходимых директорий
os.makedirs("static", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)

app = FastAPI()

# CORS для Telegram Web App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к базе данных
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parent_id INTEGER DEFAULT NULL,
        FOREIGN KEY (parent_id) REFERENCES categories(id)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        images TEXT, -- JSON с массивом путей к изображениям
        category_id INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        products TEXT, -- JSON с массивом {product_id, quantity}
        total REAL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# Обслуживание статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Корневой путь
@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

# Админ-панель
@app.get("/admin")
async def serve_admin():
    return FileResponse("static/admin.html")

# API для получения категорий
@app.get("/api/categories")
async def get_categories():
    cursor.execute("SELECT id, name, parent_id FROM categories")
    categories = [{"id": row[0], "name": row[1], "parent_id": row[2]} for row in cursor.fetchall()]
    return categories

# API для создания категории
@app.post("/api/categories")
async def create_category(name: str = Form(...), parent_id: int = Form(None)):
    try:
        cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
        conn.commit()
        return {"status": "success", "message": "Категория создана"}
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# API для получения товаров
@app.get("/api/products")
async def get_products(category_id: int = None, search: str = ''):
    query = 'SELECT p.id, p.name, p.description, p.price, p.images, c.name AS category FROM products p JOIN categories c ON p.category_id = c.id WHERE 1=1'
    params = []
    if category_id:
        query += ' AND p.category_id = ?'
        params.append(category_id)
    if search:
        query += ' AND p.name LIKE ?'
        params.append(f"%{search}%")
    cursor.execute(query, params)
    rows = cursor.fetchall()
    products = [
        {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "images": json.loads(row[4]) if row[4] else [], "category": row[5]}
        for row in rows
    ]
    return products

# API для добавления товара с несколькими изображениями
@app.post("/api/admin/upload")
async def upload_product(name: str = Form(...), description: str = Form(...), price: float = Form(...), category_id: int = Form(...), images: list[UploadFile] = File(None)):
    try:
        image_paths = []
        if images:
            for image in images:
                filename = f"static/uploads/{image.filename}"
                with open(filename, "wb") as buffer:
                    shutil.copyfileobj(image.file, buffer)
                image_paths.append(f"/static/uploads/{image.filename}")
        image_json = json.dumps(image_paths) if image_paths else "/static/placeholder.jpg"

        cursor.execute(
            "INSERT INTO products (name, description, price, images, category_id) VALUES (?, ?, ?, ?, ?)",
            (name, description, price, image_json, category_id)
        )
        conn.commit()
        logger.info(f"Product '{name}' added successfully")
        return {"status": "success", "message": "Товар добавлен"}
    except Exception as e:
        logger.error(f"Error adding product: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# API для добавления заказа
@app.post("/api/orders")
async def create_order(user_id: str = Form(...), products: str = Form(...)):  # products как JSON
    try:
        product_list = json.loads(products)
        total = sum(item["price"] * item["quantity"] for item in product_list)
        cursor.execute(
            "INSERT INTO orders (user_id, products, total) VALUES (?, ?, ?)",
            (user_id, json.dumps(product_list), total)
        )
        conn.commit()
        # Здесь можно добавить отправку уведомления продавцу (например, через Telegram API)
        logger.info(f"Order created for user {user_id} with total {total}")
        return {"status": "success", "message": "Заказ создан"}
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# API для профиля пользователя
@app.get("/api/profile")
async def get_profile():
    # В реальном приложении используем Telegram Web App data
    return {"user_id": "telegram_user_id", "username": "Maxim", "avatar": "/static/default_avatar.jpg"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
