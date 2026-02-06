from flask import Flask, render_template, request, redirect, session
import sqlite3
from collections import Counter
import json

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE CONNECTION ----------------

def get_db():
    return sqlite3.connect("database.db")


# ---------------- PRODUCTS FROM JSON ----------------

def load_all_products():
    """Load all products from product1.json and product2.json as a unified list of dicts."""
    products = []
    for filename in ("product1.json", "product2.json"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            continue

        for item in data:
            products.append({
                "id": item.get("id"),
                "name": item.get("mobile_device_model"),
                "price": item.get("price_inr"),
                "description": item.get("description"),
                "image": item.get("image"),
            })
    return products


def get_product_by_id(pid: int):
    """Find a single product dict by id from the JSON data."""
    for product in load_all_products():
        if product.get("id") == pid:
            return product
    return None


# ---------------- HOME ----------------

@app.route('/')
def home():
    # products and featured slider data from JSON (not from database)
    products = load_all_products()

    # use last 10 products as featured for the top slider
    if len(products) > 10:
        featured_products = products[-10:]
    else:
        featured_products = products

    # load product1.json for the 2nd slider (Amazon-style carousel)
    try:
        with open("product1.json", "r", encoding="utf-8") as f:
            product1_items = json.load(f)
    except FileNotFoundError:
        product1_items = []

    return render_template(
        "home.html",
        products=products,
        featured_products=featured_products,
        product1_items=product1_items,
    )

# ---------------- REGISTER ----------------

@app.route('/register', methods=['GET','POST'])
def register():
    next_page = request.args.get('next') or request.form.get('next') or '/'

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO users(username,password) VALUES (?,?)",
                       (username,password))
        db.commit()

        # log the user in immediately after successful registration
        user_id = cursor.lastrowid
        db.close()

        session['user_id'] = user_id
        session['username'] = username

        return redirect(next_page)

    return render_template("register.html", next=next_page)

# ---------------- LOGIN ----------------

@app.route('/login', methods=['GET','POST'])
def login():
    # where to go after successful login
    next_page = request.args.get('next') or request.form.get('next') or '/'

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?",
                       (username,password))
        user = cursor.fetchone()
        db.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(next_page)
        else:
            # stay on the login page and show an error message
            return render_template("login.html", error="Invalid username or password", next=next_page)

    return render_template("login.html", error=None, next=next_page)

# ---------------- LOGOUT ----------------

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- ADD PRODUCT (ADMIN) ----------------

@app.route('/add_product', methods=['GET','POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        desc = request.form['description']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO products(name,price,description) VALUES (?,?,?)",
                       (name,price,desc))
        db.commit()
        db.close()

        return redirect('/')

    return render_template("add_product.html")

# ---------------- ADD TO CART ----------------

@app.route('/add_to_cart/<int:pid>')
def add_to_cart(pid):
    # only logged-in users can add to cart
    if 'user_id' not in session:
        return redirect(f"/login?next=/product/{pid}")

    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append(pid)
    session.modified = True

    return redirect('/')

# ---------------- VIEW CART ----------------

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect("/login?next=/cart")

    if 'cart' not in session:
        return render_template("cart.html", items=[], total_quantity=0, total_price=0)

    # count quantities of each product id in cart
    counts = Counter(session['cart'])
    product_ids = list(counts.keys())

    if not product_ids:
        return render_template("cart.html", items=[], total_quantity=0, total_price=0)

    # load product data from JSON instead of database
    all_products = load_all_products()
    products_by_id = {p["id"]: p for p in all_products}

    items = []
    total_quantity = 0
    total_price = 0.0

    for pid in product_ids:
        product = products_by_id.get(pid)
        if not product:
            continue
        qty = counts.get(pid, 0)
        price = product["price"]
        subtotal = qty * price
        total_quantity += qty
        total_price += subtotal
        items.append({
            "id": pid,
            "name": product["name"],
            "price": price,
            "description": product["description"],
            "image": product["image"],
            "quantity": qty,
            "subtotal": subtotal,
        })

    return render_template("cart.html", items=items, total_quantity=total_quantity, total_price=total_price)


# ---------------- PRODUCT DETAIL ----------------

@app.route('/product/<int:pid>')
def product_detail(pid):

    if 'user_id' not in session:
        return redirect(f"/login?next=/product/{pid}")

    product = get_product_by_id(pid)
    if not product:
        return "Product not found", 404

    return render_template("product_detail.html", product=product)


# ---------------- CART QUANTITY CONTROLS ----------------

@app.route('/cart/increase/<int:pid>')
def cart_increase(pid):
    if 'user_id' not in session:
        return redirect("/login?next=/cart")

    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append(pid)
    session.modified = True
    return redirect('/cart')


@app.route('/cart/decrease/<int:pid>')
def cart_decrease(pid):
    if 'user_id' not in session:
        return redirect("/login?next=/cart")

    if 'cart' in session and pid in session['cart']:
        session['cart'].remove(pid)
        session.modified = True

    return redirect('/cart')

# ---------------- PLACE ORDER ----------------

@app.route('/order')
def order():

    if 'user_id' not in session:
        return redirect('/login')

    if 'cart' not in session:
        return "No items in cart"

    db = get_db()
    cursor = db.cursor()

    for pid in session['cart']:
        cursor.execute("INSERT INTO orders(user_id,product_id) VALUES (?,?)",
                       (session['user_id'], pid))

    db.commit()
    db.close()

    session.pop('cart')

    return "Order Placed Successfully!"

# ---------------- VIEW ORDERS ----------------

@app.route('/orders')
def orders():

    if 'user_id' not in session:
        return redirect('/login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT product_id FROM orders WHERE user_id=?", (session['user_id'],))
    rows = cursor.fetchall()
    db.close()

    all_products = load_all_products()
    products_by_id = {p["id"]: p for p in all_products}

    orders_data = []
    for (pid,) in rows:
        product = products_by_id.get(pid)
        if product:
            orders_data.append((product["name"], product["price"]))

    return render_template("orders.html", orders=orders_data)

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)