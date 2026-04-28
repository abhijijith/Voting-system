from flask import Flask, request, redirect, session, render_template_string
import sqlite3, os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_PASSWORD = "admin123"  # 🔐 change this

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

        # create students
        for r in range(1, total_students+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0, 1)", (r, str(r)))

        # block absent
        absent_list = [int(x.strip()) for x in absent_rolls.split(",") if x.strip().isdigit()]
        for r in absent_list:
            c.execute("UPDATE students SET allowed=0 WHERE roll=?", (r,))

        present_count = total_students - len(absent_list)

        # candidates
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
<a href="/export" class="btn btn-success w-100 mt-2">Export Results</a>

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
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);display:flex;justify-content:center;align-items:center;height:100vh;}
.card{background:#2c2c3e;color:white;border-radius:20px;}
</style>
</head>
<body>
<div class="card p-4 text-center">
<h3>Student Login</h3>
<p>Roll = Password</p>
<form method="post">
<input class="form-control mb-2" name="roll">
<input type="password" class="form-control mb-2" name="password">
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

    c.execute("SELECT value FROM settings WHERE key='status'")
    status = c.fetchone()[0]
    if status != "open":
        return "Voting closed"

    c.execute("SELECT voted FROM students WHERE roll=?", (roll,))
    if c.fetchone()[0] == 1 or session.get("voted"):
        return "Already voted"

    if request.method == "POST":
        male = request.form.get("male")
        female = request.form.get("female")

        if not male or not female:
            return "Select both"

        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (male,))
        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (female,))
        c.execute("UPDATE students SET voted=1 WHERE roll=?", (roll,))
        c.execute("INSERT INTO audit VALUES (?,?)", (roll, datetime.now().isoformat()))

        conn.commit()
        conn.close()

        session["voted"] = True
        return "<h3>Vote Submitted</h3>"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);}
.card{cursor:pointer;position:relative;transition:0.3s;}
.card:hover{transform:scale(1.05);}
input{display:none;}
input:checked + .card{border:3px solid gold;box-shadow:0 0 20px gold;}
.overlay{position:absolute;bottom:0;width:100%;background:rgba(0,0,0,0.7);color:white;padding:5px;}
</style>
</head>
<body class="text-light">
<div class="container mt-4">
<h2 class="text-center">Vote</h2>

<form method="post">

<h4>Male</h4>
<div class="row">
{% for c in male %}
<div class="col-md-4">
<label>
<input type="radio" name="male" value="{{c[0]}}" required>
<div class="card bg-dark p-2 mb-3">
<img src="/static/uploads/{{c[3]}}" style="height:200px">
<div class="overlay">{{c[1]}}</div>
</div>
</label>
</div>
{% endfor %}
</div>

<h4>Female</h4>
<div class="row">
{% for c in female %}
<div class="col-md-4">
<label>
<input type="radio" name="female" value="{{c[0]}}" required>
<div class="card bg-dark p-2 mb-3">
<img src="/static/uploads/{{c[3]}}" style="height:200px">
<div class="overlay">{{c[1]}}</div>
</div>
</label>
</div>
{% endfor %}
</div>

<button class="btn btn-primary w-100">Submit</button>
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

    c.execute("SELECT value FROM settings WHERE key='present_count'")
    total = int(c.fetchone()[0])

    c.execute("SELECT COUNT(*) FROM students WHERE voted=1 AND allowed=1")
    voted = c.fetchone()[0]

    preview = request.args.get("preview")

    if voted < total and preview != "true":
        return f"<h3>{total - voted} remaining</h3><a href='/result?preview=true'>Preview</a>"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    total_votes = sum([d[4] for d in data]) or 1
    sorted_data = sorted(data, key=lambda x: x[4], reverse=True)

    html = """
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);color:white;}
.card{background:#2c2c3e;border-radius:15px;}
</style>
</head>
<body>
<div class="container mt-5">
<h2 class="text-center">Results</h2>
"""

    for i, d in enumerate(sorted_data):
        percent = (d[4]/total_votes)*100
        html += f"""
<div class="card p-3 mb-2">
<b>#{i+1} {d[1]}</b> - {d[4]} votes ({percent:.1f}%)
<div class="progress mt-2">
<div class="progress-bar bg-warning" style="width:{percent}%"></div>
</div>
</div>
"""

    html += "<script>confetti();</script></div></body></html>"
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

    csv = "Name,Gender,Votes\n"
    for d in data:
        csv += f"{d[0]},{d[1]},{d[2]}\n"

    return app.response_class(csv, mimetype='text/csv',
        headers={"Content-Disposition":"attachment;filename=results.csv"})

# -------- CLOSE --------
@app.route("/close")
def close():
    if "admin" not in session:
        return "Unauthorized"

    conn = sqlite3.connect("voting.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES ('status','closed')")
    conn.commit()
    conn.close()

    return "Voting Closed"

# -------- RUN --------
if __name__ == "__main__":
    app.run()
