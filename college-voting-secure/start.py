#!/usr/bin/env python3
"""
start.py — One-command launcher for the College Voting System.
Run: python3 start.py
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "database", "voting.db")
APP_PATH = os.path.join(BASE_DIR, "backend", "app.py")
INIT_PATH = os.path.join(BASE_DIR, "database", "init_db.py")


def check_deps():
    missing = []
    try:
        import flask
    except ImportError:
        missing.append("Flask")
    try:
        import jwt
    except ImportError:
        missing.append("PyJWT")
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def main():
    check_deps()

    # Create DB if it doesn't exist
    if not os.path.exists(DB_PATH):
        print("Setting up database for the first time...")
        result = subprocess.run([sys.executable, INIT_PATH], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print("Error:", result.stderr)
            sys.exit(1)

    # Start Flask
    os.environ.setdefault("SECRET_KEY", "change-in-production-use-env-var")
    os.chdir(BASE_DIR)
    os.execv(sys.executable, [sys.executable, APP_PATH])


if __name__ == "__main__":
    main()
