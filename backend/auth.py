from flask import Blueprint, request, jsonify
from db import get_db
import hashlib

auth_bp = Blueprint("auth", __name__)

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data["email"]
    password = hash_password(data["password"])

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id, role
        FROM users
        WHERE email=%s AND password_hash=%s
    """, (email, password))

    user = cursor.fetchone()
    db.close()

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "user_id": user["user_id"],
        "role": user["role"]
    })
