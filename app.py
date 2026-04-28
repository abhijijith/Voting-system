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
        voted INTEGER DEFAULT 0
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
        total_voters = int(request.form["total_voters"])
        num_candidates = int(request.form["num_candidates"])

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()

        c.execute("DELETE FROM students")
        c.execute("DELETE FROM candidates")

        # Create voters
        for r in range(1, total_voters+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0)", (r, str(r)))

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

        c.execute("INSERT OR REPLACE INTO settings VALUES ('total_voters',?)", (str(total_voters),))
        conn.commit()
        conn.close()

        return "<h3>Setup Done! Go to /login</h3>"

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Admin</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-dark text-light">

<div class="container mt-5">
<h2 class="text-center">⚙ Election Setup</h2>

<form method="post" enctype="multipart/form-data" class="card p-4 bg-secondary">

<input class="form-control mb-2" name="total_voters" placeholder="Total Voters" required>
<input class="form-control mb-2" name="num_candidates" placeholder="Number of Candidates" required>

{% for i in range(6) %}
<div class="border p-2 mb-2 bg-dark rounded">
<input class="form-control mb-2" name="name_{{i}}" placeholder="Candidate Name">
<select class="form-control mb-2" name="gender_{{i}}">
<option>Male</option>
<option>Female</option>
</select>
<input type="file" class="form-control" name="photo_{{i}}">
</div>
{% endfor %}

<button class="btn btn-warning w-100">Start Election</button>
</form>
</div>

</body>
</html>
""")

# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        roll = request.form["roll"]
        password = request.form["password"]

        conn = sqlite3.connect("voting.db")
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE roll=? AND password=?", (roll,password))
        user = c.fetchone()
        conn.close()

        if user:
            session["roll"] = roll
            return redirect("/vote")
        else:
            return "Invalid login"

    return """
<!DOCTYPE html>
<html>
<head>
<title>Login</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-dark d-flex justify-content-center align-items-center vh-100">

<div class="card p-4 bg-secondary text-light" style="width:300px;">
<h3 class="text-center">🔐 Login</h3>

<form method="post">
<input class="form-control mb-2" name="roll" placeholder="Roll">
<input type="password" class="form-control mb-2" name="password" placeholder="Password">
<button class="btn btn-success w-100">Login</button>
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
        return "You already voted!"

    if request.method == "POST":
        male = request.form.get("male")
        female = request.form.get("female")

        if not male or not female:
            return "Select both!"

        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (male,))
        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (female,))
        c.execute("UPDATE students SET voted=1 WHERE roll=?", (roll,))

        conn.commit()
        conn.close()
        return "<h3>Vote submitted!</h3>"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Vote</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>

<body class="bg-dark text-light">
<div class="container mt-4">

<h2 class="text-center">🗳 Vote</h2>

<form method="post">

<h4>👨 Male</h4>
<div class="row">
{% for c in male %}
<div class="col-md-4">
<div class="card bg-secondary mb-3 text-center">
<img src="/static/uploads/{{c[3]}}" class="card-img-top" style="height:200px;object-fit:cover;">
<div class="card-body">
<input type="radio" name="male" value="{{c[0]}}"> {{c[1]}}
</div>
</div>
</div>
{% endfor %}
</div>

<h4>👩 Female</h4>
<div class="row">
{% for c in female %}
<div class="col-md-4">
<div class="card bg-secondary mb-3 text-center">
<img src="/static/uploads/{{c[3]}}" class="card-img-top" style="height:200px;object-fit:cover;">
<div class="card-body">
<input type="radio" name="female" value="{{c[0]}}"> {{c[1]}}
</div>
</div>
</div>
{% endfor %}
</div>

<button class="btn btn-warning w-100">Submit Vote</button>

</form>
</div>
</body>
</html>
""", male=male, female=female)

# -------- RESULT --------
html += f"""
<div class="mt-5">
    <h3>🏆 Male Winner</h3>
    <img src="/static/uploads/{male_winner[3]}" width="150"><br>
    <strong>{male_winner[0]}</strong>
</div>

<div class="mt-4">
    <h3>🏆 Female Winner</h3>
    <img src="/static/uploads/{female_winner[3]}" width="150"><br>
    <strong>{female_winner[0]}</strong>
</div>

</div>

<script>
function launchConfetti() {{
    var duration = 3 * 1000;
    var end = Date.now() + duration;

    (function frame() {{
        confetti({{
            particleCount: 5,
            angle: 60,
            spread: 55,
            origin: {{ x: 0 }}
        }});
        confetti({{
            particleCount: 5,
            angle: 120,
            spread: 55,
            origin: {{ x: 1 }}
        }});

        if (Date.now() < end) {{
            requestAnimationFrame(frame);
        }}
    }})();
}}

launchConfetti();
</script>

</body>
</html>
"""

# -------- RUN --------
import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
