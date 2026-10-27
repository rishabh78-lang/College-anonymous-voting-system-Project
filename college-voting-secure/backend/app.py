"""
backend/app.py
Main Flask application. All routes in one file for simplicity and auditability.

Security measures applied:
  - Parameterised SQL queries everywhere (no string formatting in SQL)
  - Werkzeug password hashing (PBKDF2-SHA256)
  - JWT auth with role checks on every protected route
  - Input length limits to prevent oversized payloads
  - No sensitive data in responses (no passwords, no vote-to-student links)
  - CORS restricted to same origin (served from Flask itself)
  - Rate limiting via simple in-memory counter on login endpoints
"""

import os
import sys
import time
import datetime
from collections import defaultdict
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

# Add parent dir to path so we can import backend modules
sys.path.insert(0, os.path.dirname(__file__))
import db
from auth import make_token, require_student, require_admin

# ── APP SETUP ─────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024   # 16 KB max request body

# ── SIMPLE RATE LIMITER (in-memory, resets on restart) ────────────────────────
_login_attempts = defaultdict(list)   # ip → [timestamps]

def _is_rate_limited(ip: str, window_sec=60, max_attempts=10) -> bool:
    now = time.time()
    attempts = [t for t in _login_attempts[ip] if now - t < window_sec]
    _login_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return True
    _login_attempts[ip].append(now)
    return False

# ── HELPER ────────────────────────────────────────────────────────────────────
def _bad(msg, code=400):
    return jsonify({"error": msg}), code

def _ok(data=None, msg=""):
    body = {"ok": True}
    if msg:    body["message"] = msg
    if data is not None: body["data"] = data
    return jsonify(body), 200

# ── SERVE FRONTEND ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    # Only serve files that exist in the frontend dir (no path traversal)
    safe_path = os.path.join(FRONTEND_DIR, filename)
    if not os.path.realpath(safe_path).startswith(os.path.realpath(FRONTEND_DIR)):
        return _bad("Not found", 404)
    if not os.path.isfile(safe_path):
        return _bad("Not found", 404)
    return send_from_directory(FRONTEND_DIR, filename)

# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/student/login", methods=["POST"])
def student_login():
    ip = request.remote_addr
    if _is_rate_limited(ip):
        return _bad("Too many login attempts. Wait a minute.", 429)

    data = request.get_json(silent=True) or {}
    student_id = str(data.get("student_id", "")).strip()[:20]
    password   = str(data.get("password",   ""))[:128]

    if not student_id or not password:
        return _bad("Student ID and password are required.")

    student = db.query_one(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    )
    if not student or not check_password_hash(student["password"], password):
        return _bad("Invalid student ID or password.", 401)

    token = make_token({
        "id":   student["id"],
        "sid":  student["student_id"],
        "name": student["name"],
        "role": "student",
    })
    return _ok({
        "token":     token,
        "name":      student["name"],
        "student_id": student["student_id"],
        "department": student["department"],
        "has_voted": bool(student["has_voted"]),
    })


@app.route("/api/auth/admin/login", methods=["POST"])
def admin_login():
    ip = request.remote_addr
    if _is_rate_limited(ip, max_attempts=5):
        return _bad("Too many login attempts. Wait a minute.", 429)

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()[:50]
    password = str(data.get("password", ""))[:128]

    if not username or not password:
        return _bad("Username and password are required.")

    admin = db.query_one("SELECT * FROM admins WHERE username = ?", (username,))
    if not admin or not check_password_hash(admin["password"], password):
        return _bad("Invalid credentials.", 401)

    token = make_token({"id": admin["id"], "name": admin["name"], "role": "admin"}, hours=8)
    return _ok({"token": token, "name": admin["name"]})


# ══════════════════════════════════════════════════════════════════════════════
# STUDENT ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/election/status", methods=["GET"])
def election_status():
    row = db.query_one("SELECT name, is_active FROM election WHERE id = 1")
    return _ok(row or {"name": "Election", "is_active": 0})


