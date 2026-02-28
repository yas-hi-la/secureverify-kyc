"""
OTP Routes
----------
POST /api/otp/send    → Submit customer details, get OTP
POST /api/otp/verify  → Verify the OTP entered by customer
POST /api/otp/resend  → Resend OTP (with cooldown)
GET  /api/otp/status/{session_id} → Check session status
"""

from fastapi import APIRouter, HTTPException, Request
from models.schemas import (
    CustomerDetailsRequest,
    OTPVerifyRequest,
    OTPResendRequest,
    OTPSendResponse,
    OTPVerifyResponse,
)
from services.otp_service import create_otp_session, verify_otp, resend_otp
from database.db import get_connection

router = APIRouter()


@router.post("/send", response_model=OTPSendResponse)
def send_otp(payload: CustomerDetailsRequest, request: Request):
    """
    Step 1: Customer submits their details.
    Validates the form, creates a session, and sends OTP via SMS.
    """
    try:
        result = create_otp_session(payload.model_dump())
        return OTPSendResponse(
            success=True,
            session_id=result["session_id"],
            message=result["message"],
            expires_in_sec=result["expires_in_sec"],
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


@router.post("/verify", response_model=OTPVerifyResponse)
def validate_otp(payload: OTPVerifyRequest):
    """
    Step 2: Customer enters the OTP they received.
    Returns success/failure and handles retry logic.
    """
    result = verify_otp(payload.session_id, payload.otp)

    if result.get("otp_verified"):
        return OTPVerifyResponse(
            success=True,
            session_id=payload.session_id,
            otp_verified=True,
            message=result["message"],
        )
    else:
        # Don't raise HTTP error for wrong OTP — return 200 with failure info
        # so frontend can show remaining attempts
        return OTPVerifyResponse(
            success=False,
            session_id=payload.session_id,
            otp_verified=False,
            message=result["message"],
        )


@router.post("/resend")
def resend(payload: OTPResendRequest):
    """
    Resend OTP to the same mobile number.
    Enforces 30-second cooldown between resend requests.
    """
    result = resend_otp(payload.session_id)
    if not result["success"]:
        raise HTTPException(status_code=429, detail=result["message"])
    return result


@router.get("/status/{session_id}")
def get_session_status(session_id: str):
    """
    Get the current status of an OTP session.
    Useful for frontend to check if session is still valid.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM otp_sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    conn.close()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id":   session_id,
        "is_verified":  bool(session["is_verified"]),
        "is_locked":    bool(session["is_locked"]),
        "attempts":     session["attempts"],
        "expires_at":   session["expires_at"],
        "mobile":       f"****{session['mobile_number'][-4:]}",   # Masked
    }
