from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "attendance_secret_key"


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll TEXT NOT NULL,
            class_name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            status TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template("index.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = "admin"
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    total_students = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    today = date.today().isoformat()

    today_present = c.execute(
        "SELECT COUNT(*) FROM attendance WHERE date=? AND status='Present'",
        (today,)
    ).fetchone()[0]

    percentage = (today_present / total_students * 100) if total_students > 0 else 0

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        today_present=today_present,
        percentage=round(percentage, 2)
    )


# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]
        class_name = request.form["class"]
        email = request.form["email"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            INSERT INTO students (name, roll, class_name, email)
            VALUES (?, ?, ?, ?)
        """, (name, roll, class_name, email))

        conn.commit()
        conn.close()

        flash("Student added successfully! 🎉", "success")
        return redirect(url_for("view_students"))

    return render_template("add_student.html")


# ---------------- VIEW STUDENTS (WITH SEARCH + PERCENTAGE) ----------------
@app.route("/view_students")
def view_students():
    if "user" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if search:
        students_data = c.execute("""
            SELECT * FROM students
            WHERE name LIKE ? OR roll LIKE ? OR class_name LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        students_data = c.execute("SELECT * FROM students").fetchall()

    students = []

    for student in students_data:
        student_id = student[0]

        total_classes = c.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=?",
            (student_id,)
        ).fetchone()[0]

        present_count = c.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'",
            (student_id,)
        ).fetchone()[0]

        percentage = (present_count / total_classes * 100) if total_classes > 0 else 0

        students.append((
            student[0],
            student[1],
            student[2],
            student[3],
            student[4],
            round(percentage, 2)
        ))

    conn.close()

    return render_template("view_students.html", students=students, search=search)

# ---------------- EDIT STUDENT ----------------
@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]
        class_name = request.form["class"]
        email = request.form["email"]

        c.execute("""
            UPDATE students
            SET name=?, roll=?, class_name=?, email=?
            WHERE id=?
        """, (name, roll, class_name, email, id))

        conn.commit()
        conn.close()

        flash("Student updated successfully ✏️", "info")
        return redirect(url_for("view_students"))

    student = c.execute(
        "SELECT * FROM students WHERE id=?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template("edit_student.html", student=student)


# ---------------- DELETE STUDENT ----------------
@app.route("/delete_student/<int:id>")
def delete_student(id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()

    flash("Student deleted successfully ❌", "danger")
    return redirect(url_for("view_students"))


# ---------------- MARK ATTENDANCE ----------------
@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    students = c.execute("SELECT * FROM students").fetchall()

    if request.method == "POST":
        today = date.today().isoformat()

        c.execute("DELETE FROM attendance WHERE date=?", (today,))

        for student in students:
            student_id = student[0]
            status = "Present" if request.form.get(str(student_id)) else "Absent"

            c.execute(
                "INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)",
                (student_id, today, status)
            )

        conn.commit()
        conn.close()

        flash("Attendance marked successfully ✔️", "success")
        return redirect(url_for("view_attendance"))

    conn.close()
    return render_template("mark_attendance.html", students=students)


# ---------------- VIEW ATTENDANCE ----------------
@app.route("/view_attendance", methods=["GET"])
def view_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    selected_date = request.args.get("date")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # ---- Date Filter Records ----
    if selected_date:
        records = c.execute("""
            SELECT students.name, attendance.date, attendance.status
            FROM attendance
            JOIN students ON attendance.student_id = students.id
            WHERE attendance.date = ?
            ORDER BY students.name
        """, (selected_date,)).fetchall()
    else:
        records = []

    # ---- Attendance % For Graph ----
    students = c.execute("SELECT id, name FROM students").fetchall()

    chart_labels = []
    chart_data = []

    for student in students:
        student_id = student[0]
        name = student[1]

        total = c.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=?",
            (student_id,)
        ).fetchone()[0]

        present = c.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'",
            (student_id,)
        ).fetchone()[0]

        percentage = (present / total * 100) if total > 0 else 0

        chart_labels.append(name)
        chart_data.append(round(percentage, 2))

    conn.close()

    return render_template(
        "view_attendance.html",
        records=records,
        selected_date=selected_date,
        chart_labels=chart_labels,
        chart_data=chart_data
    )


if __name__ == "__main__":
    app.run(debug=True)
