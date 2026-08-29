"""
Minimal auth: salted PBKDF2 password hashing + username/password lookup.
Prototype-level only — see the Responsible AI / privacy note in the app
and README for what real deployment would need.
"""
import hashlib
import os
import sqlite3


def hash_password(password: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()
    return check == digest_hex


def authenticate(conn: sqlite3.Connection, username: str, password: str):
    """Returns the user row (as a dict) on success, or None."""
    cur = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}
