from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import os

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# simple memory storage (per session, resets on restart)
chat_history = []

def ask_ai(message):
    global chat_history

    chat_history.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Jarvis, a professional AI assistant. "
                    "You are clear, structured, helpful, and act like a SaaS business assistant."
                )
            },
            *chat_history
        ]
    )

    reply = response.choices[0].message.content

    chat_history.append({"role": "assistant", "content": reply})

    return reply


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message")

    reply = ask_ai(user_message)

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)