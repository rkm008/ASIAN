from flask import Flask, render_template, request, redirect, jsonify, session, url_for
import sqlite3
import os
import string
import random
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "secure_key_for_asin_app"
app.permanent_session_lifetime = timedelta(days=30)

USERNAME = "admin123"
PASSWORD_HASH = generate_password_hash("its~your-boss")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  asin TEXT,
                  keyword_block TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS urls
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  original_url TEXT UNIQUE,
                  short_code TEXT UNIQUE)''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (id INTEGER PRIMARY KEY, 
                  key TEXT UNIQUE, 
                  value TEXT)''')
    
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('amazon_tag', 'pplc7-20')")

    conn.commit()
    conn.close()

init_db()

def get_tag():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='amazon_tag'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else "pplc7-20"

def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits

    while True:
        code = ''.join(random.choice(chars) for _ in range(length))

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM urls WHERE short_code=?", (code,))
        exists = c.fetchone()
        conn.close()

        if not exists:
            return code

def shorten_url(original_url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT short_code FROM urls WHERE original_url=?", (original_url,))
    row = c.fetchone()

    if row:
        conn.close()
        return row[0]

    short_code = generate_short_code()

    c.execute(
        "INSERT INTO urls (original_url, short_code) VALUES (?, ?)",
        (original_url, short_code)
    )

    conn.commit()
    conn.close()

    return short_code

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")

        if user == USERNAME and check_password_hash(PASSWORD_HASH, pw):
            session.permanent = True
            session['logged_in'] = True
            return redirect("/")

        return render_template("login.html", error="Invalid Username or Password")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    return redirect("/")

@app.route("/")
def index():
    return render_template("search.html", logged_in=session.get('logged_in'))

@app.route("/live_search", methods=["POST"])
def live_search():
    asin = request.json.get("asin", "").strip()

    if not asin:
        return jsonify({"results": [], "logged_in": session.get('logged_in')})

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT id, asin, keyword_block FROM links WHERE asin LIKE ?",
        ('%' + asin + '%',)
    )

    results = c.fetchall()
    conn.close()

    return jsonify({"results": results, "logged_in": session.get('logged_in')})

@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get('logged_in'):
        return redirect("/login")

    if request.method == "POST":
        asin = request.form["asin"]
        kw = request.form["keyword_block"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute(
            "INSERT INTO links (asin, keyword_block) VALUES (?, ?)",
            (asin, kw)
        )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add.html")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get('logged_in'):
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if request.method == "POST":
        c.execute(
            "UPDATE links SET asin=?, keyword_block=? WHERE id=?",
            (request.form["asin"], request.form["keyword_block"], id)
        )

        conn.commit()
        conn.close()

        return redirect("/")

    c.execute("SELECT * FROM links WHERE id=?", (id,))
    item = c.fetchone()
    conn.close()

    return render_template("edit.html", item=item)

@app.route("/delete/<int:id>", methods=["DELETE"])
def delete(id):
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 403

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM links WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "deleted"})

@app.route("/generator")
def generator():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM urls")
    total_count = c.fetchone()[0]
    conn.close()

    amazon_link = session.pop('gen_amazon', None)
    short_link = session.pop('gen_short', None)

    return render_template("index.html",
                           total_count=total_count,
                           amazon_link=amazon_link,
                           short_link=short_link)

@app.route("/generate", methods=["POST"])
def generate():
    asin = request.form.get("asin", "").strip()

    if not asin:
        return redirect(url_for("generator"))

    tag = get_tag()
    amazon_link = f"https://www.amazon.com/dp/{asin}/?tag={tag}"
    short_code = shorten_url(amazon_link)
    short_link = request.host_url.rstrip("/") + "/s/" + short_code

    session['gen_amazon'] = amazon_link
    session['gen_short'] = short_link

    return redirect(url_for("generator"))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not session.get('logged_in'):
        return redirect("/login")

    if request.method == "POST":
        new_tag = request.form.get("amazon_tag", "").strip()
        if new_tag:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE settings SET value=? WHERE key='amazon_tag'", (new_tag,))
            conn.commit()
            conn.close()
        return redirect(url_for("generator"))

    current_tag = get_tag()
    return render_template("settings.html", current_tag=current_tag, logged_in=True)

@app.route("/s/<short_code>")
def redirect_short(short_code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT original_url FROM urls WHERE short_code=?",
        (short_code,)
    )

    row = c.fetchone()
    conn.close()

    if row:
        return redirect(row[0])

    return "Link not found", 404

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="5000")
