from flask import Flask, request, redirect, session, render_template_string, send_file
import sqlite3, os
from datetime import datetime

import cloudinary
import cloudinary.uploader

# -------- CLOUDINARY CONFIG --------
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_PASSWORD = "admin123"

# -------- DATABASE --------
def init_db():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS students(
        roll INTEGER PRIMARY KEY,
        password TEXT,
        voted INTEGER DEFAULT 0,
        allowed INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        gender TEXT,
        image TEXT,
        votes INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    conn.commit()
    conn.close()

init_db()

# -------- ADMIN LOGIN --------
@app.route("/admin-login", methods=["GET","POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
        else:
            error = "Wrong password"

    return render_template_string("""
    <body style="display:flex;justify-content:center;align-items:center;height:100vh;background:#111;color:white;">
    <form method="post">
        <h3>Admin Login</h3>
        <input type="password" name="password" placeholder="Password"><br><br>
        <button>Login</button>
        <p style="color:red;">{{error}}</p>
    </form>
    </body>
    """, error=error)

# -------- ADMIN --------
@app.route("/admin", methods=["GET","POST"])
def admin():
    if "admin" not in session:
        return redirect("/admin-login")

    if request.method == "POST":
        total = int(request.form["total_students"])
        absent = request.form["absent_rolls"]
        num = int(request.form["num_candidates"])

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()

        c.execute("DELETE FROM students")
        c.execute("DELETE FROM candidates")

        for r in range(1, total+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0, 1)", (r, str(r)))

        absent_list = [int(x.strip()) for x in absent.split(",") if x.strip().isdigit()]
        for r in absent_list:
            c.execute("UPDATE students SET allowed=0 WHERE roll=?", (r,))

        for i in range(num):
            name = request.form.get(f"name_{i}")
            gender = request.form.get(f"gender_{i}")
            file = request.files.get(f"photo_{i}")

            if name and gender and file:
                upload = cloudinary.uploader.upload(file)
                image_url = upload["secure_url"]

                c.execute("INSERT INTO candidates(name,gender,image,votes) VALUES (?,?,?,0)",
                          (name, gender, image_url))

        c.execute("INSERT OR REPLACE INTO settings VALUES ('status','open')")

        conn.commit()
        conn.close()

        return "<h3>✅ Setup Done! <a href='/login'>Go to Login</a></h3>"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#141e30,#243b55);}
.card{background:#1e1e2f;color:white;border-radius:15px;}
</style>
</head>
<body>
<div class="container mt-5">
<div class="card p-4">

<h2>⚙ Admin Setup</h2>

<form method="post" enctype="multipart/form-data">
<input class="form-control mb-2" name="total_students" placeholder="Total Students">
<input class="form-control mb-2" name="absent_rolls" placeholder="Absent Rolls (e.g 2,5)">
<input class="form-control mb-3" name="num_candidates" placeholder="Number of Candidates">

{% for i in range(6) %}
<div class="bg-dark p-2 mb-2 rounded">
<input class="form-control mb-1" name="name_{{i}}" placeholder="Name">
<select class="form-control mb-1" name="gender_{{i}}">
<option>Male</option>
<option>Female</option>
</select>
<input type="file" class="form-control" name="photo_{{i}}">
</div>
{% endfor %}

<button class="btn btn-primary w-100">Start</button>
</form>

<a href="/export" class="btn btn-success mt-3 w-100">📄 Export PDF</a>

</div>
</div>
</body>
</html>
""")

# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
    error = None

    if request.method == "POST":
        roll = request.form.get("roll")
        password = request.form.get("password")

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()

        c.execute("SELECT * FROM students WHERE roll=? AND password=? AND allowed=1",(roll,password))
        user = c.fetchone()
        conn.close()

        if user:
            session["roll"] = roll
            return redirect("/vote")
        else:
            error = "Invalid login"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#141e30,#243b55);display:flex;justify-content:center;align-items:center;height:100vh;}
.card{background:#1e1e2f;color:white;padding:25px;border-radius:15px;}
</style>
</head>
<body>
<div class="card text-center">
<h3>🎓 Student Login</h3>
<p>Roll Number = Password</p>

<form method="post">
<input class="form-control mb-2" name="roll" placeholder="Roll Number" required>
<input type="password" class="form-control mb-2" name="password" placeholder="Password" required>

{% if error %}<p class="text-danger">{{error}}</p>{% endif %}

<button class="btn btn-primary w-100">Login</button>
</form>
</div>
</body>
</html>
""", error=error)

# -------- VOTE --------
@app.route("/vote", methods=["GET","POST"])
def vote():
    if "roll" not in session:
        return redirect("/login")

    roll = session["roll"]

    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    c.execute("SELECT voted FROM students WHERE roll=?", (roll,))
    if c.fetchone()[0] == 1:
        return "Already voted"

    if request.method == "POST":
        male = request.form.get("male")
        female = request.form.get("female")

        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (male,))
        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (female,))
        c.execute("UPDATE students SET voted=1 WHERE roll=?", (roll,))
        conn.commit()
        conn.close()

        return "<h3>✅ Vote Submitted</h3>"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
<style>
body{background:#111;color:white;}
.card{cursor:pointer;}
input{display:none;}
input:checked + .card{border:3px solid gold;}
</style>
</head>
<body>
<div class="container mt-4">

<form method="post">

<h4>Male</h4>
{% for c in male %}
<label>
<input type="radio" name="male" value="{{c[0]}}">
<div class="card bg-dark p-2 mb-2">
<img src="{{c[3]}}" style="width:100%;height:200px;object-fit:cover;">
<p>{{c[1]}}</p>
</div>
</label>
{% endfor %}

<h4>Female</h4>
{% for c in female %}
<label>
<input type="radio" name="female" value="{{c[0]}}">
<div class="card bg-dark p-2 mb-2">
<img src="{{c[3]}}" style="width:100%;height:200px;object-fit:cover;">
<p>{{c[1]}}</p>
</div>
</label>
{% endfor %}

<button class="btn btn-primary w-100 mt-3">Submit</button>

</form>
</div>
</body>
</html>
""", male=male, female=female)

# -------- RESULT --------
@app.route("/result")
def result():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()
    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    html = "<h2 style='text-align:center'>📊 Results</h2>"

    for d in data:
        html += f"<p>{d[1]} - {d[4]} votes</p>"

    return html

# -------- RUN --------
if __name__ == "__main__":
    app.run()
