from flask import Flask, request, redirect, session, render_template_string, send_file
import sqlite3, os
from werkzeug.utils import secure_filename
from datetime import datetime

# PDF imports
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

    c.execute("""CREATE TABLE IF NOT EXISTS audit(
        roll INTEGER,
        timestamp TEXT
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
    <html>
    <body style="display:flex;justify-content:center;align-items:center;height:100vh;background:#1f1c2c;color:white;">
    <form method="post">
        <h3>Admin Login</h3>
        <input type="password" name="password" placeholder="Password"><br><br>
        <button>Login</button>
        <p style="color:red;">{{error}}</p>
    </form>
    </body>
    </html>
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
        c.execute("DELETE FROM audit")

        for r in range(1, total_students+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0, 1)", (r, str(r)))

        absent_list = [int(x.strip()) for x in absent_rolls.split(",") if x.strip().isdigit()]
        for r in absent_list:
            c.execute("UPDATE students SET allowed=0 WHERE roll=?", (r,))

        present_count = total_students - len(absent_list)

        for i in range(num_candidates):
            name = request.form.get(f"name_{i}")
            gender = request.form.get(f"gender_{i}")
            file = request.files.get(f"photo_{i}")

            if name and gender and file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                c.execute("INSERT INTO candidates(name,gender,image,votes) VALUES (?,?,?,0)",
                          (name, gender, filename))

        c.execute("INSERT OR REPLACE INTO settings VALUES ('present_count',?)", (str(present_count),))
        c.execute("INSERT OR REPLACE INTO settings VALUES ('status','open')")

        conn.commit()
        conn.close()

        return "<h3>Setup Done! <a href='/login'>Go to Login</a></h3>"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);}
.card{background:#2c2c3e;color:white;border-radius:20px;}
</style>
</head>
<body>
<div class="container mt-5">
<div class="card p-4">

<h2 class="text-center">⚙ Admin Setup</h2>

<form method="post" enctype="multipart/form-data">
<input class="form-control mb-2" name="total_students" placeholder="Total Students">
<input class="form-control mb-2" name="absent_rolls" placeholder="Absent Rolls (e.g. 2,5)">
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

<button class="btn btn-primary w-100">Start Election</button>
</form>

<br>
<a href="/close" class="btn btn-danger w-100">Close Voting</a>
<a href="/export" class="btn btn-success w-100 mt-2">📄 Export PDF</a>

</div>
</div>
</body>
</html>
""")

# -------- EXPORT PDF --------
@app.route("/export")
def export():
    if "admin" not in session:
        return "Unauthorized"

    conn = sqlite3.connect("voting.db")
    c = conn.cursor()
    c.execute("SELECT name, gender, votes FROM candidates")
    data = c.fetchall()
    conn.close()

    file_path = "results.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph("Election Results", styles["Title"]))
    content.append(Spacer(1, 20))

    for d in data:
        text = f"{d[0]} ({d[1]}) - {d[2]} votes"
        content.append(Paragraph(text, styles["Normal"]))
        content.append(Spacer(1, 10))

    doc.build(content)

    return send_file(file_path, as_attachment=True)
# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
    error = None

    if request.method == "POST":
        roll = request.form["roll"]
        password = request.form["password"]

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE roll=? AND password=? AND allowed=1", (roll,password))
        user = c.fetchone()
        conn.close()

        if user:
            session["roll"] = roll
            return redirect("/vote")
        else:
            error = "Invalid or not allowed"

    return render_template_string("""
    <html>
    <body style="background:#1f1c2c;color:white;display:flex;justify-content:center;align-items:center;height:100vh;">
    <form method="post">
        <h3>Student Login</h3>
        <input name="roll" placeholder="Roll"><br><br>
        <input type="password" name="password" placeholder="Password"><br><br>
        <button>Login</button>
        <p style="color:red;">{{error}}</p>
    </form>
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

        return "<h3>Vote Submitted</h3>"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    return render_template_string("""
    <h2>Vote</h2>
    <form method="post">

    <h3>Male</h3>
    {% for c in male %}
        <input type="radio" name="male" value="{{c[0]}}"> {{c[1]}}<br>
    {% endfor %}

    <h3>Female</h3>
    {% for c in female %}
        <input type="radio" name="female" value="{{c[0]}}"> {{c[1]}}<br>
    {% endfor %}

    <button>Submit</button>
    </form>
    """, male=male, female=female)
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

    html = """
    <html>
    <head>
    <style>
    body{background:#121212;color:white;font-family:Arial;}
    .card{background:white;color:black;padding:10px;margin:10px;border-radius:10px;}
    .winner{border:3px solid gold;}
    </style>
    </head>
    <body>

    <h2 style="text-align:center;">📊 Results</h2>
    """

    # leaderboard
    for i, d in enumerate(sorted_data):
        percent = (d[4]/total_votes)*100

        html += f"""
        <div class="card">
        <b>#{i+1} {d[1]} ({d[2]})</b><br>
        Votes: {d[4]} ({percent:.1f}%)
        </div>
        """

    # winners
    html += "<h2 style='text-align:center;'>🏆 Winners</h2><div style='display:flex;justify-content:space-around;'>"

    if male_winner:
        html += f"""
        <div class="card winner">
        <h3>Male Winner</h3>
        <img src="/static/uploads/{male_winner[3]}" height="150"><br>
        {male_winner[1]}
        </div>
        """

    if female_winner:
        html += f"""
        <div class="card winner">
        <h3>Female Winner</h3>
        <img src="/static/uploads/{female_winner[3]}" height="150"><br>
        {female_winner[1]}
        </div>
        """

    html += "</div></body></html>"

    return html
# -------- RUN --------
if __name__ == "__main__":
    app.run()
