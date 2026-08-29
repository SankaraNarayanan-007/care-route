"""
SQLite setup + all CRUD helpers. Kept deliberately flat (no ORM) so the
whole data layer can be read top-to-bottom in a couple of minutes.
"""
import datetime
import json
import os
import sqlite3

from src.auth import hash_password

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "care_route.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('patient','doctor','staff'))
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    dob TEXT,
    contact TEXT
);

CREATE TABLE IF NOT EXISTS appointment_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    raw_text TEXT NOT NULL,
    status TEXT NOT NULL,               -- PENDING | CLARIFICATION_REQUESTED | APPROVED | ESCALATED
    created_at TEXT NOT NULL,
    ai_summary TEXT,
    ai_analysis_json TEXT,
    suggested_queue TEXT,
    confidence TEXT,
    policy_rule TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER REFERENCES appointment_requests(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    date TEXT,
    time TEXT,
    department TEXT,
    status TEXT NOT NULL                -- CONFIRMED | COMPLETED
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    message TEXT NOT NULL,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES appointment_requests(id),
    ai_recommendation TEXT,
    human_decision TEXT,
    modification_reason TEXT,
    decided_by TEXT,
    created_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _seed_if_empty(conn)
    return conn


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _seed_if_empty(conn: sqlite3.Connection):
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("patient01", hash_password("demo123"), "patient"),
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("doctor01", hash_password("demo123"), "doctor"),
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("staff01", hash_password("demo123"), "staff"),
    )
    conn.commit()

    patient_user = conn.execute(
        "SELECT id FROM users WHERE username = 'patient01'"
    ).fetchone()
    conn.execute(
        "INSERT INTO patients (user_id, name, dob, contact) VALUES (?, ?, ?, ?)",
        (patient_user["id"], "Synthetic Patient (Demo)", "1990-04-12", "demo@example.com"),
    )
    conn.commit()
    patient_id = conn.execute("SELECT id FROM patients").fetchone()["id"]

    # synthetic completed appointment history, so the doctor review screen
    # has something real to show as "relevant history"
    conn.execute(
        "INSERT INTO appointments (request_id, patient_id, date, time, department, status) "
        "VALUES (NULL, ?, ?, ?, ?, 'COMPLETED')",
        (patient_id, "2026-07-15", "10:00 AM", "General Consultation"),
    )
    conn.execute(
        "INSERT INTO appointments (request_id, patient_id, date, time, department, status) "
        "VALUES (NULL, ?, ?, ?, ?, 'COMPLETED')",
        (patient_id, "2026-08-02", "02:30 PM", "Follow-up"),
    )
    conn.execute(
        "INSERT INTO appointment_requests (patient_id, raw_text, status, created_at, ai_summary, "
        "ai_analysis_json, suggested_queue, confidence, policy_rule) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            patient_id,
            "Follow-up on last visit's blood pressure medication.",
            "APPROVED",
            "2026-08-02T09:00:00",
            "Routine medication follow-up.",
            json.dumps({}),
            "FOLLOW_UP",
            "high",
            "F-02",
        ),
    )
    conn.commit()


# ---------- patients ----------

def get_patient_by_user_id(conn, user_id: int):
    return conn.execute("SELECT * FROM patients WHERE user_id = ?", (user_id,)).fetchone()


def get_patient(conn, patient_id: int):
    return conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()


# ---------- appointment_requests ----------

