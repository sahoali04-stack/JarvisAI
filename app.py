from flask import Flask, render_template, request, jsonify, session, redirect
from openai import OpenAI
import sqlite3
import os
import hashlib
import stripe

app = Flask(__name__)

# ---------------- SECRET KEY ----------------
app.secret_key = "CHANGE_THIS_SECRET_KEY"

# ---------------- OPENAI ----------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ---------------- STRIPE ----------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# CHANGE THIS AFTER DEPLOY
DOMAIN = "http://localhost:10000"

# ---------------- DATABASE ----------------
DB = "jarvis.db"


# =========================
# DATABASE INIT
# =========================
def init_db():

    conn = sqlite3.connect(DB)

    c = conn.cursor()

    # USERS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            plan TEXT DEFAULT 'free'
        )
    """)

    # MESSAGES TABLE
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
# PASSWORD HASH
# =========================
def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# =========================
# CURRENT USER
# =========================
def current_user():

    return session.get("email")


# =========================
# SAVE MESSAGE
# =========================
def save_message(email, role, content):

    conn = sqlite3.connect(DB)

    c = conn.cursor()

    c.execute(
        """
        INSERT INTO messages
        (email, role, content)
        VALUES (?, ?, ?)
        """,
        (email, role, content)
    )

    conn.commit()

    conn.close()


# =========================
# LOAD HISTORY
# =========================
def load_history(email):

    conn = sqlite3.connect(DB)

    c = conn.cursor()

    c.execute(
        """
        SELECT role, content
        FROM messages
        WHERE email=?
        """,
        (email,)
    )

    rows = c.fetchall()

    conn.close()

    history = []

    for row in rows:

        history.append({
            "role": row[0],
            "content": row[1]
        })

    return history


# =========================
# ASK AI
# =========================
def ask_ai(email, message):

    # SAVE USER MESSAGE
    save_message(
        email,
        "user",
        message
    )

    history = load_history(email)

    response = client.chat.completions.create(

        model="gpt-4o-mini",

        messages=[
            {
                "role": "system",
                "content":
                """
                You are Jarvis,
                an advanced voice AI assistant.
                Be smart, helpful,
                professional and friendly.
                """
            },

            *history
        ]
    )

    reply = response.choices[0].message.content

    # SAVE AI MESSAGE
    save_message(
        email,
        "assistant",
        reply
    )

    return reply


# =========================
# HOME
# =========================
@app.route("/")
def home():

    if not current_user():

        return redirect("/login")

    return render_template(
        "index.html",
        email=current_user()
    )


# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        data = request.json

        email = data["email"]

        password = hash_password(
            data["password"]
        )

        try:

            conn = sqlite3.connect(DB)

            c = conn.cursor()

            c.execute(
                """
                INSERT INTO users
                (email, password)
                VALUES (?, ?)
                """,
                (email, password)
            )

            conn.commit()

            conn.close()

            return jsonify({
                "success": True
            })

        except:

            return jsonify({
                "error": "User already exists"
            })

    return render_template(
        "register.html"
    )


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        data = request.json

        email = data["email"]

        password = hash_password(
            data["password"]
        )

        conn = sqlite3.connect(DB)

        c = conn.cursor()

        c.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            AND password=?
            """,
            (email, password)
        )

        user = c.fetchone()

        conn.close()

        if user:

            session["email"] = email

            return jsonify({
                "success": True
            })

        return jsonify({
            "error": "Invalid credentials"
        })

    return render_template(
        "login.html"
    )


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# CHAT API
# =========================
@app.route("/chat", methods=["POST"])
def chat():

    email = current_user()

    if not email:

        return jsonify({
            "reply": "Please login first."
        })

    data = request.json

    message = data.get("message")

    if not message:

        return jsonify({
            "reply": "Empty message."
        })

    try:

        reply = ask_ai(
            email,
            message
        )

        return jsonify({
            "reply": reply
        })

    except Exception as e:

        return jsonify({
            "reply": f"Error: {str(e)}"
        })


# =========================
# STRIPE PAYMENT
# =========================
@app.route("/upgrade/<plan>")
def upgrade(plan):

    prices = {
        "basic": 500,
        "pro": 1500
    }

    amount = prices.get(
        plan,
        500
    )

    checkout = stripe.checkout.Session.create(

        payment_method_types=[
            "card"
        ],

        line_items=[{

            "price_data": {

                "currency": "usd",

                "product_data": {
                    "name": f"Jarvis {plan.capitalize()} Plan"
                },

                "unit_amount": amount
            },

            "quantity": 1
        }],

        mode="payment",

        success_url=
        DOMAIN + "/success/" + plan,

        cancel_url=
        DOMAIN + "/"
    )

    return redirect(
        checkout.url
    )


# =========================
# PAYMENT SUCCESS
# =========================
@app.route("/success/<plan>")
def success(plan):

    email = current_user()

    conn = sqlite3.connect(DB)

    c = conn.cursor()

    c.execute(
        """
        UPDATE users
        SET plan=?
        WHERE email=?
        """,
        (plan, email)
    )

    conn.commit()

    conn.close()

    return redirect("/")


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect(DB)

    c = conn.cursor()

    # USERS
    c.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = c.fetchone()[0]

    # MESSAGES
    c.execute(
        "SELECT COUNT(*) FROM messages"
    )

    messages = c.fetchone()[0]

    # PAID USERS
    c.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE plan != 'free'
        """
    )

    paid_users = c.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        users=users,
        messages=messages,
        paid_users=paid_users
    )


# =========================
# ADMIN PANEL
# =========================
@app.route("/admin")
def admin():

    conn = sqlite3.connect(DB)

    c = conn.cursor()

    c.execute(
        """
        SELECT email, plan
        FROM users
        """
    )

    users = c.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users
    )


# =========================
# RUN APP
# =========================
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=True
    )