from flask import Flask, render_template, request
from openai import OpenAI
import os

app = Flask(__name__)

# Get API key from Render environment variables
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_ai(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Jarvis, an advanced AI assistant. "
                        "You are extremely clear, structured, and helpful. "
                        "You always give short, practical answers first, then details if needed. "
                        "You behave like a professional assistant used in a business environment."
                    )
                },
                {"role": "user", "content": message}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"


@app.route("/", methods=["GET", "POST"])
def home():
    response = ""

    if request.method == "POST":
        user_message = request.form.get("message")

        if user_message:
            response = ask_ai(user_message)

    return render_template("index.html", response=response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)