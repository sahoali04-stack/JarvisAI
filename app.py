from flask import Flask, render_template, request, jsonify, session, redirect
from openai import OpenAI
from dotenv import load_dotenv
import sqlite3
import os
import hashlib

# =========================
# LOAD ENV
# =========================
load_dotenv()

app = Flask(__name__)
app.secret_key = "jarvis_secret_key_change_this"

# =========================
# OPENAI
# =========================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# DB
# =========================
DB = "jarvis.db"


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
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
            {"role": "system", "content": "You are Jarvis AI assistant."},
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

    if request.method == "GET":
        return render_template("login.html")

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

    return jsonify({"success": False})


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")

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


# ---------------- CHAT ----------------
@app.route("/chat", methods=["POST"])
def chat():

    if not current_user():
        return jsonify({"reply": "Login required"})

    data = request.json
    message = data.get("message")

    reply = ask_ai(current_user(), message)

    return jsonify({"reply": reply})


# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)