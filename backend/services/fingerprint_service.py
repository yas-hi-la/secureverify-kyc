"""
Fingerprint Biometric Verification Service (Layer 2)
------------------------------------------------------
In production: sends fingerprint template to UIDAI Aadhaar Authentication API.
In this prototype: simulates the biometric check using mock Aadhaar records.

Mock Aadhaar biometric records for testing:
  123456789012  →  Fingerprint always matches
  234567890123  →  Fingerprint matches, liveness fails
  000000000000  →  No biometric record found
"""

import random
import hashlib


# ── Mock UIDAI Aadhaar Biometric Database ─────────────────────────────────────
MOCK_AADHAAR_DB = {
    "123456789012": {
        "name":              "Rahul Sharma",
        "has_biometric":     True,
        "biometric_quality": "HIGH",
    },
    "234567890123": {
        "name":              "Priya Nair",
        "has_biometric":     True,
        "biometric_quality": "LOW",
    },
    "000000000000": {
        "name":              None,
        "has_biometric":     False,
        "biometric_quality": None,
    },
}


def verify_fingerprint(aadhaar_number: str, fingerprint_token: str) -> dict:
    """
    Simulate UIDAI Aadhaar fingerprint authentication.

    In real implementation:
      - Convert fingerprint scan to ISO template
      - Send to https://auth.uidai.gov.in/
      - Receive YES/NO with error code

    Here we simulate based on:
      - Whether Aadhaar has a biometric record
      - Quality of fingerprint token provided
      - Liveness detection simulation

    Returns:
        dict with fingerprint_match, liveness_passed, score, details
    """

    record = MOCK_AADHAAR_DB.get(aadhaar_number)

    if record:
        has_biometric     = record["has_biometric"]
        biometric_quality = record["biometric_quality"]
        registered_name   = record["name"]
    else:
        # Unknown Aadhaar → assume valid for demo (any number works)
        has_biometric     = True
        biometric_quality = "HIGH"
        registered_name   = "Unknown"

    # ── Fingerprint Match Simulation ──────────────────────────────────────
    if not has_biometric:
        return {
            "passed": False,
            "score":  0.0,
            "details": {
                "fingerprint_match":  False,
                "liveness_passed":    False,
                "error":              "No biometric record found for this Aadhaar",
                "aadhaar_registered": False,
            },
        }

    # Token quality check (simulate: empty or very short token fails)
    token_quality = _assess_token_quality(fingerprint_token)

    fingerprint_match = token_quality >= 0.5
    liveness_passed   = _simulate_liveness(fingerprint_token, biometric_quality)

    # ── Score Calculation ─────────────────────────────────────────────────
    score = 0.0
    if fingerprint_match: score += 60.0
    if liveness_passed:   score += 40.0

    # Penalise low biometric quality
    if biometric_quality == "LOW":
        score *= 0.85

    passed = fingerprint_match and liveness_passed

    return {
        "passed": passed,
        "score":  round(score, 1),
        "details": {
            "fingerprint_match":    fingerprint_match,
            "liveness_passed":      liveness_passed,
            "biometric_quality":    biometric_quality,
            "token_quality_score":  round(token_quality, 2),
            "aadhaar_registered":   has_biometric,
            "matched_name":         registered_name,
        },
    }


def _assess_token_quality(token: str) -> float:
    """
    Simulate fingerprint token quality assessment.
    In production, this would analyse ridge clarity, minutiae count etc.
    Here: longer / more complex tokens = higher quality.
    """
    if not token or len(token) < 4:
        return 0.1
    if len(token) < 10:
        return 0.4
    # Use hash-based pseudo-randomness for consistency
    hash_val = int(hashlib.md5(token.encode()).hexdigest(), 16)
    quality  = 0.55 + (hash_val % 1000) / 2000   # 0.55 to 1.05, capped at 1.0
    return min(quality, 1.0)


def _simulate_liveness(token: str, biometric_quality: str) -> bool:
    """
    Simulate liveness detection (ensures it's a real finger, not a spoof).
    In production: uses pulse detection, 3D depth mapping etc.
    """
    if biometric_quality == "LOW":
        return False
    # Deterministic based on token so same token always gives same result
    hash_val = int(hashlib.sha256(token.encode()).hexdigest(), 16)
    return (hash_val % 10) > 2   # 70% pass rate for simulation
