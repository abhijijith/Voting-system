from flask import Flask, request, redirect, session, render_template_string
import sqlite3, os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"

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

# -------- ADMIN --------
@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        total_students = int(request.form["total_students"])
        absent_rolls = request.form["absent_rolls"]
        num_candidates = int(request.form["num_candidates"])

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()

        c.execute("DELETE FROM students")
        c.execute("DELETE FROM candidates")

        # Create students
        for r in range(1, total_students+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0, 1)", (r, str(r)))

        # Block absent
        absent_list = [int(x.strip()) for x in absent_rolls.split(",") if x.strip().isdigit()]
        for r in absent_list:
            c.execute("UPDATE students SET allowed=0 WHERE roll=?", (r,))

        present_count = total_students - len(absent_list)

        # Add candidates
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
        conn.commit()
        conn.close()

        return "<h3>Setup Done! Go to /login</h3>"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Admin</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);}
.card{background:#2c2c3e;color:white;border-radius:20px;}
</style>
</head>
<body>
<div class="container mt-5">
<div class="card p-4">

<h2 class="text-center">⚙ Election Setup</h2>

<form method="post" enctype="multipart/form-data">

<input class="form-control mb-2" name="total_students" placeholder="Total Students">

<input class="form-control mb-2" name="absent_rolls" placeholder="Absent Rolls (e.g. 2,5,10)">

<input class="form-control mb-3" name="num_candidates" placeholder="Number of Candidates">

{% for i in range(6) %}
<div class="border p-2 mb-2 rounded bg-dark">
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
            error = "Invalid roll or not allowed"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Login</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);display:flex;justify-content:center;align-items:center;height:100vh;}
.card{background:#2c2c3e;color:white;border-radius:20px;}
</style>
</head>
<body>

<div class="card p-4 text-center" style="width:320px;">
<h3>🗳 Student Login</h3>

<p>Roll = Username<br>Password = Same Roll</p>

<form method="post">

<label>Roll Number</label>
<input class="form-control mb-2" name="roll" required>

<label>Password</label>
<input type="password" class="form-control mb-2" name="password" required>

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
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);}
.card{position:relative;}
.card:hover{transform:scale(1.05);transition:0.3s;}
.overlay{
position:absolute;bottom:0;width:100%;background:rgba(0,0,0,0.7);color:white;padding:5px;
}
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
<div class="card bg-dark p-2 mb-3">

<img src="/static/uploads/{{c[3]}}" style="height:200px">

<div class="overlay">{{c[1]}}</div>

<input type="radio" name="male" value="{{c[0]}}">
</div>
</div>
{% endfor %}
</div>

<h4>Female</h4>
<div class="row">
{% for c in female %}
<div class="col-md-4">
<div class="card bg-dark p-2 mb-3">

<img src="/static/uploads/{{c[3]}}" style="height:200px">

<div class="overlay">{{c[1]}}</div>

<input type="radio" name="female" value="{{c[0]}}">
</div>
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

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    male_winner = max(male, key=lambda x: x[4])
    female_winner = max(female, key=lambda x: x[4])

    html = "<html><body style='background:black;color:white;text-align:center'>"

    for d in data:
        html += f"<p>{d[1]} - {d[4]}</p>"

    html += f"<h3>Male Winner: {male_winner[1]}</h3>"
    html += f"<img src='/static/uploads/{male_winner[3]}' width='150'>"

    html += f"<h3>Female Winner: {female_winner[1]}</h3>"
    html += f"<img src='/static/uploads/{female_winner[3]}' width='150'>"

    html += "<script src='https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js'></script><script>confetti();</script>"

    html += "</body></html>"

    return html

if __name__ == "__main__":
    app.run()
