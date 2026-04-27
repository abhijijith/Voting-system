from flask import Flask, request, redirect, session, render_template_string, url_for
import sqlite3, os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -------- DATABASE --------
def init_db():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS students(
        roll INTEGER PRIMARY KEY,
        password TEXT,
        voted INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        gender TEXT,
        image TEXT,
        votes INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------- ADMIN --------
@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        conn = sqlite3.connect("voting.db")
        c = conn.cursor()

        # Create students 1–62
        for r in range(1, 63):
            c.execute("INSERT OR IGNORE INTO students VALUES (?, ?, 0)", (r, str(r)))

        # Clear old candidates
        c.execute("DELETE FROM candidates")

        # Add candidates
        for i in range(6):
            name = request.form.get(f"name_{i}")
            gender = request.form.get(f"gender_{i}")
            file = request.files.get(f"photo_{i}")

            if name and gender and file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

                c.execute("INSERT INTO candidates(name,gender,image,votes) VALUES (?,?,?,0)",
                          (name, gender, filename))

        # Start voting
        c.execute("INSERT OR REPLACE INTO settings VALUES ('voting','on')")

        conn.commit()
        conn.close()
        return "<h3>Setup complete! Go to /login</h3>"

    return """
    <h2>Admin Setup</h2>
    <form method="post" enctype="multipart/form-data">
    <h3>Add Candidates</h3>
    """ + "".join([
        f"""
        Name: <input name="name_{i}">
        Gender:
        <select name="gender_{i}">
            <option>Male</option>
            <option>Female</option>
        </select>
        Photo: <input type="file" name="photo_{i}"><br><br>
        """ for i in range(6)
    ]) + """
    <button type="submit">Start Election</button>
    </form>
    """

# -------- LOGIN --------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        try:
            roll = int(request.form["roll"])
            password = request.form["password"]
        except:
            return "Invalid input"

        # Restrict 1–62
        if roll < 1 or roll > 62:
            return "Access denied! Only rolls 1–62 allowed."

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
    <h2>Student Login</h2>
    <form method="post">
    Roll: <input name="roll"><br>
    Password: <input type="password" name="password"><br>
    <button>Login</button>
    </form>
    """

# -------- VOTE --------
@app.route("/vote", methods=["GET","POST"])
def vote():
    if "roll" not in session:
        return redirect("/login")

    roll = int(session["roll"])

    if roll < 1 or roll > 62:
        return "Unauthorized"

    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    # Check voting status
    c.execute("SELECT value FROM settings WHERE key='voting'")
    status = c.fetchone()

    if not status or status[0] != "on":
        return "Voting closed"

    # Check if already voted
    c.execute("SELECT voted FROM students WHERE roll=?", (roll,))
    if c.fetchone()[0] == 1:
        return "You already voted!"

    if request.method == "POST":
        male = request.form.get("male")
        female = request.form.get("female")

        if not male or not female:
            return "Select both candidates!"

        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (male,))
        c.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (female,))
        c.execute("UPDATE students SET voted=1 WHERE roll=?", (roll,))

        conn.commit()
        conn.close()
        return "<h3>Vote submitted successfully!</h3>"

    # Load candidates
    c.execute("SELECT * FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[2]=="Male"]
    female = [d for d in data if d[2]=="Female"]

    return render_template_string("""
    <h2>Vote for Class Representatives</h2>

    <form method="post">

    <h3>Male Representative</h3>
    {% for c in male %}
        <div>
            <img src="/static/uploads/{{c[3]}}" width="100"><br>
            <input type="radio" name="male" value="{{c[0]}}"> {{c[1]}}
        </div>
    {% endfor %}

    <h3>Female Representative</h3>
    {% for c in female %}
        <div>
            <img src="/static/uploads/{{c[3]}}" width="100"><br>
            <input type="radio" name="female" value="{{c[0]}}"> {{c[1]}}
        </div>
    {% endfor %}

    <button type="submit">Submit Vote</button>
    </form>
    """, male=male, female=female)

# -------- RESULT --------
@app.route("/result")
def result():
    conn = sqlite3.connect("voting.db")
    c = conn.cursor()

    # Check remaining voters
    c.execute("SELECT COUNT(*) FROM students WHERE voted=0")
    remaining = c.fetchone()[0]

    if remaining > 0:
        return f"<h3>Voting still in progress</h3><p>{remaining} students yet to vote</p>"

    c.execute("SELECT name, gender, votes FROM candidates")
    data = c.fetchall()
    conn.close()

    male = [d for d in data if d[1]=="Male"]
    female = [d for d in data if d[1]=="Female"]

    male_winner = max(male, key=lambda x: x[2])
    female_winner = max(female, key=lambda x: x[2])

    html = "<h2>Final Results</h2>"

    for d in data:
        html += f"<p>{d[0]} ({d[1]}): {d[2]} votes</p>"

    html += f"<h3>Male Winner: {male_winner[0]}</h3>"
    html += f"<h3>Female Winner: {female_winner[0]}</h3>"

    return html

# -------- RUN --------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
