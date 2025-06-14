from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

# Создание необходимых директорий
os.makedirs("static", exist_ok=True)

app = FastAPI()

# Подключение к базе данных
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        image TEXT DEFAULT '/static/placeholder.jpg',
        category TEXT
    )
''')
conn.commit()

# Обслуживание статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Корневой путь (пользовательская страница)
@app.get("/")
async def serve_index():
    index_path = "static/index.html"
    if not os.path.exists(index_path):
        logger.error("index.html не найден!")
        raise HTTPException(status_code=404, detail="Файл index.html не найден")
    return FileResponse(index_path)

# Админ-панель
@app.get("/admin")
async def serve_admin():
    admin_path = "static/admin.html"
    if not os.path.exists(admin_path):
        logger.error("admin.html не найден!")
        raise HTTPException(status_code=404, detail="Файл admin.html не найден")
    return FileResponse(admin_path)

# API для получения товаров
@app.get("/api/products")
async def get_products(category: str = '', search: str = ''):
    logger.info(f"Fetching products with category='{category}', search='{search}'")
    query = 'SELECT * FROM products WHERE 1=1'
    params = []
    if category:
        query += ' AND category = ?'
        params.append(category)
    if search:
        query += ' AND name LIKE ?'
        params.append(f"%{search}%")
    cursor.execute(query, params)
    rows = cursor.fetchall()
    products = [
        {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "image": row[4], "category": row[5]}
        for row in rows
    ]
    logger.info(f"Returning {len(products)} products")
    return products

# API для добавления товара
@app.post("/api/admin/upload")
async def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...)
):
    try:
        cursor.execute(
            'INSERT INTO products (name, description, price, category) VALUES (?, ?, ?, ?)',
            (name, description, price, category)
        )
        conn.commit()
        logger.info(f"Product '{name}' added successfully")
        return {"status": "success", "message": "Товар добавлен"}
    except Exception as e:
        logger.error(f"Error adding product: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
