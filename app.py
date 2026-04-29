from flask import Flask, request, redirect, session, render_template_string, send_file
import sqlite3, os

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

    conn.commit()
    conn.close()

init_db()

# -------- ADMIN LOGIN --------
@app.route("/admin-login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")
    return """
    <h3>Admin Login</h3>
    <form method="post">
    <input type="password" name="password">
    <button>Login</button>
    </form>
    """

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

        # create students
        for r in range(1, total+1):
            c.execute("INSERT INTO students VALUES (?, ?, 0, 1)", (r, str(r)))

        # mark absent
        absent_list = [int(x.strip()) for x in absent.split(",") if x.strip().isdigit()]
        for r in absent_list:
            c.execute("UPDATE students SET allowed=0 WHERE roll=?", (r,))

        # upload candidates
        for i in range(num):
            name = request.form.get(f"name_{i}")
            gender = request.form.get(f"gender_{i}")
            file = request.files.get(f"photo_{i}")

            if name and gender and file:
                upload = cloudinary.uploader.upload(file)
                image_url = upload["secure_url"]

                c.execute(
                    "INSERT INTO candidates(name,gender,image,votes) VALUES (?,?,?,0)",
                    (name, gender, image_url)
                )

        conn.commit()
        conn.close()

        return "<h3>Setup done! <a href='/login'>Go to Login</a></h3>"

    return """
    <h2>Admin Setup</h2>
    <form method="post" enctype="multipart/form-data">
    Total Students: <input name="total_students"><br>
    Absent Rolls: <input name="absent_rolls"><br>
    Candidates: <input name="num_candidates"><br><br>

    Name: <input name="name_0"> Gender:
    <select name="gender_0"><option>Male</option><option>Female</option></select>
    Photo: <input type="file" name="photo_0"><br><br>

    Name: <input name="name_1"> Gender:
    <select name="gender_1"><option>Male</option><option>Female</option></select>
    Photo: <input type="file" name="photo_1"><br><br>

    <button>Start</button>
    </form>
    """

# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
    error = None

    if request.method == "POST":
        roll = request.form.get("roll")
        password = request.form.get("password")

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
            error = "Invalid login"

    return f"""
    <h3>Student Login</h3>
    <p>Roll = Password</p>
    <form method="post">
    Roll: <input name="roll"><br>
    Password: <input type="password" name="password"><br>
    <button>Login</button>
    <p>{error or ""}</p>
    </form>
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
        return "<h3>Vote submitted</h3>"

    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    html = "<h2>Vote</h2><form method='post'>"

    for c in male:
        html += f"<input type='radio' name='male' value='{c[0]}'> <img src='{c[3]}' height=100> {c[1]}<br>"

    for c in female:
        html += f"<input type='radio' name='female' value='{c[0]}'> <img src='{c[3]}' height=100> {c[1]}<br>"

    html += "<button>Submit</button></form>"
    return html

# -------- RESULT --------
@app.route("/result")
def result():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()
    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    html = "<h2>Results</h2>"

    for d in data:
        html += f"<p><img src='{d[3]}' height=100> {d[1]} - {d[4]} votes</p>"

    return html

# -------- RUN (IMPORTANT FOR RAILWAY) --------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
