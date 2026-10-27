"""
database/init_db.py
Creates the SQLite database with all tables and seed data.
Run this ONCE before starting the server: python3 database/init_db.py
"""

import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "voting.db")


def init_database():
    """Create all tables and insert seed data."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # enforce FK constraints
    conn.execute("PRAGMA journal_mode = WAL")  # safer concurrent writes
    cur = conn.cursor()

    # ── ADMINS ────────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL,
            name     TEXT    NOT NULL
        )
    """)

    # ── STUDENTS ──────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT    NOT NULL UNIQUE,
            name       TEXT    NOT NULL,
            department TEXT,
            password   TEXT    NOT NULL,
            has_voted  INTEGER NOT NULL DEFAULT 0   -- 0=false, 1=true
        )
    """)

    # ── ELECTION STATUS ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS election (
            id        INTEGER PRIMARY KEY CHECK (id = 1),  -- only one row
            name      TEXT    NOT NULL DEFAULT 'Student Council Election',
            is_active INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ── NOMINEES ──────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nominees (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            position   TEXT    NOT NULL,
            department TEXT,
            bio        TEXT,
            vote_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ── VOTES (Anonymous) ─────────────────────────────────────────────────────
    # Stores ONLY nominee_id — NO student_id here (anonymity guarantee)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nominee_id INTEGER NOT NULL REFERENCES nominees(id),
            position   TEXT    NOT NULL,
            voted_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── SEED: Default Admin ───────────────────────────────────────────────────
    admin_pw = generate_password_hash("admin123")
    cur.execute("""
        INSERT OR IGNORE INTO admins (username, password, name)
        VALUES (?, ?, ?)
    """, ("admin", admin_pw, "System Administrator"))

    # ── SEED: Election Row ────────────────────────────────────────────────────
    cur.execute("""
        INSERT OR IGNORE INTO election (id, name, is_active)
        VALUES (1, 'Student Council Election 2024', 0)
    """)

    # ── SEED: Sample Students (password = student123) ─────────────────────────
    student_pw = generate_password_hash("student123")
    students = [
        ("CS2024001", "Amit Kumar",   "Computer Science"),
        ("CS2024002", "Divya Raj",    "Computer Science"),
        ("EC2024001", "Rohit Verma",  "Electronics"),
        ("ME2024001", "Sita Devi",    "Mechanical"),
        ("IT2024001", "Mohan Lal",    "Information Technology"),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO students (student_id, name, department, password)
        VALUES (?, ?, ?, ?)
    """, [(s[0], s[1], s[2], student_pw) for s in students])

    # ── SEED: Sample Nominees ─────────────────────────────────────────────────
    nominees = [
        ("Arjun Sharma",  "President",      "Computer Science",  "Passionate student leader with 2 years of council experience."),
        ("Priya Nair",    "President",      "Electronics",       "Dedicated to student welfare and transparent communication."),
        ("Rahul Mehta",   "Vice President", "Mechanical",        "Organized multiple college events and technical fests."),
        ("Sneha Patel",   "Vice President", "Information Tech",  "Student mentor focused on mental health and inclusivity."),
        ("Karthik Rajan", "Secretary",      "Civil Engineering", "Strong communicator with excellent organizational skills."),
        ("Ananya Singh",  "Treasurer",      "Commerce",          "Finance club president with experience managing budgets."),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO nominees (name, position, department, bio)
        VALUES (?, ?, ?, ?)
    """, nominees)

    conn.commit()
    conn.close()
    print(f"✅ Database created at: {DB_PATH}")
    print("   Admin login  → username: admin     | password: admin123")
    print("   Student login→ ID: CS2024001       | password: student123")


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        ans = input(f"Database already exists at {DB_PATH}. Recreate? (y/N): ")
        if ans.lower() != "y":
            print("Skipped.")
            sys.exit(0)
        os.remove(DB_PATH)
    init_database()
