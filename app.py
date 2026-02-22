from flask import Flask, render_template, request, redirect, jsonify, session
import sqlite3
import os
import requests  # Required for is.gd API
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "secure_key_for_asin_app" 
app.permanent_session_lifetime = timedelta(days=30) 

# --- LOGIN CREDENTIALS ---
USERNAME = "admin123"
# Your password: its~your-boss
PASSWORD_HASH = generate_password_hash("its~your-boss") 
# -------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# --- DATABASE INITIALIZATION FOR TERMUX ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS links 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  asin TEXT, 
                  keyword_block TEXT)''')
    conn.commit()
    conn.close()

# Ensure the table exists before the app starts
init_db()
# ------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == USERNAME and check_password_hash(PASSWORD_HASH, pw):
            session.permanent = True
            session['logged_in'] = True
            return redirect("/")
        return "Invalid Username or Password", 401
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
    c.execute("SELECT id, asin, keyword_block FROM links WHERE asin LIKE ?", ('%' + asin + '%',))
    results = c.fetchall()
    conn.close()
    return jsonify({"results": results, "logged_in": session.get('logged_in')})

@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get('logged_in'): return redirect("/login")
    if request.method == "POST":
        asin = request.form["asin"]
        kw = request.form["keyword_block"]
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO links (asin, keyword_block) VALUES (?, ?)", (asin, kw))
        conn.commit(); conn.close()
        return redirect("/")
    return render_template("add.html")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get('logged_in'): return redirect("/login")
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    if request.method == "POST":
        c.execute("UPDATE links SET asin=?, keyword_block=? WHERE id=?", (request.form["asin"], request.form["keyword_block"], id))
        conn.commit(); conn.close()
        return redirect("/")
    c.execute("SELECT * FROM links WHERE id=?", (id,))
    item = c.fetchone(); conn.close()
    return render_template("edit.html", item=item)

@app.route("/delete/<int:id>", methods=["DELETE"])
def delete(id):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 403
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM links WHERE id=?", (id,))
    conn.commit(); conn.close()
    return jsonify({"status": "deleted"})

@app.route("/generator")
def generator():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    asin = request.form.get("asin", "").strip()
    if not asin:
        return redirect("/generator")
    
    amazon_link = f"https://www.amazon.com/dp/{asin}/?tag=ahd03c-20"
    
    # Shorten using is.gd
    try:
        api_url = f"https://is.gd/create.php?format=simple&url={amazon_link}"
        response = requests.get(api_url, timeout=5)
        short_link = response.text.strip() if response.status_code == 200 else amazon_link
    except:
        short_link = amazon_link
        
    return render_template("index.html", amazon_link=amazon_link, short_link=short_link)

if __name__ == "__main__":
    app.run(debug=False)
