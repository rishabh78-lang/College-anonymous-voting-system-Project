"""
backend/auth.py
JWT token creation and verification — only PyJWT used, no extra libraries.
"""

import jwt
import os
import datetime
from functools import wraps
from flask import request, jsonify

# In production: set this as an environment variable
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-use-env-var-32chars")


def make_token(payload: dict, hours: int = 24) -> str:
    """Create a signed JWT that expires in `hours` hours."""
    payload = payload.copy()
    payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(hours=hours)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _get_token_from_header() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def require_student(f):
    """Decorator: protect a route so only authenticated students can access it."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _get_token_from_header()
        if not token:
            return jsonify({"error": "Authentication required."}), 401
        payload = decode_token(token)
        if not payload or payload.get("role") != "student":
            return jsonify({"error": "Invalid or expired session."}), 401
        request.student_id = payload["id"]
        request.student_name = payload["name"]
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Decorator: protect a route so only authenticated admins can access it."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _get_token_from_header()
        if not token:
            return jsonify({"error": "Authentication required."}), 401
        payload = decode_token(token)
        if not payload or payload.get("role") != "admin":
            return jsonify({"error": "Admin access required."}), 403
        request.admin_id = payload["id"]
        return f(*args, **kwargs)
    return wrapper
