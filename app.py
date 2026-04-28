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

        # create all students
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
        conn.commit()
        conn.close()

        return "<h3>Setup Done! Go to /login</h3>"

    return """
    <h2>Admin Setup</h2>
    <form method="post" enctype="multipart/form-data">
        Total Students: <input name="total_students"><br><br>
        Absent Rolls: <input name="absent_rolls"><br><br>
        Number of Candidates: <input name="num_candidates"><br><br>

        <input name="name_0"> <select name="gender_0"><option>Male</option><option>Female</option></select> <input type="file" name="photo_0"><br>
        <input name="name_1"> <select name="gender_1"><option>Male</option><option>Female</option></select> <input type="file" name="photo_1"><br>
        <input name="name_2"> <select name="gender_2"><option>Male</option><option>Female</option></select> <input type="file" name="photo_2"><br>
        <input name="name_3"> <select name="gender_3"><option>Male</option><option>Female</option></select> <input type="file" name="photo_3"><br>

        <br><button>Start Election</button>
    </form>
    """

# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
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
            return "Not allowed"

    return """
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {background:linear-gradient(135deg,#1f1c2c,#928dab);height:100vh;display:flex;align-items:center;justify-content:center;}
.card{border-radius:20px;background:#2c2c3e;color:white;}
</style>
</head>
<body>
<div class="card p-4">
<h3>🗳 Login</h3>
<form method="post">
<input class="form-control mb-2" name="roll" placeholder="Roll">
<input type="password" class="form-control mb-2" name="password">
<button class="btn btn-primary w-100">Login</button>
</form>
</div>
</body>
</html>
"""

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
.card:hover{transform:scale(1.05);transition:0.3s;}
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
<div class="card bg-dark p-2">
<img src="/static/uploads/{{c[3]}}" style="height:200px">
<input type="radio" name="male" value="{{c[0]}}"> {{c[1]}}
</div>
</div>
{% endfor %}
</div>

<h4>Female</h4>
<div class="row">
{% for c in female %}
<div class="col-md-4">
<div class="card bg-dark p-2">
<img src="/static/uploads/{{c[3]}}" style="height:200px">
<input type="radio" name="female" value="{{c[0]}}"> {{c[1]}}
</div>
</div>
{% endfor %}
</div>

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

    html = """
<!DOCTYPE html>
<html>
<head>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
<style>
body{background:linear-gradient(135deg,#1f1c2c,#928dab);}
.winner{border:3px solid gold;box-shadow:0 0 20px gold;}
</style>
</head>
<body class="text-light text-center">
<div class="container mt-5">
<h2>Results</h2>
"""

    for d in data:
        html += f"<p>{d[1]} - {d[4]}</p>"

    html += f"""
<div class="row mt-5">
<div class="col-md-6">
<div class="card winner bg-dark p-3">
<h4>Male Winner</h4>
<img src="/static/uploads/{male_winner[3]}" height="200">
<h5>{male_winner[1]}</h5>
</div>
</div>

<div class="col-md-6">
<div class="card winner bg-dark p-3">
<h4>Female Winner</h4>
<img src="/static/uploads/{female_winner[3]}" height="200">
<h5>{female_winner[1]}</h5>
</div>
</div>
</div>
"""

    html += "<script>confetti();</script></div></body></html>"

    return html

if __name__ == "__main__":
    app.run()
