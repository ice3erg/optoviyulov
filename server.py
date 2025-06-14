from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from PIL import Image
import shutil
import logging

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

# Инициализация FastAPI
app = FastAPI()

# CORS на всякий случай
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статические файлы
app.mount("/", StaticFiles(directory="static", html=True), name="static")
app.mount("/uploads", StaticFiles(directory="static/uploads"), name="uploads")

# Подключение к базе
DB_PATH = "products.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL,
        image TEXT,
        category TEXT
    )
''')
conn.commit()

# Получение всех товаров
@app.get("/api/products")
async def get_products(category: str = '', search: str = ''):
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
    return [
        {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "image": row[4], "category": row[5]}
        for row in rows
    ]

# Получение одного товара
@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "image": row[4], "category": row[5]}

# Загрузка товара
@app.post("/api/admin/upload")
async def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    image: UploadFile = File(...)
):
    try:
        os.makedirs("static/uploads", exist_ok=True)
        image_path = f"static/uploads/{image.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # Сжимаем изображение
        img = Image.open(image_path)
        img.thumbnail((200, 200))
        img.save(image_path, optimize=True)

        image_url = f"/uploads/{image.filename}"
        cursor.execute(
            'INSERT INTO products (name, description, price, image, category) VALUES (?, ?, ?, ?, ?)',
            (name, description, price, image_url, category)
        )
        conn.commit()

        return JSONResponse(status_code=201, content={
            "status": "success",
            "message": "Товар добавлен",
            "image_path": image_url
        })
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {e}")

# Запуск локально
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