def create_request(conn, patient_id, raw_text, status, ai_summary=None, ai_analysis: dict = None,
                    suggested_queue=None, confidence=None, policy_rule=None) -> int:
    cur = conn.execute(
        "INSERT INTO appointment_requests "
        "(patient_id, raw_text, status, created_at, ai_summary, ai_analysis_json, "
        "suggested_queue, confidence, policy_rule) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            patient_id, raw_text, status, _now(), ai_summary,
            json.dumps(ai_analysis) if ai_analysis is not None else None,
            suggested_queue, confidence, policy_rule,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_request_status(conn, request_id, status):
    conn.execute("UPDATE appointment_requests SET status = ? WHERE id = ?", (status, request_id))
    conn.commit()


def update_request_routing(conn, request_id, suggested_queue, policy_rule, modification_reason=None):
    conn.execute(
        "UPDATE appointment_requests SET suggested_queue = ?, policy_rule = ? WHERE id = ?",
        (suggested_queue, policy_rule, request_id),
    )
    conn.commit()


def update_request_full(conn, request_id, raw_text, status, ai_summary, ai_analysis: dict,
                         suggested_queue, confidence, policy_rule):
    """Used when a patient resubmits after a clarification request — re-analyzes
    and overwrites the same request row rather than creating a duplicate."""
    conn.execute(
        "UPDATE appointment_requests SET raw_text=?, status=?, ai_summary=?, "
        "ai_analysis_json=?, suggested_queue=?, confidence=?, policy_rule=? WHERE id=?",
        (raw_text, status, ai_summary, json.dumps(ai_analysis), suggested_queue,
         confidence, policy_rule, request_id),
    )
    conn.commit()


def get_request(conn, request_id):
    return conn.execute("SELECT * FROM appointment_requests WHERE id = ?", (request_id,)).fetchone()


def get_requests_for_patient(conn, patient_id):
    return conn.execute(
        "SELECT * FROM appointment_requests WHERE patient_id = ? ORDER BY created_at DESC",
        (patient_id,),
    ).fetchall()


def get_pending_requests(conn):
    return conn.execute(
        "SELECT * FROM appointment_requests WHERE status IN ('PENDING') ORDER BY created_at ASC"
    ).fetchall()


def get_requests_by_status(conn, statuses):
    placeholders = ",".join("?" for _ in statuses)
    return conn.execute(
        f"SELECT * FROM appointment_requests WHERE status IN ({placeholders}) ORDER BY created_at DESC",
        tuple(statuses),
    ).fetchall()


def count_requests_by_status(conn, status):
    return conn.execute(
        "SELECT COUNT(*) FROM appointment_requests WHERE status = ?", (status,)
    ).fetchone()[0]


def count_approved_today(conn):
    today = datetime.date.today().isoformat()
    return conn.execute(
        "SELECT COUNT(*) FROM appointment_requests WHERE status = 'APPROVED' AND created_at LIKE ?",
        (f"{today}%",),
    ).fetchone()[0]


# ---------- appointments ----------

def create_appointment(conn, request_id, patient_id, date, time, department) -> int:
    cur = conn.execute(
        "INSERT INTO appointments (request_id, patient_id, date, time, department, status) "
        "VALUES (?,?,?,?,?, 'CONFIRMED')",
        (request_id, patient_id, date, time, department),
    )
    conn.commit()
    return cur.lastrowid


def get_upcoming_appointment(conn, patient_id):
    return conn.execute(
        "SELECT * FROM appointments WHERE patient_id = ? AND status = 'CONFIRMED' "
        "ORDER BY date ASC LIMIT 1",
        (patient_id,),
    ).fetchone()


def get_appointment_history(conn, patient_id):
    return conn.execute(
        "SELECT * FROM appointments WHERE patient_id = ? AND status = 'COMPLETED' ORDER BY date DESC",
        (patient_id,),
    ).fetchall()


def get_recent_history_for_review(conn, patient_id, limit=3):
    """Small, relevant slice of history shown to the doctor during review."""
    return conn.execute(
        "SELECT * FROM appointments WHERE patient_id = ? ORDER BY date DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()


# ---------- notifications ----------

def create_notification(conn, patient_id, message, ntype) -> int:
    cur = conn.execute(
        "INSERT INTO notifications (patient_id, message, type, created_at, read) "
        "VALUES (?,?,?,?,0)",
        (patient_id, message, ntype, _now()),
    )
    conn.commit()
    return cur.lastrowid


def get_notifications(conn, patient_id):
    return conn.execute(
        "SELECT * FROM notifications WHERE patient_id = ? ORDER BY created_at DESC",
        (patient_id,),
    ).fetchall()


def mark_notification_read(conn, notification_id):
    conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
    conn.commit()


def unread_count(conn, patient_id):
    return conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE patient_id = ? AND read = 0", (patient_id,)
    ).fetchone()[0]


# ---------- decision_log ----------

def log_decision(conn, request_id, ai_recommendation, human_decision, decided_by,
                  modification_reason=None):
    conn.execute(
        "INSERT INTO decision_log (request_id, ai_recommendation, human_decision, "
        "modification_reason, decided_by, created_at) VALUES (?,?,?,?,?,?)",
        (request_id, ai_recommendation, human_decision, modification_reason, decided_by, _now()),
    )
    conn.commit()


def get_decision_log(conn):
    return conn.execute("SELECT * FROM decision_log ORDER BY created_at DESC").fetchall()
