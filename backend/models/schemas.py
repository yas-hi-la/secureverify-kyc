"""
Pydantic models for request body validation and response shaping.
These act as the contract between frontend and backend.
"""

from pydantic import BaseModel, field_validator
from typing import Optional
import re


# ══════════════════════════════════════════════
# OTP MODELS
# ══════════════════════════════════════════════

class CustomerDetailsRequest(BaseModel):
    """Submitted when customer fills in the initial form."""
    full_name:      str
    date_of_birth:  str   # Format: YYYY-MM-DD
    aadhaar_number: str
    pan_number:     Optional[str] = None
    mobile_number:  str

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile(cls, v):
        v = v.strip().replace(" ", "")
        if not re.fullmatch(r"[6-9]\d{9}", v):
            raise ValueError("Mobile number must be a valid 10-digit Indian number starting with 6-9")
        return v

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar(cls, v):
        v = v.strip().replace(" ", "")
        if not re.fullmatch(r"\d{12}", v):
            raise ValueError("Aadhaar must be exactly 12 digits")
        return v

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v):
            raise ValueError("Invalid PAN format. Expected: ABCDE1234F")
        return v


class OTPVerifyRequest(BaseModel):
    """Submitted when customer enters the OTP."""
    session_id: str
    otp:        str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v):
        if not re.fullmatch(r"\d{6}", v.strip()):
            raise ValueError("OTP must be exactly 6 digits")
        return v.strip()


class OTPResendRequest(BaseModel):
    """Request to resend OTP."""
    session_id: str


# ══════════════════════════════════════════════
# VERIFICATION MODELS
# ══════════════════════════════════════════════

class FingerprintVerifyRequest(BaseModel):
    """
    In production, this would contain a biometric template.
    For the prototype, we accept a mock fingerprint token.
    """
    session_id:         str
    fingerprint_token:  str   # Mock: any non-empty string simulates a scan


class FullVerificationRequest(BaseModel):
    """
    Triggers all 3 layers of deep verification simultaneously.
    Called after OTP is confirmed.
    """
    session_id:         str
    fingerprint_token:  str   # Mock fingerprint data


# ══════════════════════════════════════════════
# RESPONSE MODELS
# ══════════════════════════════════════════════

class OTPSendResponse(BaseModel):
    success:        bool
    session_id:     str
    message:        str
    expires_in_sec: int


class OTPVerifyResponse(BaseModel):
    success:        bool
    session_id:     str
    message:        str
    otp_verified:   bool


class LayerResult(BaseModel):
    passed:  bool
    score:   float
    details: dict


class VerificationResponse(BaseModel):
    success:        bool
    session_id:     str
    overall_result: str           # "VERIFIED", "FLAGGED", "REJECTED"
    trust_score:    float         # 0.0 to 100.0
    sim_layer:      LayerResult
    fingerprint_layer: LayerResult
    kyc_layer:      LayerResult
    failure_reason: Optional[str] = None
    message:        str


class AuditLogEntry(BaseModel):
    session_id: str
    event:      str
    details:    Optional[str]
    timestamp:  str
