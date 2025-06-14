from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
from PIL import Image
import shutil
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Монтирование статических файлов с явным путем
app.mount("/static", StaticFiles(directory="static"), name="static")

# Инициализация базы данных
try:
    conn = sqlite3.connect('products.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price REAL,
            image TEXT,
            category TEXT
        )
    ''')
    # Добавление начальных данных для теста
    sample_products = [
        {"name": "Кренк 5см", "description": "Кренк для щуки", "price": 500, "image": "/static/placeholder_krenk.jpg", "category": "krenki"},
        {"name": "Минноу 6см", "description": "Минноу для окуня", "price": 600, "image": "/static/placeholder_minnow.jpg", "category": "minnow"},
        {"name": "Поппер 5см", "description": "Поппер для поверхностной ловли", "price": 550, "image": "/static/placeholder_popper.jpg", "category": "poppers"},
        {"name": "Кастинг Спиннинг", "description": "Спиннинг для дальних забросов", "price": 3000, "image": "/static/placeholder_casting.jpg", "category": "casting"}
    ]
    for product in sample_products:
        cursor.execute('INSERT OR IGNORE INTO products (name, description, price, image, category) VALUES (?, ?, ?, ?, ?)', 
                       (product["name"], product["description"], product["price"], product["image"], product["category"]))
    conn.commit()
    logger.info("База данных успешно инициализирована")
except sqlite3.Error as e:
    logger.error(f"Ошибка подключения к базе данных: {e}")

# API для товаров
@app.get('/api/products')
async def get_products(category: str = '', search: str = ''):
    try:
        query = 'SELECT * FROM products WHERE 1=1'
        params = []
        if category:
            query += ' AND category = ?'
            params.append(category)
        if search:
            query += ' AND name LIKE ?'
            params.append(f'%{search}%')
        cursor.execute(query, params)
        products = cursor.fetchall()
        if not products:
            raise HTTPException(status_code=404, detail="Товары не найдены")
        return [{'id': p[0], 'name': p[1], 'description': p[2], 'price': p[3], 'image': p[4], 'category': p[5]} for p in products]
    except Exception as e:
        logger.error(f"Ошибка в /api/products: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")

@app.get('/api/products/{product_id}')
async def get_product(product_id: int):
    try:
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        p = cursor.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Товар не найден")
        return {'id': p[0], 'name': p[1], 'description': p[2], 'price': p[3], 'image': p[4], 'category': p[5]}
    except Exception as e:
        logger.error(f"Ошибка в /api/products/{product_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")

# Загрузка через админ-панель
@app.post('/api/admin/upload')
async def upload_product(name: str, description: str, price: float, category: str, image: UploadFile = File(...)):
    try:
        logger.info(f"Получен запрос: name={name}, description={description}, price={price}, category={category}, filename={image.filename}")
        # Сохранение изображения
        image_path = f"static/uploads/{image.filename}"
        os.makedirs("static/uploads", exist_ok=True)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        logger.info(f"Изображение сохранено в {image_path}")
        # Сжатие изображения
        img = Image.open(image_path)
        img.thumbnail((100, 100))  # Уменьшение до 100x100
        img.save(image_path, optimize=True)
        logger.info(f"Изображение сжато и сохранено в {image_path}")
        # Добавление в базу
        cursor.execute('INSERT INTO products (name, description, price, image, category) VALUES (?, ?, ?, ?, ?)',
                       (name, description, price, f"/static/uploads/{image.filename}", category))
        conn.commit()
        logger.info("Товар добавлен в базу данных")
        return {"status": "success", "image_path": f"/static/uploads/{image.filename}"}
    except Exception as e:
        logger.error(f"Ошибка в /api/admin/upload: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
