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

<h2 class="text-center">⚙ Setup</h2>

<form method="post" enctype="multipart/form-data">
<input class="form-control mb-2" name="total_students" placeholder="Total Students">
<input class="form-control mb-2" name="absent_rolls" placeholder="Absent Rolls">
<input class="form-control mb-3" name="num_candidates" placeholder="Candidates">

{% for i in range(6) %}
<div class="bg-dark p-2 mb-2 rounded">
<input class="form-control mb-1" name="name_{{i}}" placeholder="Name">
<select class="form-control mb-1" name="gender_{{i}}">
<option>Male</option><option>Female</option>
</select>
<input type="file" class="form-control" name="photo_{{i}}">
</div>
{% endfor %}

<button class="btn btn-primary w-100">Start</button>
</form>

<a href="/export" class="btn btn-success w-100 mt-2">📄 Export PDF</a>
<a href="/close" class="btn btn-danger w-100 mt-2">Close Voting</a>

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

        # Basic validation
        if not roll or not password:
            error = "Please enter both roll number and password"
        else:
            conn = sqlite3.connect("voting.db")
            c = conn.cursor()

            c.execute(
                "SELECT * FROM students WHERE roll=? AND password=? AND allowed=1",
                (roll, password)
            )
            user = c.fetchone()
            conn.close()

            if user:
                session["roll"] = roll
                return redirect("/vote")
            else:
                error = "Invalid roll number or not allowed"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Login</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

<style>
body {
    background: linear-gradient(135deg,#1f1c2c,#928dab);
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
}
.card {
    background: #2c2c3e;
    color: white;
    border-radius: 20px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
}
</style>
</head>

<body>

<div class="card p-4 text-center" style="width:320px;">

<h3>🗳 Student Login</h3>

<p class="small text-light mb-3">
👉 Roll number = Password
</p>

<form method="post">

<label class="text-start w-100">Roll Number</label>
<input class="form-control mb-2" name="roll" placeholder="Enter roll number" required>

<label class="text-start w-100">Password</label>
<input type="password" class="form-control mb-3" name="password" placeholder="Enter password" required>

{% if error %}
<p class="text-danger">{{error}}</p>
{% endif %}

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

    roll=session["roll"]

    conn=sqlite3.connect("voting.db")
    c=conn.cursor()

    c.execute("SELECT voted FROM students WHERE roll=?", (roll,))
    if c.fetchone()[0]==1:
        return "Already voted"

    if request.method=="POST":
        male=request.form.get("male")
        female=request.form.get("female")

        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (male,))
        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (female,))
        c.execute("UPDATE students SET voted=1 WHERE roll=?", (roll,))
        conn.commit()
        conn.close()
        return "Vote Submitted"

    c.execute("SELECT * FROM candidates")
    data=c.fetchall()
    conn.close()

    male=[d for d in data if d[2]=="Male"]
    female=[d for d in data if d[2]=="Female"]

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);}
.card{cursor:pointer;transition:0.3s;}
.card:hover{transform:scale(1.05);}
input{display:none;}
input:checked + .card{border:3px solid gold;}
.overlay{position:absolute;bottom:0;width:100%;background:rgba(0,0,0,0.7);color:white;}
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
<input type="radio" name="male" value="{{c[0]}}">
<div class="card bg-dark position-relative">
<img src="/static/uploads/{{c[3]}}" style="height:200px;width:100%">
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
<input type="radio" name="female" value="{{c[0]}}">
<div class="card bg-dark position-relative">
<img src="/static/uploads/{{c[3]}}" style="height:200px;width:100%">
<div class="overlay">{{c[1]}}</div>
</div>
</label>
</div>
{% endfor %}
</div>

<button class="btn btn-primary w-100 mt-3">Submit</button>

</form>
</div>
</body>
</html>
""",male=male,female=female)

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

    html = """
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:#121212;color:white;}
.card{background:white;color:black;border-radius:12px;}
.progress{height:20px;}
.winner{
    border:3px solid gold;
    box-shadow:0 0 20px gold;
}
</style>
</head>

<body>
<div class="container mt-5">

<h2 class="text-center mb-4">📊 Election Results</h2>
"""

    for d in sorted_data:
        percent = (d[4]/total_votes)*100

        html += f"""
<div class="card p-3 mb-3">
<b>{d[1]} ({d[2]})</b><br>
Votes: {d[4]} ({percent:.1f}%)

<div class="progress mt-2">
<div class="progress-bar bg-success" style="width:{percent}%"></div>
</div>
</div>
"""

    html += f"""
<div class="row mt-5 text-center">

<div class="col-md-6">
<div class="card winner p-3">
<h4>🏆 Male Winner</h4>
<img src="/static/uploads/{male_winner[3]}" height="200">
<h5>{male_winner[1]}</h5>
</div>
</div>

<div class="col-md-6">
<div class="card winner p-3">
<h4>🏆 Female Winner</h4>
<img src="/static/uploads/{female_winner[3]}" height="200">
<h5>{female_winner[1]}</h5>
</div>
</div>

</div>
"""

    html += "</div></body></html>"
    return html

# -------- CLOSE --------
@app.route("/close")
def close():
    return "Voting Closed"

if __name__=="__main__":
    app.run()
