from flask import Flask, render_template, request, jsonify, session, redirect
from openai import OpenAI
from dotenv import load_dotenv

import sqlite3
import os
print("CURRENT FOLDER:", os.getcwd())
print("ENV FILE EXISTS:", os.path.exists(".env"))
import hashlib
import stripe

# =========================
# LOAD ENV FILE
# =========================
load_dotenv()
print("OPENAI KEY:", os.getenv("OPENAI_API_KEY"))
# =========================
# APP INIT
# =========================
app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

# =========================
# OPENAI SETUP
# =========================
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# =========================
# STRIPE SETUP
# =========================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

DOMAIN = "http://127.0.0.1:10000"

# =========================
# DATABASE
# =========================
DB = "jarvis.db"


def init_db():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            plan TEXT DEFAULT 'free'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            role TEXT,
            content TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()


# =========================
# HELPERS
# =========================
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


def current_user():
    return session.get("email")


def save_message(email, role, content):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        INSERT INTO messages (email, role, content)
        VALUES (?, ?, ?)
    """, (email, role, content))

    conn.commit()
    conn.close()


def load_history(email):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        SELECT role, content FROM messages
        WHERE email=?
    """, (email,))

    data = c.fetchall()
    conn.close()

    return [{"role": r, "content": m} for r, m in data]


# =========================
# AI FUNCTION
# =========================
def ask_ai(email, message):

    save_message(email, "user", message)

    history = load_history(email)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are Jarvis AI assistant. Be helpful and smart."
            },
            *history
        ]
    )

    reply = response.choices[0].message.content

    save_message(email, "assistant", reply)

    return reply


# =========================
# ROUTES
# =========================
@app.route("/")
def home():

    if not current_user():
        return redirect("/login")

    return render_template("index.html", email=current_user())


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        data = request.json
        email = data["email"]
        password = hash_password(data["password"])

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute("""
            SELECT * FROM users
            WHERE email=? AND password=?
        """, (email, password))

        user = c.fetchone()
        conn.close()

        if user:
            session["email"] = email
            return jsonify({"success": True})

        return jsonify({"error": "Invalid login"})

    return render_template("login.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        data = request.json

        email = data["email"]
        password = hash_password(data["password"])

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        try:
            c.execute("""
                INSERT INTO users (email, password)
                VALUES (?, ?)
            """, (email, password))

            conn.commit()

        except:
            return jsonify({"error": "User exists"})

        conn.close()

        return jsonify({"success": True})

    return render_template("register.html")


# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
def chat():

    if not current_user():
        return jsonify({"reply": "Login required"})

    data = request.json
    message = data["message"]

    reply = ask_ai(current_user(), message)

    return jsonify({"reply": reply})


# ---------------- STRIPE ----------------
@app.route("/upgrade/<plan>")
def upgrade(plan):

    prices = {
        "basic": 500,
        "pro": 1500
    }

    session_checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"Jarvis {plan}"
                },
                "unit_amount": prices.get(plan, 500),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=DOMAIN + "/success/" + plan,
        cancel_url=DOMAIN + "/"
    )

    return redirect(session_checkout.url)


@app.route("/success/<plan>")
def success(plan):

    if current_user():

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute("""
            UPDATE users
            SET plan=?
            WHERE email=?
        """, (plan, current_user()))

        conn.commit()
        conn.close()

    return redirect("/")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM messages")
    messages = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE plan!='free'")
    paid = c.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        users=users,
        messages=messages,
        paid=paid
    )


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)