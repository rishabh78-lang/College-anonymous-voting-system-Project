"""
backend/db.py
Simple SQLite connection helper — no ORM, no extra deps.
Uses parameterised queries everywhere (SQL injection safe).
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "voting.db")


def get_conn():
    """Return a new database connection with row factory and FK support."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows accessible as dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query_one(sql, params=()):
    """Run a SELECT and return the first row as a dict, or None."""
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query_all(sql, params=()):
    """Run a SELECT and return all rows as a list of dicts."""
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(sql, params=()):
    """Run an INSERT / UPDATE / DELETE and return lastrowid."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def execute_many(sql, params_list):
    """Run executemany for bulk inserts."""
    with get_conn() as conn:
        conn.executemany(sql, params_list)
        conn.commit()
