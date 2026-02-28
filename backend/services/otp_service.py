"""
OTP Service
-----------
Handles:
  - Generating a secure 6-digit OTP
  - Sending it via SMS (Twilio or MSG91)
  - Storing hashed OTP in the database
  - Validating submitted OTP
  - Retry/lockout/resend logic
"""

import os
import random
import hashlib
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

from database.db import get_connection
from utils.audit import log_event

load_dotenv()

OTP_EXPIRY_MINUTES      = int(os.getenv("OTP_EXPIRY_MINUTES", 5))
OTP_MAX_RETRIES         = int(os.getenv("OTP_MAX_RETRIES", 3))
OTP_RESEND_COOLDOWN_SEC = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", 30))
APP_ENV                 = os.getenv("APP_ENV", "development")


# ── Helpers ────────────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """Generate a secure 6-digit OTP."""
    return str(random.SystemRandom().randint(100000, 999999))


def hash_otp(otp: str) -> str:
    """Hash OTP with SHA-256 before storing (never store plain OTP)."""
    return hashlib.sha256(otp.encode()).hexdigest()


def now_str() -> str:
    return datetime.utcnow().isoformat()


def expiry_str() -> str:
    return (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()


# ── SMS Sending ────────────────────────────────────────────────────────────────

def send_otp_sms(mobile: str, otp: str) -> dict:
    """
    Send OTP via SMS.
    In development mode: just prints OTP to console (no SMS sent).
    In production mode: sends via Twilio or MSG91.
    """

    if APP_ENV == "development":
        # ── DEV MODE: Print OTP to terminal ──
        print(f"\n{'='*40}")
        print(f"  📱 DEV MODE — OTP for {mobile}: {otp}")
        print(f"{'='*40}\n")
        return {"success": True, "provider": "console", "message": f"OTP printed to console: {otp}"}

    # ── PRODUCTION: Try MSG91 first, fall back to Twilio ──
    msg91_key = os.getenv("MSG91_AUTH_KEY")
    if msg91_key:
        return _send_via_msg91(mobile, otp)

    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    if twilio_sid:
        return _send_via_twilio(mobile, otp)

    raise RuntimeError("No SMS provider configured. Set MSG91_AUTH_KEY or TWILIO_ACCOUNT_SID in .env")


def _send_via_msg91(mobile: str, otp: str) -> dict:
    """Send OTP via MSG91 (recommended for India)."""
    import requests

    url = "https://api.msg91.com/api/v5/otp"
    payload = {
        "template_id": os.getenv("MSG91_TEMPLATE_ID"),
        "mobile":      f"91{mobile}",
        "authkey":     os.getenv("MSG91_AUTH_KEY"),
        "otp":         otp,
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    data = response.json()

    if data.get("type") == "success":
        return {"success": True, "provider": "msg91"}
    else:
        raise RuntimeError(f"MSG91 error: {data}")


def _send_via_twilio(mobile: str, otp: str) -> dict:
    """Send OTP via Twilio."""
    from twilio.rest import Client

    client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
    )
    message = client.messages.create(
        body=f"Your verification OTP is {otp}. Valid for {OTP_EXPIRY_MINUTES} minutes. Do not share this with anyone.",
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        to=f"+91{mobile}",
    )
    return {"success": True, "provider": "twilio", "sid": message.sid}


# ── Core OTP Logic ─────────────────────────────────────────────────────────────

def create_otp_session(customer_data: dict) -> dict:
    """
    Create a new OTP session:
    1. Generate OTP
    2. Hash and store in DB
    3. Save customer details
    4. Send SMS
    Returns session_id to frontend.
    """
    otp        = generate_otp()
    session_id = str(uuid.uuid4())
    otp_hashed = hash_otp(otp)
    mobile     = customer_data["mobile_number"]

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        # Store OTP session
        cursor.execute("""
            INSERT INTO otp_sessions
              (session_id, mobile_number, otp_hash, attempts, is_verified, is_locked, created_at, expires_at)
            VALUES (?, ?, ?, 0, 0, 0, ?, ?)
        """, (session_id, mobile, otp_hashed, now_str(), expiry_str()))

        # Store customer details
        cursor.execute("""
            INSERT INTO customers
              (session_id, full_name, date_of_birth, aadhaar_number, pan_number, mobile_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            customer_data["full_name"],
            customer_data["date_of_birth"],
            customer_data["aadhaar_number"],
            customer_data.get("pan_number"),
            mobile,
            now_str(),
        ))

        conn.commit()

        # Send SMS
        sms_result = send_otp_sms(mobile, otp)

        log_event(session_id, "OTP_SENT", f"OTP sent via {sms_result.get('provider')}")

        return {
            "success":        True,
            "session_id":     session_id,
            "expires_in_sec": OTP_EXPIRY_MINUTES * 60,
            "message":        f"OTP sent to +91{mobile[-4:].zfill(10)[-4:].rjust(10, '*')}",
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def verify_otp(session_id: str, submitted_otp: str) -> dict:
    """
    Validate submitted OTP:
    - Check session exists and not locked
    - Check expiry
    - Compare hashes
    - Increment attempts; lock after max retries
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM otp_sessions WHERE session_id = ?", (session_id,))
        session = cursor.fetchone()

        if not session:
            return {"success": False, "otp_verified": False, "message": "Session not found. Please start again."}

        if session["is_locked"]:
            return {"success": False, "otp_verified": False, "message": "Session is locked due to too many failed attempts. Please try again after 24 hours."}

        if session["is_verified"]:
            return {"success": True, "otp_verified": True, "message": "OTP already verified."}

        # Check expiry
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.utcnow() > expires_at:
            log_event(session_id, "OTP_EXPIRED", "OTP expired")
            return {"success": False, "otp_verified": False, "message": "OTP has expired. Please request a new one."}

        # Compare hash
        submitted_hash = hash_otp(submitted_otp)
        attempts       = session["attempts"] + 1

        if submitted_hash == session["otp_hash"]:
            # ── SUCCESS ──
            cursor.execute("""
                UPDATE otp_sessions SET is_verified = 1, attempts = ? WHERE session_id = ?
            """, (attempts, session_id))
            conn.commit()
            log_event(session_id, "OTP_VERIFIED", "OTP verified successfully")
            return {
                "success":      True,
                "otp_verified": True,
                "session_id":   session_id,
                "message":      "OTP verified successfully. Proceeding to deep verification.",
            }
        else:
            # ── WRONG OTP ──
            remaining = OTP_MAX_RETRIES - attempts
            should_lock = attempts >= OTP_MAX_RETRIES

            cursor.execute("""
                UPDATE otp_sessions SET attempts = ?, is_locked = ? WHERE session_id = ?
            """, (attempts, 1 if should_lock else 0, session_id))
            conn.commit()

            if should_lock:
                log_event(session_id, "SESSION_LOCKED", f"Locked after {attempts} failed attempts")
                return {"success": False, "otp_verified": False, "message": "Too many wrong attempts. Session locked for 24 hours."}

            log_event(session_id, "OTP_WRONG", f"Wrong OTP — attempt {attempts}/{OTP_MAX_RETRIES}")
            return {
                "success":      False,
                "otp_verified": False,
                "message":      f"Incorrect OTP. {remaining} attempt(s) remaining.",
            }

    finally:
        conn.close()


def resend_otp(session_id: str) -> dict:
    """
    Resend a fresh OTP (if cooldown has passed and session is not locked).
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM otp_sessions WHERE session_id = ?", (session_id,))
        session = cursor.fetchone()

        if not session:
            return {"success": False, "message": "Session not found."}

        if session["is_locked"]:
            return {"success": False, "message": "Session is locked. Cannot resend OTP."}

        if session["is_verified"]:
            return {"success": False, "message": "OTP already verified. No need to resend."}

        # Check cooldown
        if session["last_resent_at"]:
            last_sent = datetime.fromisoformat(session["last_resent_at"])
            elapsed   = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN_SEC:
                wait = int(OTP_RESEND_COOLDOWN_SEC - elapsed)
                return {"success": False, "message": f"Please wait {wait} seconds before resending."}

        # Generate new OTP and update session
        new_otp    = generate_otp()
        new_hash   = hash_otp(new_otp)
        new_expiry = expiry_str()

        cursor.execute("""
            UPDATE otp_sessions
               SET otp_hash = ?, expires_at = ?, attempts = 0, last_resent_at = ?
             WHERE session_id = ?
        """, (new_hash, new_expiry, now_str(), session_id))
        conn.commit()

        mobile     = session["mobile_number"]
        sms_result = send_otp_sms(mobile, new_otp)

        log_event(session_id, "OTP_RESENT", f"OTP resent via {sms_result.get('provider')}")

        return {
            "success":        True,
            "session_id":     session_id,
            "expires_in_sec": OTP_EXPIRY_MINUTES * 60,
            "message":        "New OTP sent successfully.",
        }

    finally:
        conn.close()
