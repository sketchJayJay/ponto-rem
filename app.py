import os
import sqlite3
from datetime import datetime
from pathlib import Path
from functools import wraps
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("DATABASE_PATH", DATA_DIR / "ponto_rem.db"))
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-essa-chave-no-coolify")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def now_br():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def money(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


app.jinja_env.filters["money"] = money


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand TEXT DEFAULT '',
                category TEXT DEFAULT 'Tênis ortopédico',
                description TEXT DEFAULT '',
                price REAL NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0,
                image_path TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                show_public INTEGER NOT NULL DEFAULT 1,
                highlight INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                color TEXT NOT NULL DEFAULT 'Única',
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                sku TEXT DEFAULT '',
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost REAL DEFAULT 0,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(variant_id) REFERENCES variants(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT DEFAULT '',
                customer_phone TEXT DEFAULT '',
                payment_method TEXT DEFAULT 'Pix',
                discount REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                variant_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                unit_cost REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(variant_id) REFERENCES variants(id)
            );
            """
        )
        defaults = {
            "store_name": "Ponto REM",
            "store_subtitle": "Conforto, cuidado e bem-estar para caminhar melhor todos os dias.",
            "whatsapp": "",
            "catalog_intro": "Escolha o modelo ideal para sua rotina com mais conforto, praticidade e confiança.",
            "low_stock_limit": "2",
        }
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
        conn.commit()


def query_one(sql, params=()):
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()


def query_all(sql, params=()):
    with get_db() as conn:
        return conn.execute(sql, params).fetchall()


def settings_dict():
    rows = query_all("SELECT key, value FROM settings")
    return {row["key"]: row["value"] for row in rows}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    if not file_storage or file_storage.filename == "":
        return ""
    if not allowed_file(file_storage.filename):
        flash("Envie imagem em PNG, JPG, JPEG, WEBP ou GIF.", "error")
        return ""
    ext = secure_filename(file_storage.filename).rsplit(".", 1)[1].lower()
    filename = f"produto-{uuid4().hex}.{ext}"
    destination = UPLOAD_DIR / filename
    file_storage.save(destination)
    return f"/static/uploads/{filename}"


def product_image(product):
    if product and product["image_path"]:
        return product["image_path"]
    if product and product["image_url"]:
        return product["image_url"]
    return "/static/img/shoe-placeholder.svg"


app.jinja_env.globals["product_image"] = product_image
app.jinja_env.globals["now_br"] = now_br


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"settings": settings_dict()}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user", "").strip()
        password = request.form.get("password", "")
        admin_user = os.environ.get("ADMIN_USER", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        if user == admin_user and password == admin_password:
            session["admin_logged"] = True
            flash("Bem-vindo ao painel da Ponto REM.", "success")
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Usuário ou senha inválidos.", "error")
    return render_template("admin/login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do painel.", "success")
    return redirect(url_for("login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    low_limit = int(settings_dict().get("low_stock_limit", "2") or 2)
    total_products = query_one("SELECT COUNT(*) total FROM products")["total"]
    total_stock = query_one("SELECT COALESCE(SUM(quantity),0) total FROM variants")["total"]
    stock_value = query_one(
        """
        SELECT COALESCE(SUM(v.quantity * p.cost),0) total
        FROM variants v JOIN products p ON p.id = v.product_id
        """
    )["total"]
    month_key = datetime.now().strftime("%Y-%m")
    month_sales = query_one(
        "SELECT COALESCE(SUM(total),0) total FROM sales WHERE substr(created_at, 1, 7) = ?",
        (month_key,),
    )["total"]
    month_sold_qty = query_one(
        """
        SELECT COALESCE(SUM(si.quantity),0) total
        FROM sale_items si JOIN sales s ON s.id = si.sale_id
        WHERE substr(s.created_at, 1, 7) = ?
        """,
        (month_key,),
    )["total"]
    low_stock = query_all(
        """
        SELECT p.name, v.color, v.size, v.quantity
        FROM variants v JOIN products p ON p.id = v.product_id
        WHERE v.quantity <= ?
        ORDER BY v.quantity ASC, p.name ASC
        LIMIT 10
        """,
        (low_limit,),
    )
    best_sellers = query_all(
        """
        SELECT p.name, v.color, v.size, SUM(si.quantity) qty
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        JOIN variants v ON v.id = si.variant_id
        GROUP BY p.id, v.id
        ORDER BY qty DESC
        LIMIT 6
        """
    )
    recent_movements = query_all(
        """
        SELECT m.*, p.name, v.color, v.size
        FROM movements m
        JOIN products p ON p.id = m.product_id
        LEFT JOIN variants v ON v.id = m.variant_id
        ORDER BY m.id DESC
        LIMIT 8
        """
    )
    return render_template(
        "admin/dashboard.html",
        total_products=total_products,
        total_stock=total_stock,
        stock_value=stock_value,
        month_sales=month_sales,
        month_sold_qty=month_sold_qty,
        low_stock=low_stock,
        best_sellers=best_sellers,
        recent_movements=recent_movements,
    )


@app.route("/admin/products")
@login_required
def products():
    q = request.args.get("q", "").strip()
    params = []
    where = ""
    if q:
        where = "WHERE p.name LIKE ? OR p.brand LIKE ? OR p.category LIKE ?"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    rows = query_all(
        f"""
        SELECT p.*, COALESCE(SUM(v.quantity),0) total_quantity,
               COUNT(v.id) variant_count
        FROM products p
        LEFT JOIN variants v ON v.product_id = p.id
        {where}
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """,
        tuple(params),
    )
    return render_template("admin/products.html", products=rows, q=q)


@app.route("/admin/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    if request.method == "POST":
        return save_product()
    return render_template("admin/product_form.html", product=None, variants=[])


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def product_edit(product_id):
    product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not product:
        abort(404)
    if request.method == "POST":
        return save_product(product_id)
    variants = query_all("SELECT * FROM variants WHERE product_id = ? ORDER BY color, CAST(size AS INTEGER), size", (product_id,))
    return render_template("admin/product_form.html", product=product, variants=variants)


def save_product(product_id=None):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do modelo.", "error")
        return redirect(request.referrer or url_for("products"))
    price = float(request.form.get("price") or 0)
    cost = float(request.form.get("cost") or 0)
    uploaded_path = save_upload(request.files.get("image_file"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        if product_id:
            current = conn.execute("SELECT image_path FROM products WHERE id = ?", (product_id,)).fetchone()
            image_path = uploaded_path or (current["image_path"] if current else "")
            conn.execute(
                """
                UPDATE products
                SET name=?, brand=?, category=?, description=?, price=?, cost=?, image_path=?, image_url=?,
                    show_public=?, highlight=?, updated_at=?
                WHERE id=?
                """,
                (
                    name,
                    request.form.get("brand", "").strip(),
                    request.form.get("category", "Tênis ortopédico").strip(),
                    request.form.get("description", "").strip(),
                    price,
                    cost,
                    image_path,
                    request.form.get("image_url", "").strip(),
                    1 if request.form.get("show_public") else 0,
                    1 if request.form.get("highlight") else 0,
                    now,
                    product_id,
                ),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO products(name, brand, category, description, price, cost, image_path, image_url,
                                     show_public, highlight, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    request.form.get("brand", "").strip(),
                    request.form.get("category", "Tênis ortopédico").strip(),
                    request.form.get("description", "").strip(),
                    price,
                    cost,
                    uploaded_path,
                    request.form.get("image_url", "").strip(),
                    1 if request.form.get("show_public") else 0,
                    1 if request.form.get("highlight") else 0,
                    now,
                    now,
                ),
            )
            product_id = cur.lastrowid

        variant_ids = request.form.getlist("variant_id[]")
        colors = request.form.getlist("variant_color[]")
        sizes = request.form.getlist("variant_size[]")
        quantities = request.form.getlist("variant_quantity[]")
        skus = request.form.getlist("variant_sku[]")
        seen_ids = []
        for i, size in enumerate(sizes):
            size = (size or "").strip()
            if not size:
                continue
            color = (colors[i] if i < len(colors) else "Única").strip() or "Única"
            sku = (skus[i] if i < len(skus) else "").strip()
            quantity = int(float(quantities[i] or 0)) if i < len(quantities) else 0
            variant_id = variant_ids[i] if i < len(variant_ids) else ""
            if variant_id:
                conn.execute(
                    "UPDATE variants SET color=?, size=?, quantity=?, sku=? WHERE id=? AND product_id=?",
                    (color, size, quantity, sku, variant_id, product_id),
                )
                seen_ids.append(int(variant_id))
            else:
                cur = conn.execute(
                    "INSERT INTO variants(product_id, color, size, quantity, sku) VALUES (?, ?, ?, ?, ?)",
                    (product_id, color, size, quantity, sku),
                )
                seen_ids.append(cur.lastrowid)
        if product_id and seen_ids:
            placeholders = ",".join("?" for _ in seen_ids)
            conn.execute(
                f"DELETE FROM variants WHERE product_id=? AND id NOT IN ({placeholders})",
                (product_id, *seen_ids),
            )
        elif product_id and not seen_ids:
            conn.execute("DELETE FROM variants WHERE product_id=?", (product_id,))
        conn.commit()
    flash("Produto salvo com sucesso.", "success")
    return redirect(url_for("products"))


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
def product_delete(product_id):
    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    flash("Produto removido.", "success")
    return redirect(url_for("products"))


@app.route("/admin/stock", methods=["GET", "POST"])
@login_required
def stock():
    if request.method == "POST":
        variant_id = int(request.form.get("variant_id") or 0)
        movement_type = request.form.get("type", "entrada")
        quantity = int(float(request.form.get("quantity") or 0))
        unit_cost = float(request.form.get("unit_cost") or 0)
        note = request.form.get("note", "").strip()
        if quantity <= 0 or movement_type not in {"entrada", "saida", "ajuste"}:
            flash("Informe uma quantidade válida.", "error")
            return redirect(url_for("stock"))
        variant = query_one("SELECT * FROM variants WHERE id=?", (variant_id,))
        if not variant:
            flash("Selecione uma variação válida.", "error")
            return redirect(url_for("stock"))
        delta = quantity if movement_type == "entrada" else -quantity
        if movement_type in {"saida", "ajuste"} and variant["quantity"] + delta < 0:
            flash("Não há estoque suficiente para essa saída.", "error")
            return redirect(url_for("stock"))
        with get_db() as conn:
            conn.execute("UPDATE variants SET quantity = quantity + ? WHERE id=?", (delta, variant_id))
            conn.execute(
                "INSERT INTO movements(product_id, variant_id, type, quantity, unit_cost, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (variant["product_id"], variant_id, movement_type, quantity, unit_cost, note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        flash("Movimentação registrada.", "success")
        return redirect(url_for("stock"))

    variants = query_all(
        """
        SELECT v.*, p.name, p.cost
        FROM variants v JOIN products p ON p.id = v.product_id
        ORDER BY p.name, v.color, CAST(v.size AS INTEGER), v.size
        """
    )
    movements = query_all(
        """
        SELECT m.*, p.name, v.color, v.size
        FROM movements m
        JOIN products p ON p.id = m.product_id
        LEFT JOIN variants v ON v.id = m.variant_id
        ORDER BY m.id DESC LIMIT 40
        """
    )
    return render_template("admin/stock.html", variants=variants, movements=movements)


@app.route("/admin/sales/new", methods=["GET", "POST"])
@login_required
def sale_new():
    if request.method == "POST":
        variant_ids = request.form.getlist("variant_id[]")
        quantities = request.form.getlist("quantity[]")
        prices = request.form.getlist("unit_price[]")
        items = []
        for i, variant_id in enumerate(variant_ids):
            if not variant_id:
                continue
            qty = int(float(quantities[i] or 0)) if i < len(quantities) else 0
            unit_price = float(prices[i] or 0) if i < len(prices) else 0
            if qty <= 0:
                continue
            variant = query_one(
                """
                SELECT v.*, p.name, p.price, p.cost, p.id AS product_id
                FROM variants v JOIN products p ON p.id = v.product_id
                WHERE v.id=?
                """,
                (variant_id,),
            )
            if not variant:
                flash("Produto inválido na venda.", "error")
                return redirect(url_for("sale_new"))
            if variant["quantity"] < qty:
                flash(f"Estoque insuficiente: {variant['name']} {variant['color']} tam. {variant['size']}.", "error")
                return redirect(url_for("sale_new"))
            items.append({"variant": variant, "qty": qty, "unit_price": unit_price or variant["price"]})
        if not items:
            flash("Adicione pelo menos um produto na venda.", "error")
            return redirect(url_for("sale_new"))
        discount = float(request.form.get("discount") or 0)
        subtotal = sum(item["qty"] * item["unit_price"] for item in items)
        total = max(subtotal - discount, 0)
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO sales(customer_name, customer_phone, payment_method, discount, total, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request.form.get("customer_name", "").strip(),
                    request.form.get("customer_phone", "").strip(),
                    request.form.get("payment_method", "Pix").strip(),
                    discount,
                    total,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            sale_id = cur.lastrowid
            for item in items:
                v = item["variant"]
                conn.execute("UPDATE variants SET quantity = quantity - ? WHERE id=?", (item["qty"], v["id"]))
                conn.execute(
                    "INSERT INTO sale_items(sale_id, product_id, variant_id, quantity, unit_price, unit_cost) VALUES (?, ?, ?, ?, ?, ?)",
                    (sale_id, v["product_id"], v["id"], item["qty"], item["unit_price"], v["cost"]),
                )
                conn.execute(
                    "INSERT INTO movements(product_id, variant_id, type, quantity, unit_cost, note, created_at) VALUES (?, ?, 'venda', ?, ?, ?, ?)",
                    (v["product_id"], v["id"], item["qty"], v["cost"], f"Venda #{sale_id}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
            conn.commit()
        flash(f"Venda #{sale_id} registrada com sucesso.", "success")
        return redirect(url_for("sale_receipt", sale_id=sale_id))

    variants = query_all(
        """
        SELECT v.*, p.name, p.price, p.cost
        FROM variants v JOIN products p ON p.id = v.product_id
        WHERE v.quantity > 0
        ORDER BY p.name, v.color, CAST(v.size AS INTEGER), v.size
        """
    )
    return render_template("admin/sale_new.html", variants=variants)


@app.route("/admin/sales/<int:sale_id>")
@login_required
def sale_receipt(sale_id):
    sale = query_one("SELECT * FROM sales WHERE id=?", (sale_id,))
    if not sale:
        abort(404)
    items = query_all(
        """
        SELECT si.*, p.name, v.color, v.size
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        JOIN variants v ON v.id = si.variant_id
        WHERE si.sale_id=?
        """,
        (sale_id,),
    )
    return render_template("admin/sale_receipt.html", sale=sale, items=items)


@app.route("/admin/reports")
@login_required
def reports():
    sales = query_all("SELECT * FROM sales ORDER BY id DESC LIMIT 80")
    profit = query_one(
        """
        SELECT COALESCE(SUM((si.unit_price - si.unit_cost) * si.quantity),0) gross_profit,
               COALESCE(SUM(si.unit_price * si.quantity),0) revenue
        FROM sale_items si
        """
    )
    sizes = query_all(
        """
        SELECT v.size, SUM(si.quantity) qty
        FROM sale_items si JOIN variants v ON v.id = si.variant_id
        GROUP BY v.size
        ORDER BY qty DESC LIMIT 12
        """
    )
    return render_template("admin/reports.html", sales=sales, profit=profit, sizes=sizes)


@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if request.method == "POST":
        allowed = ["store_name", "store_subtitle", "whatsapp", "catalog_intro", "low_stock_limit"]
        with get_db() as conn:
            for key in allowed:
                conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, request.form.get(key, "").strip()))
            conn.commit()
        flash("Configurações atualizadas.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("admin/settings.html")


@app.route("/api/variants")
@login_required
def api_variants():
    rows = query_all(
        """
        SELECT v.id, v.color, v.size, v.quantity, p.name, p.price
        FROM variants v JOIN products p ON p.id = v.product_id
        ORDER BY p.name, v.color, CAST(v.size AS INTEGER), v.size
        """
    )
    return jsonify([dict(row) for row in rows])


@app.route("/")
def public_home():
    return redirect(url_for("catalog"))


@app.route("/loja")
@app.route("/vitrine")
def public_store_alias():
    return redirect(url_for("catalog"))


@app.route("/catalogo")
def catalog():
    search = request.args.get("q", "").strip()
    size = request.args.get("tam", "").strip()
    color = request.args.get("cor", "").strip()
    category = request.args.get("categoria", "").strip()
    params = []
    where = ["p.show_public = 1"]
    if search:
        where.append("(p.name LIKE ? OR p.brand LIKE ? OR p.category LIKE ? OR p.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    if size:
        where.append("EXISTS (SELECT 1 FROM variants vx WHERE vx.product_id = p.id AND vx.size = ? AND vx.quantity > 0)")
        params.append(size)
    if color:
        where.append("EXISTS (SELECT 1 FROM variants vx WHERE vx.product_id = p.id AND vx.color LIKE ? AND vx.quantity > 0)")
        params.append(f"%{color}%")
    if category:
        where.append("p.category = ?")
        params.append(category)
    products = query_all(
        f"""
        SELECT p.*, COALESCE(SUM(v.quantity),0) total_quantity
        FROM products p
        LEFT JOIN variants v ON v.product_id = p.id
        WHERE {' AND '.join(where)}
        GROUP BY p.id
        HAVING total_quantity > 0
        ORDER BY p.highlight DESC, p.updated_at DESC, p.name ASC
        """,
        tuple(params),
    )
    product_ids = [row["id"] for row in products]
    variant_map = {}
    if product_ids:
        placeholders = ",".join("?" for _ in product_ids)
        variants = query_all(
            f"""
            SELECT product_id, color, size, quantity
            FROM variants
            WHERE quantity > 0 AND product_id IN ({placeholders})
            ORDER BY color, CAST(size AS INTEGER), size
            """,
            tuple(product_ids),
        )
        for row in variants:
            entry = variant_map.setdefault(row["product_id"], {"sizes": [], "colors": [], "stock": 0})
            if row["size"] not in entry["sizes"]:
                entry["sizes"].append(row["size"])
            if row["color"] not in entry["colors"]:
                entry["colors"].append(row["color"])
            entry["stock"] += row["quantity"]
    sizes = query_all("SELECT DISTINCT size FROM variants WHERE quantity > 0 ORDER BY CAST(size AS INTEGER), size")
    colors = query_all("SELECT DISTINCT color FROM variants WHERE quantity > 0 ORDER BY color")
    categories = query_all("SELECT DISTINCT category FROM products WHERE show_public=1 AND category != '' ORDER BY category")
    highlights = [row for row in products if row["highlight"]][:6]
    spotlight = highlights[0] if highlights else (products[0] if products else None)
    new_arrivals = products[:8]
    stats = {
        "total_models": len(products),
        "total_stock": sum(item["stock"] for item in variant_map.values()) if variant_map else 0,
        "featured_count": len(highlights),
    }
    low_limit = int(settings_dict().get("low_stock_limit", "2") or 2)
    return render_template(
        "public/catalog.html",
        products=products,
        sizes=sizes,
        colors=colors,
        categories=categories,
        q=search,
        size=size,
        color=color,
        category=category,
        variant_map=variant_map,
        highlights=highlights,
        spotlight=spotlight,
        new_arrivals=new_arrivals,
        stats=stats,
        low_limit=low_limit,
    )


@app.route("/produto/<int:product_id>")
def product_detail(product_id):
    product = query_one("SELECT * FROM products WHERE id=? AND show_public=1", (product_id,))
    if not product:
        abort(404)
    variants = query_all(
        "SELECT * FROM variants WHERE product_id=? AND quantity > 0 ORDER BY color, CAST(size AS INTEGER), size",
        (product_id,),
    )
    related = query_all(
        """
        SELECT p.*, COALESCE(SUM(v.quantity),0) total_quantity
        FROM products p
        LEFT JOIN variants v ON v.product_id = p.id
        WHERE p.show_public=1 AND p.id != ?
        GROUP BY p.id
        HAVING total_quantity > 0
        ORDER BY p.highlight DESC, p.updated_at DESC
        LIMIT 4
        """,
        (product_id,),
    )
    grouped = {}
    colors = []
    sizes = []
    total_quantity = 0
    for row in variants:
        total_quantity += row["quantity"]
        grouped.setdefault(row["color"], []).append(row)
        if row["color"] not in colors:
            colors.append(row["color"])
        if row["size"] not in sizes:
            sizes.append(row["size"])
    related_map = {}
    related_ids = [row["id"] for row in related]
    if related_ids:
        placeholders = ",".join("?" for _ in related_ids)
        related_variants = query_all(
            f"SELECT product_id, color, size, quantity FROM variants WHERE quantity > 0 AND product_id IN ({placeholders}) ORDER BY color, CAST(size AS INTEGER), size",
            tuple(related_ids),
        )
        for row in related_variants:
            entry = related_map.setdefault(row["product_id"], {"sizes": [], "colors": [], "stock": 0})
            if row["size"] not in entry["sizes"]:
                entry["sizes"].append(row["size"])
            if row["color"] not in entry["colors"]:
                entry["colors"].append(row["color"])
            entry["stock"] += row["quantity"]
    low_limit = int(settings_dict().get("low_stock_limit", "2") or 2)
    return render_template(
        "public/product_detail.html",
        product=product,
        variants=variants,
        grouped_variants=grouped,
        colors=colors,
        sizes=sizes,
        total_quantity=total_quantity,
        related=related,
        related_map=related_map,
        low_limit=low_limit,
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
else:
    init_db()
