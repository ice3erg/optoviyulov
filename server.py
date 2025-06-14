from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
import sqlite3
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

# Инициализация FastAPI
app = FastAPI()

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
        image TEXT DEFAULT '/static/placeholder.jpg',
        category TEXT
    )
''')
conn.commit()

# Корневой путь перенаправляет на admin.html
@app.get("/")
async def root():
    return FileResponse("static/admin.html", media_type="text/html")

# Обслуживание статических файлов
@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    file_path = os.path.join("static", file_path)
    if os.path.isfile(file_path):
        media_type = "text/html" if file_path.endswith(".html") else "application/octet-stream"
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Файл не найден")

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
async def upload_product(name: str = Form(...), description: str = Form(...), price: float = Form(...), category: str = Form(...)):
    try:
        logger.info(f"Получен запрос: name={name}, description={description}, price={price}, category={category}")
        cursor.execute(
            'INSERT INTO products (name, description, price, category) VALUES (?, ?, ?, ?)',
            (name, description, price, category)
        )
        conn.commit()
        logger.info("Товар добавлен в базу данных")
        return {"status": "success", "message": "Товар добавлен", "image_path": "/static/placeholder.jpg"}
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