@app.route("/api/nominees", methods=["GET"])
@require_student
def get_nominees():
    rows = db.query_all(
        "SELECT id, name, position, department, bio FROM nominees ORDER BY position, name"
    )
    return _ok(rows)


@app.route("/api/vote", methods=["POST"])
@require_student
def cast_vote():
    # 1. Check election is active
    election = db.query_one("SELECT is_active FROM election WHERE id = 1")
    if not election or not election["is_active"]:
        return _bad("Voting is not currently active.", 403)

    # 2. Check student has not already voted
    student = db.query_one("SELECT has_voted FROM students WHERE id = ?", (request.student_id,))
    if not student:
        return _bad("Student not found.", 404)
    if student["has_voted"]:
        return _bad("You have already voted.", 403)

    # 3. Validate input
    data = request.get_json(silent=True) or {}
    votes = data.get("votes")   # list of {nominee_id, position}
    if not isinstance(votes, list) or len(votes) == 0:
        return _bad("No votes provided.")
    if len(votes) > 10:
        return _bad("Too many vote selections.")

    # 4. Validate each nominee exists
    for v in votes:
        nid  = v.get("nominee_id")
        pos  = str(v.get("position", ""))[:100]
        if not isinstance(nid, int):
            return _bad("Invalid nominee selection.")
        nominee = db.query_one(
            "SELECT id FROM nominees WHERE id = ? AND position = ?", (nid, pos)
        )
        if not nominee:
            return _bad("Invalid nominee or position mismatch.")

    # 5. Record votes — ANONYMOUS (no student_id stored in votes table)
    conn = db.get_conn()
    try:
        with conn:
            for v in votes:
                conn.execute(
                    "INSERT INTO votes (nominee_id, position) VALUES (?, ?)",
                    (v["nominee_id"], str(v["position"])[:100])
                )
                conn.execute(
                    "UPDATE nominees SET vote_count = vote_count + 1 WHERE id = ?",
                    (v["nominee_id"],)
                )
            # Mark student as voted (records participation only, not choice)
            conn.execute(
                "UPDATE students SET has_voted = 1 WHERE id = ?",
                (request.student_id,)
            )
        conn.commit()
    finally:
        conn.close()

    return _ok(msg="Your vote has been cast successfully.")


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    total   = db.query_one("SELECT COUNT(*) AS n FROM students")["n"]
    voted   = db.query_one("SELECT COUNT(*) AS n FROM students WHERE has_voted = 1")["n"]
    nominees = db.query_one("SELECT COUNT(*) AS n FROM nominees")["n"]
    total_votes = db.query_one("SELECT COUNT(*) AS n FROM votes")["n"]
    election = db.query_one("SELECT name, is_active FROM election WHERE id = 1")
    return _ok({
        "total_students": total,
        "voted":          voted,
        "not_voted":      total - voted,
        "turnout_pct":    round(voted / total * 100) if total else 0,
        "total_nominees": nominees,
        "total_votes":    total_votes,
        "election":       election,
    })


@app.route("/api/admin/results", methods=["GET"])
@require_admin
def admin_results():
    rows = db.query_all(
        "SELECT id, name, position, department, vote_count FROM nominees ORDER BY position, vote_count DESC"
    )
    # Group by position
    grouped = {}
    for r in rows:
        pos = r["position"]
        grouped.setdefault(pos, []).append(r)
    return _ok(grouped)


@app.route("/api/admin/election", methods=["PUT"])
@require_admin
def toggle_election():
    data      = request.get_json(silent=True) or {}
    is_active = int(bool(data.get("is_active", False)))
    name      = str(data.get("name", "")).strip()[:200] or None
    if name:
        db.execute("UPDATE election SET is_active = ?, name = ? WHERE id = 1", (is_active, name))
    else:
        db.execute("UPDATE election SET is_active = ? WHERE id = 1", (is_active,))
    status = "started" if is_active else "stopped"
    return _ok(msg=f"Voting {status} successfully.")


