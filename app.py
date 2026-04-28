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

# -------- RUN --------
if __name__ == "__main__":
    app.run()
