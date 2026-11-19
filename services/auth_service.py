"""User registration and login stored in Firebase Realtime Database."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Union

from werkzeug.security import check_password_hash, generate_password_hash

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_to_key(email: str) -> str:
    """Firebase-safe key for email lookup index."""
    key = email.strip().lower()
    for char in ".#$[]/":
        key = key.replace(char, "_")
    return key.replace("@", "_at_")


def register_user(db, name: str, email: str, password: str) -> tuple[bool, str]:
    name = name.strip()
    email = email.strip().lower()

    if not name:
        return False, "Please enter your name."
    if not EMAIL_RE.match(email):
        return False, "Please enter a valid email address."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    email_key = email_to_key(email)
    index_ref = db.reference(f"users_by_email/{email_key}")
    if index_ref.get():
        return False, "An account with this email already exists. Try logging in."

    user_ref = db.reference("users").push({
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    uid = user_ref.key
    index_ref.set(uid)
    return True, uid


def authenticate_user(db, email: str, password: str) -> tuple[bool, Union[str, dict]]:
    email = email.strip().lower()
    if not email or not password:
        return False, "Please enter your email and password."

    email_key = email_to_key(email)
    uid = db.reference(f"users_by_email/{email_key}").get()
    if not uid:
        return False, "Invalid email or password."

    user = db.reference(f"users/{uid}").get()
    if not user:
        return False, "Invalid email or password."

    stored_hash = user.get("password_hash", "")
    if not check_password_hash(stored_hash, password):
        return False, "Invalid email or password."

    return True, {
        "uid": uid,
        "name": user.get("name", ""),
        "email": user.get("email", email),
    }
