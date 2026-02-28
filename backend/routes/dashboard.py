"""
Dashboard Routes
-----------------
GET /api/dashboard/stats          → Summary stats (total, verified, flagged, rejected)
GET /api/dashboard/audit-logs     → All audit logs (paginated)
GET /api/dashboard/audit-logs/{id} → Audit logs for a specific session
GET /api/dashboard/recent         → Recent verification attempts
"""

from fastapi import APIRouter, Query
from database.db  import get_connection
from utils.audit  import get_audit_logs

router = APIRouter()


@router.get("/stats")
def get_stats():
    """
    Returns summary statistics for the dashboard.
    Useful for showing counts of verified / flagged / rejected on the UI.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM verification_results")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as c FROM verification_results WHERE overall_result = 'VERIFIED'")
    verified = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM verification_results WHERE overall_result = 'FLAGGED'")
    flagged = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM verification_results WHERE overall_result = 'REJECTED'")
    rejected = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM otp_sessions WHERE is_verified = 1")
    otp_verified = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM otp_sessions WHERE is_locked = 1")
    locked_sessions = cursor.fetchone()["c"]

    conn.close()

    return {
        "total_verifications":  total,
        "verified":             verified,
        "flagged":              flagged,
        "rejected":             rejected,
        "otp_verified_count":   otp_verified,
        "locked_sessions":      locked_sessions,
        "verification_rate":    round((verified / total * 100) if total > 0 else 0, 1),
    }


@router.get("/recent")
def get_recent_verifications(limit: int = Query(default=10, le=50)):
    """
    Returns the most recent verification attempts.
    Shows session ID, mobile (masked), result, trust score, and timestamp.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            vr.session_id,
            substr(vr.mobile_number, 1, 6) || '****' AS mobile_masked,
            vr.overall_result,
            vr.trust_score,
            vr.failure_reason,
            vr.verified_at,
            vr.sim_subscriber_match,
            vr.fingerprint_match,
            vr.kyc_name_match,
            vr.sim_swap_detected
        FROM verification_results vr
        ORDER BY vr.verified_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@router.get("/audit-logs")
def all_audit_logs(limit: int = Query(default=50, le=200)):
    """
    Returns the most recent audit log entries (all sessions).
    For compliance reporting.
    """
    return get_audit_logs(limit=limit)


@router.get("/audit-logs/{session_id}")
def session_audit_logs(session_id: str):
    """
    Returns all audit log entries for a specific session.
    """
    logs = get_audit_logs(session_id=session_id)
    if not logs:
        return {"session_id": session_id, "logs": [], "message": "No logs found for this session"}
    return {"session_id": session_id, "logs": logs, "count": len(logs)}
