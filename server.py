from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import logging
import os
import shutil

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

# Создание необходимых директорий
os.makedirs("static", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)

app = FastAPI()

# CORS (на всякий случай)
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

# API для получения одного товара по id
@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "image": row[4], "category": row[5]}

# API для добавления товара
@app.post("/api/admin/upload")
async def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    image: UploadFile = File(None)
):
    try:
        image_path = "/static/placeholder.jpg"
        if image:
            filename = f"static/uploads/{image.filename}"
            with open(filename, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_path = f"/static/uploads/{image.filename}"

        cursor.execute(
            'INSERT INTO products (name, description, price, image, category) VALUES (?, ?, ?, ?, ?)',
            (name, description, price, image_path, category)
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
