from flask import Flask, request, redirect, session, render_template_string, send_file
import sqlite3, os
from werkzeug.utils import secure_filename
from datetime import datetime

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_PASSWORD = "admin123"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -------- DATABASE --------
def init_db():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS students(
        roll INTEGER PRIMARY KEY,
        password TEXT,
        voted INTEGER DEFAULT 0,
        allowed INTEGER DEFAULT 0
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
    <body style="display:flex;justify-content:center;align-items:center;height:100vh;background:#1f1c2c;color:white;">
    <form method="post">
        <h3>Admin Login</h3>
        <input type="password" name="password"><br><br>
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
        total_students = int(request.form["total_students"])
        absent_rolls = request.form["absent_rolls"]
        num_candidates = int(request.form["num_candidates"])

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()

        c.execute("DELETE FROM students")
        c.execute("DELETE FROM candidates")

        for r in range(1, total_students+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0, 1)", (r, str(r)))

        absent_list = [int(x.strip()) for x in absent_rolls.split(",") if x.strip().isdigit()]
        for r in absent_list:
            c.execute("UPDATE students SET allowed=0 WHERE roll=?", (r,))

        for i in range(num_candidates):
            name = request.form.get(f"name_{i}")
            gender = request.form.get(f"gender_{i}")
            file = request.files.get(f"photo_{i}")

            if name and gender and file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                c.execute("INSERT INTO candidates(name,gender,image,votes) VALUES (?,?,?,0)",
                          (name, gender, filename))

        c.execute("INSERT OR REPLACE INTO settings VALUES ('status','open')")

        conn.commit()
        conn.close()

        return "<h3>Setup Done! <a href='/login'>Go to Login</a></h3>"

    return render_template_string("""
    <form method="post" enctype="multipart/form-data">
    Total Students:<input name="total_students"><br>
    Absent:<input name="absent_rolls"><br>
    Candidates:<input name="num_candidates"><br><br>

    {% for i in range(6) %}
    <input name="name_{{i}}">
    <select name="gender_{{i}}">
    <option>Male</option><option>Female</option>
    </select>
    <input type="file" name="photo_{{i}}"><br>
    {% endfor %}

    <button>Start</button>
    </form>

    <a href="/export">Export PDF</a><br>
    <a href="/close">Close Voting</a>
    """)

# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
    error = None

    if request.method == "POST":
        roll = request.form["roll"]
        password = request.form["password"]

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
    <form method="post">
    Roll:<input name="roll"><br>
    Password:<input type="password" name="password"><br>
    <button>Login</button>
    <p style="color:red;">{{error}}</p>
    </form>
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
        return "Vote Submitted"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    return render_template_string("""
    <form method="post">

    <h3>Male</h3>
    {% for c in male %}
    <input type="radio" name="male" value="{{c[0]}}">{{c[1]}}<br>
    {% endfor %}

    <h3>Female</h3>
    {% for c in female %}
    <input type="radio" name="female" value="{{c[0]}}">{{c[1]}}<br>
    {% endfor %}

    <button>Submit</button>
    </form>
    """, male=male, female=female)

# -------- RESULT --------
@app.route("/result")
def result():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    total_votes = sum([d[4] for d in data]) or 1
    sorted_data = sorted(data, key=lambda x: x[4], reverse=True)

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    male_winner = max(male, key=lambda x: x[4]) if male else None
    female_winner = max(female, key=lambda x: x[4]) if female else None

    html = "<h2>Results</h2>"

    for i,d in enumerate(sorted_data):
        percent = (d[4]/total_votes)*100
        html += f"<p>{d[1]} ({d[2]}) - {d[4]} votes ({percent:.1f}%)</p>"

    if male_winner:
        html += f"<h3>Male Winner: {male_winner[1]}</h3>"
        html += f"<img src='/static/uploads/{male_winner[3]}' height='150'>"

    if female_winner:
        html += f"<h3>Female Winner: {female_winner[1]}</h3>"
        html += f"<img src='/static/uploads/{female_winner[3]}' height='150'>"

    return html

# -------- EXPORT --------
@app.route("/export")
def export():
    if "admin" not in session:
        return "Unauthorized"

    conn = sqlite3.connect("voting.db")
    c = conn.cursor()
    c.execute("SELECT name, gender, votes FROM candidates")
    data = c.fetchall()
    conn.close()

    doc = SimpleDocTemplate("results.pdf")
    styles = getSampleStyleSheet()

    content = [Paragraph("Election Results", styles["Title"]), Spacer(1,20)]

    for d in data:
        content.append(Paragraph(f"{d[0]} ({d[1]}) - {d[2]} votes", styles["Normal"]))
        content.append(Spacer(1,10))

    doc.build(content)

    return send_file("results.pdf", as_attachment=True)

# -------- CLOSE --------
@app.route("/close")
def close():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES ('status','closed')")
    conn.commit()
    conn.close()
    return "Voting Closed"

if __name__ == "__main__":
    app.run()
