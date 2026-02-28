"""
Audit Logger
------------
Every significant event in the verification flow is logged
to the audit_logs table for DPDP Act 2023 compliance.
"""

from datetime import datetime
from database.db import get_connection


def log_event(session_id: str, event: str, details: str = None, ip_address: str = None):
    """
    Write an event to the audit log.

    Events used throughout the system:
      OTP_SENT, OTP_VERIFIED, OTP_WRONG, OTP_EXPIRED,
      OTP_RESENT, SESSION_LOCKED,
      VERIFICATION_STARTED, VERIFICATION_COMPLETE,
      VERIFICATION_FLAGGED, VERIFICATION_REJECTED
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO audit_logs (session_id, event, details, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            event,
            details,
            ip_address,
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
    except Exception as e:
        print(f"⚠ Audit log error: {e}")
    finally:
        conn.close()


def get_audit_logs(session_id: str = None, limit: int = 50) -> list:
    """Retrieve audit logs, optionally filtered by session."""
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        if session_id:
            cursor.execute("""
                SELECT * FROM audit_logs
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM audit_logs
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
