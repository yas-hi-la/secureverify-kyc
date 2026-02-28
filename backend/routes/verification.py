"""
Verification Routes
--------------------
POST /api/verify/full        → Run all 3 layers after OTP is confirmed
GET  /api/verify/result/{id} → Get stored verification result
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime

from models.schemas import FullVerificationRequest, VerificationResponse, LayerResult
from services.sim_service         import verify_sim
from services.fingerprint_service import verify_fingerprint
from services.kyc_service         import verify_kyc
from services.trust_score_engine  import calculate_trust_score
from utils.audit                  import log_event
from database.db                  import get_connection

router = APIRouter()


@router.post("/full", response_model=VerificationResponse)
def full_verification(payload: FullVerificationRequest):
    """
    Run the complete 3-layer deep verification after OTP is confirmed.

    Layers:
      1. SIM Verification     (Telecom API)
      2. Fingerprint Biometric (UIDAI Aadhaar API)
      3. KYC Cross-Check      (CERSAI / CKYCR)

    Returns a trust score and final result.
    """

    conn   = get_connection()
    cursor = conn.cursor()

    # ── Pre-flight checks ─────────────────────────────────────────────────

    # 1. Session must exist
    cursor.execute("SELECT * FROM otp_sessions WHERE session_id = ?", (payload.session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. OTP must be verified first
    if not session["is_verified"]:
        conn.close()
        raise HTTPException(status_code=403, detail="OTP not yet verified. Complete OTP verification first.")

    # 3. Get customer details
    cursor.execute("SELECT * FROM customers WHERE session_id = ?", (payload.session_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer details not found")

    conn.close()

    log_event(payload.session_id, "VERIFICATION_STARTED", "3-layer verification initiated")

    # ── Run all 3 layers ──────────────────────────────────────────────────

    # Layer 1: SIM
    sim_result = verify_sim(
        mobile_number = customer["mobile_number"],
        customer_name = customer["full_name"],
        aadhaar       = customer["aadhaar_number"],
    )

    # Layer 2: Fingerprint
    fingerprint_result = verify_fingerprint(
        aadhaar_number    = customer["aadhaar_number"],
        fingerprint_token = payload.fingerprint_token,
    )

    # Layer 3: KYC
    kyc_result = verify_kyc(
        full_name      = customer["full_name"],
        aadhaar_number = customer["aadhaar_number"],
        pan_number     = customer["pan_number"],
    )

    # ── Trust Score Engine ────────────────────────────────────────────────
    trust = calculate_trust_score(sim_result, fingerprint_result, kyc_result)

    # ── Store Results ─────────────────────────────────────────────────────
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO verification_results (
            session_id, mobile_number,
            sim_subscriber_match, sim_active, sim_swap_detected, sim_score,
            fingerprint_match, liveness_passed, fingerprint_score,
            kyc_name_match, kyc_aadhaar_linked, kyc_pan_linked, kyc_score,
            trust_score, overall_result, failure_reason, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload.session_id,
        customer["mobile_number"],
        int(sim_result["details"].get("subscriber_match", False)),
        int(sim_result["details"].get("sim_active", False)),
        int(sim_result["details"].get("sim_swap_detected", False)),
        sim_result["score"],
        int(fingerprint_result["details"].get("fingerprint_match", False)),
        int(fingerprint_result["details"].get("liveness_passed", False)),
        fingerprint_result["score"],
        int(kyc_result["details"].get("kyc_name_match", False)),
        int(kyc_result["details"].get("aadhaar_linked", False)),
        int(kyc_result["details"].get("pan_linked", False)),
        kyc_result["score"],
        trust["trust_score"],
        trust["overall_result"],
        trust["failure_reason"],
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()

    # ── Audit log ─────────────────────────────────────────────────────────
    log_event(
        payload.session_id,
        f"VERIFICATION_{trust['overall_result']}",
        f"Trust score: {trust['trust_score']} | Result: {trust['overall_result']}",
    )

    # ── Build Response ────────────────────────────────────────────────────
    result_message = {
        "VERIFIED": "✅ Identity fully verified. Account can be activated.",
        "FLAGGED":  "⚠ Verification flagged for manual review.",
        "REJECTED": "❌ Verification failed. Please visit branch with original documents.",
    }.get(trust["overall_result"], "Verification complete.")

    return VerificationResponse(
        success        = trust["overall_result"] == "VERIFIED",
        session_id     = payload.session_id,
        overall_result = trust["overall_result"],
        trust_score    = trust["trust_score"],
        sim_layer      = LayerResult(**sim_result),
        fingerprint_layer = LayerResult(**fingerprint_result),
        kyc_layer      = LayerResult(**kyc_result),
        failure_reason = trust["failure_reason"],
        message        = result_message,
    )


@router.get("/result/{session_id}")
def get_verification_result(session_id: str):
    """Retrieve a previously stored verification result."""
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM verification_results WHERE session_id = ? ORDER BY id DESC LIMIT 1",
        (session_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No verification result found for this session")

    return dict(row)
