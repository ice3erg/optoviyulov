from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

app = FastAPI()

# Database connection
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

# Serve index.html at root
@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

# Serve admin.html at /admin
@app.get("/admin")
async def serve_admin():
    return FileResponse("static/admin.html")

# Mount static files at /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# API to get products
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

# API to add a product
@app.post("/api/admin/upload")
async def upload_product(name: str = Form(...), description: str = Form(...), price: float = Form(...), category: str = Form(...)):
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
