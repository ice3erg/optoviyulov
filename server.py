from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, json, aiosqlite, logging
import telegram_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("optulov")

app = FastAPI()

os.makedirs("static/uploads", exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "products.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES categories(id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT,
            price REAL, images TEXT DEFAULT '["/static/placeholder.jpg"]',
            category_id INTEGER, FOREIGN KEY (category_id) REFERENCES categories(id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, products TEXT,
            total_price REAL, status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        await db.commit()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index(): return FileResponse("static/index.html")

@app.get("/admin")
async def serve_admin(): return FileResponse("static/admin.html")

@app.get("/profile")
async def serve_profile(): return FileResponse("static/profile.html")

@app.get("/cart")
async def serve_cart(): return FileResponse("static/cart.html")

@app.get("/api/categories")
async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, parent_id FROM categories") as cursor:
            return [{"id": row[0], "name": row[1], "parent_id": row[2]} for row in await cursor.fetchall()]

@app.post("/api/admin/create_category")
async def create_category(name: str = Form(...), parent_id: str = Form(None)):
    if not name.strip(): raise HTTPException(422, detail="Название обязательно")
    parent_id = int(parent_id) if parent_id and parent_id != "null" else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name.strip(), parent_id))
        await db.commit()
    return {"status": "success"}

@app.get("/api/products")
async def get_products(category_id: int = None, search: str = None):
    query = """SELECT p.id, p.name, p.description, p.price, p.images, c.name
               FROM products p JOIN categories c ON p.category_id = c.id WHERE 1=1"""
    params = []
    if category_id: query += " AND p.category_id = ?", params.append(category_id)
    if search: query += " AND p.name LIKE ?", params.append(f"%{search.strip()}%")
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(query, params)
    return [{"id": r[0], "name": r[1], "description": r[2], "price": r[3], "images": json.loads(r[4]), "category": r[5]} for r in rows]

@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone("SELECT * FROM products WHERE id = ?", (product_id,))
    if not row: raise HTTPException(404, detail="Не найден")
    return {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "images": json.loads(row[4]), "category_id": row[5]}

@app.post("/api/admin/upload")
async def upload_product(name: str = Form(...), description: str = Form(...), price: float = Form(...),
                         category_id: int = Form(...), images: list[UploadFile] = File(...)):
    image_paths = []
    for image in images:
        path = f"static/uploads/{image.filename}"
        with open(path, "wb") as f: shutil.copyfileobj(image.file, f)
        image_paths.append(f"/static/uploads/{image.filename}")
    images_json = json.dumps(image_paths or ["/static/placeholder.jpg"])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO products (name, description, price, images, category_id) VALUES (?, ?, ?, ?, ?)",
                         (name, description, price, images_json, category_id))
        await db.commit()
    return {"status": "success", "message": "Добавлено"}

@app.delete("/api/admin/delete_product/{product_id}")
async def delete_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()
    return {"status": "success"}

@app.post("/api/orders")
async def create_order(user_id: str = Form(...), products: str = Form(...), total_price: float = Form(...)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO orders (user_id, products, total_price) VALUES (?, ?, ?)",
                         (user_id, products, total_price))
        await db.commit()
        row = await db.execute_fetchone("SELECT * FROM orders WHERE id = last_insert_rowid()")
    order = {
        "id": row[0], "user_id": row[1], "products": json.loads(row[2]),
        "total_price": row[3], "status": row[4], "created_at": row[5]
    }
    await telegram_bot.send_order_notification(order)
    return {"status": "success"}

@app.get("/api/orders")
async def get_orders(user_id: str = None):
    if not user_id: raise HTTPException(400, detail="user_id required")
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall("SELECT * FROM orders WHERE user_id = ?", (user_id,))
    return [{"id": r[0], "user_id": r[1], "products": json.loads(r[2]), "total_price": r[3], "status": r[4], "created_at": r[5]} for r in rows]

@app.on_event("startup")
async def startup_event():
    await init_db()
