from flask import Flask, render_template, request
from openai import OpenAI
import os

app = Flask(__name__)

# Load API key from environment variable (SAFE METHOD)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_ai(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Jarvis, a helpful assistant."},
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
    app.run(debug=True)