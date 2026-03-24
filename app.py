import csv
import io
import json
import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Flask, Response, g, jsonify, render_template_string, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ["DATABASE_URL"]

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    id           SERIAL PRIMARY KEY,
                    student_name TEXT   NOT NULL,
                    exam_id      TEXT   NOT NULL,
                    answers      TEXT   NOT NULL,
                    score        REAL   NOT NULL,
                    submitted_at TEXT   NOT NULL
                )
                """
            )
        db.commit()


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f5f7fa; color: #333; padding: 2rem; }
    h1 { margin-bottom: 1.5rem; font-size: 1.6rem; }
    .meta { margin-bottom: 1rem; color: #666; font-size: 0.9rem; }
    table { width: 100%; border-collapse: collapse; background: #fff;
            border-radius: 8px; overflow: hidden;
            box-shadow: 0 1px 4px rgba(0,0,0,.12); }
    thead { background: #4f46e5; color: #fff; }
    th, td { padding: .75rem 1rem; text-align: left; font-size: .9rem; }
    tbody tr:nth-child(even) { background: #f0f1ff; }
    tbody tr:hover { background: #e5e7ff; }
    .score { font-weight: 600; }
    .answers { max-width: 320px; word-break: break-word;
               font-size: .8rem; color: #555; }
    a { color: #4f46e5; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .empty { padding: 2rem; text-align: center; color: #888; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p class="meta">
    {{ rows|length }} result(s)
    {% if exam_id %}
      for exam <strong>{{ exam_id }}</strong> &mdash;
      <a href="/results">View all exams</a>
    {% endif %}
    <a href="/results/export{% if exam_id %}?exam_id={{ exam_id }}{% endif %}"
       style="margin-left:1rem; background:#4f46e5; color:#fff; padding:.35rem .8rem;
              border-radius:5px; font-size:.85rem;">
      Download CSV
    </a>
  </p>
  {% if rows %}
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Student</th>
        <th>Exam</th>
        <th>Score</th>
        <th>Answers</th>
        <th>Submitted</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.id }}</td>
        <td>{{ row.student_name }}</td>
        <td><a href="/results/{{ row.exam_id }}">{{ row.exam_id }}</a></td>
        <td class="score">{{ row.score }}</td>
        <td class="answers">{{ row.answers }}</td>
        <td>{{ row.submitted_at }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="empty">No results found.</div>
  {% endif %}
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/results")
def submit_result():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    student_name = data.get("student_name", "").strip()
    exam_id = data.get("exam_id", "").strip()
    answers = data.get("answers")
    score = data.get("score")

    if not student_name:
        return jsonify({"error": "student_name is required"}), 400
    if not exam_id:
        return jsonify({"error": "exam_id is required"}), 400
    if answers is None:
        return jsonify({"error": "answers is required"}), 400
    if score is None:
        return jsonify({"error": "score is required"}), 400

    try:
        score = float(score)
    except (TypeError, ValueError):
        return jsonify({"error": "score must be a number"}), 400

    answers_json = json.dumps(answers)
    submitted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO results (student_name, exam_id, answers, score, submitted_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (student_name, exam_id, answers_json, score, submitted_at),
        )
        new_id = cur.fetchone()["id"]
    db.commit()

    return jsonify({"id": new_id, "message": "Result saved"}), 201


@app.get("/results")
def all_results():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM results ORDER BY submitted_at DESC")
        rows = cur.fetchall()
    return render_template_string(
        RESULTS_TEMPLATE,
        title="All Quiz Results",
        rows=rows,
        exam_id=None,
    )


@app.get("/results/export")
def export_csv():
    exam_id = request.args.get("exam_id")
    db = get_db()
    with db.cursor() as cur:
        if exam_id:
            cur.execute(
                "SELECT * FROM results WHERE exam_id = %s ORDER BY submitted_at DESC",
                (exam_id,),
            )
            filename = f"results_{exam_id}.csv"
        else:
            cur.execute("SELECT * FROM results ORDER BY submitted_at DESC")
            filename = "results_all.csv"
        rows = cur.fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "student_name", "exam_id", "answers", "score", "submitted_at"])
    for row in rows:
        writer.writerow([row["id"], row["student_name"], row["exam_id"],
                         row["answers"], row["score"], row["submitted_at"]])

    return Response(
        "\ufeff" + buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/results/<exam_id>")
def results_by_exam(exam_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM results WHERE exam_id = %s ORDER BY submitted_at DESC",
            (exam_id,),
        )
        rows = cur.fetchall()
    return render_template_string(
        RESULTS_TEMPLATE,
        title=f"Results — Exam {exam_id}",
        rows=rows,
        exam_id=exam_id,
    )


EXAMS_DIR = os.path.join(os.path.dirname(__file__), "exams")

@app.get("/exam/<exam_id>")
def serve_exam(exam_id):
    return send_from_directory(EXAMS_DIR, f"{exam_id}.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)