@app.route("/api/admin/nominees", methods=["GET"])
@require_admin
def admin_get_nominees():
    rows = db.query_all("SELECT * FROM nominees ORDER BY position, name")
    return _ok(rows)


@app.route("/api/admin/nominees", methods=["POST"])
@require_admin
def admin_add_nominee():
    data = request.get_json(silent=True) or {}
    name       = str(data.get("name",       "")).strip()[:150]
    position   = str(data.get("position",   "")).strip()[:100]
    department = str(data.get("department", "")).strip()[:100]
    bio        = str(data.get("bio",        "")).strip()[:500]

    if not name or not position:
        return _bad("Name and position are required.")

    rid = db.execute(
        "INSERT INTO nominees (name, position, department, bio) VALUES (?, ?, ?, ?)",
        (name, position, department, bio)
    )
    return _ok({"id": rid}, "Nominee added.")


@app.route("/api/admin/nominees/<int:nid>", methods=["DELETE"])
@require_admin
def admin_delete_nominee(nid):
    existing = db.query_one("SELECT id FROM nominees WHERE id = ?", (nid,))
    if not existing:
        return _bad("Nominee not found.", 404)
    db.execute("DELETE FROM votes WHERE nominee_id = ?", (nid,))
    db.execute("DELETE FROM nominees WHERE id = ?", (nid,))
    return _ok(msg="Nominee removed.")


@app.route("/api/admin/students", methods=["GET"])
@require_admin
def admin_get_students():
    rows = db.query_all(
        "SELECT id, student_id, name, department, has_voted FROM students ORDER BY name"
    )
    return _ok(rows)


@app.route("/api/admin/students", methods=["POST"])
@require_admin
def admin_add_student():
    data       = request.get_json(silent=True) or {}
    student_id = str(data.get("student_id", "")).strip()[:20]
    name       = str(data.get("name",       "")).strip()[:150]
    department = str(data.get("department", "")).strip()[:100]
    password   = str(data.get("password",   ""))[:128]

    if not student_id or not name or not password:
        return _bad("Student ID, name, and password are required.")
    if len(password) < 6:
        return _bad("Password must be at least 6 characters.")

    existing = db.query_one("SELECT id FROM students WHERE student_id = ?", (student_id,))
    if existing:
        return _bad("Student ID already exists.", 409)

    pw_hash = generate_password_hash(password)
    rid = db.execute(
        "INSERT INTO students (student_id, name, department, password) VALUES (?, ?, ?, ?)",
        (student_id, name, department, pw_hash)
    )
    return _ok({"id": rid}, "Student added.")


@app.route("/api/admin/students/<int:sid>", methods=["DELETE"])
@require_admin
def admin_delete_student(sid):
    existing = db.query_one("SELECT id FROM students WHERE id = ?", (sid,))
    if not existing:
        return _bad("Student not found.", 404)
    db.execute("DELETE FROM students WHERE id = ?", (sid,))
    return _ok(msg="Student removed.")


@app.route("/api/admin/reset-votes", methods=["POST"])
@require_admin
def admin_reset_votes():
    db.execute("DELETE FROM votes")
    db.execute("UPDATE nominees SET vote_count = 0")
    db.execute("UPDATE students SET has_voted = 0")
    return _ok(msg="All votes reset.")


# ── SECURITY HEADERS ──────────────────────────────────────────────────────────
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"]   = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:;"
    )
    return response


# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    db_path = os.path.join(BASE_DIR, "database", "voting.db")
    if not os.path.exists(db_path):
        print("ERROR: Database not found. Run: python3 database/init_db.py")
        raise SystemExit(1)

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    print(f"\n🎓 College Voting System")
    print(f"🚀 Running at http://localhost:{port}")
    print(f"   Open your browser and go to http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=debug)
