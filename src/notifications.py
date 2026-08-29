"""
In-app notification templates. No real SMS/email integration — the
prototype only needs notifications to show up on the patient dashboard.
"""
from src import database as db


def notify_appointment_confirmed(conn, patient_id, date, time, department):
    message = (
        f"Your appointment request has been approved.\n"
        f"Date: {date} | Time: {time} | Department: {department} | Status: CONFIRMED"
    )
    return db.create_notification(conn, patient_id, message, "APPOINTMENT_CONFIRMED")


def notify_clarification_needed(conn, patient_id):
    message = "Additional information is needed before your request can be reviewed."
    return db.create_notification(conn, patient_id, message, "CLARIFICATION_REQUESTED")


def notify_escalated(conn, patient_id):
    message = "Your request has been escalated for additional human review."
    return db.create_notification(conn, patient_id, message, "ESCALATED")


def notify_awaiting_review(conn, patient_id):
    message = "Your request is awaiting review."
    return db.create_notification(conn, patient_id, message, "AWAITING_REVIEW")
