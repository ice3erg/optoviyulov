from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
import sqlite3

app = FastAPI()
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Простой маршрут для проверки (опционально)
@app.get("/api")
async def read_root():
    return {"message": "API Оптовый Улов работает!"}

# Инициализация базы данных (опционально)
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
conn.commit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
