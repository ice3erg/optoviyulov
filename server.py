from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
import sqlite3
import pandas as pd
import requests
import uvicorn

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Инициализация базы данных
conn = sqlite3.connect('products.db')
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

# API для товаров
@app.get('/api/products')
async def get_products(category: str = '', search: str = ''):
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
    return [{'id': p[0], 'name': p[1], 'description': p[2], 'price': p[3], 'image': p[4], 'category': p[5]} for p in products]

@app.get('/api/products/{product_id}')
async def get_product(product_id: int):
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    p = cursor.fetchone()
    return {'id': p[0], 'name': p[1], 'description': p[2], 'price': p[3], 'image': p[4], 'category': p[5]}

@app.post('/api/products')
async def add_product(product: dict):
    cursor.execute('''
        INSERT INTO products (name, description, price, image, category)
        VALUES (?, ?, ?, ?, ?)
    ''', (product['name'], product['description'], product['price'], product['image'], product['category']))
    conn.commit()
    return {'status': 'success'}

@app.post('/api/upload_excel')
async def upload_excel(file: UploadFile = File(...)):
    df = pd.read_excel(file.file)
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO products (name, description, price, image, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (row['name'], row['description'], row['price'], row['image'], row['category']))
    conn.commit()
    return {'status': 'success'}

@app.post('/api/order')
async def send_order(order: dict):
    user = order['user']
    items = order['items']
    message = f"Новый заказ от {user['first_name']} {user.get('last_name', '')}:\n"
    for item in items:
        message += f"- {item['name']} ({item['price']} ₽)\n"
    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={SELLER_CHAT_ID}&text={message}")
    return {'status': 'success'}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
