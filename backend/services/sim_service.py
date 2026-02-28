"""
SIM Verification Service (Layer 1)
------------------------------------
In production: calls real Telecom / DoT API to verify subscriber.
In this prototype: uses a mock database of sample numbers to simulate responses.

Mock numbers for testing:
  9876543210  →  VERIFIED (all checks pass)
  9123456789  →  SIM SWAP detected (flagged)
  9000000001  →  Name mismatch (fail)
  any other   →  Random realistic result
"""

import random
from datetime import datetime, timedelta


# ── Mock Telecom Database ──────────────────────────────────────────────────────
MOCK_TELECOM_DB = {
    "9876543210": {
        "subscriber_name": "Rahul Sharma",
        "aadhaar_linked":  "123456789012",
        "active":          True,
        "last_sim_swap":   None,          # No recent swap → safe
        "operator":        "Jio",
    },
    "9123456789": {
        "subscriber_name": "Priya Nair",
        "aadhaar_linked":  "234567890123",
        "active":          True,
        "last_sim_swap":   (datetime.utcnow() - timedelta(days=2)).isoformat(),  # Recent swap!
        "operator":        "Airtel",
    },
    "9000000001": {
        "subscriber_name": "Different Person",     # Name won't match
        "aadhaar_linked":  "000000000000",
        "active":          True,
        "last_sim_swap":   None,
        "operator":        "BSNL",
    },
}

SIM_SWAP_THRESHOLD_DAYS = 7   # SIM swap within 7 days = suspicious


def verify_sim(mobile_number: str, customer_name: str, aadhaar: str) -> dict:
    """
    Simulate a Telecom API call to verify SIM ownership.

    Returns:
        dict with:
          - subscriber_match (bool)
          - sim_active       (bool)
          - sim_swap_detected (bool)
          - score            (float 0-100)
          - details          (dict)
    """

    # Look up in mock DB or generate a realistic random result
    record = MOCK_TELECOM_DB.get(mobile_number)

    if record:
        telecom_name  = record["subscriber_name"]
        sim_active    = record["active"]
        last_swap     = record["last_sim_swap"]
        operator      = record["operator"]
    else:
        # For any other number → generate a plausible mock result
        telecom_name  = customer_name          # Assume match for demo
        sim_active    = True
        last_swap     = None
        operator      = random.choice(["Jio", "Airtel", "Vi", "BSNL"])

    # ── Checks ────────────────────────────────────────────────────────────
    # 1. Name match (case-insensitive, partial match allowed)
    subscriber_match = _names_match(customer_name, telecom_name)

    # 2. SIM swap detection
    sim_swap_detected = False
    if last_swap:
        swap_date         = datetime.fromisoformat(last_swap)
        days_since_swap   = (datetime.utcnow() - swap_date).days
        sim_swap_detected = days_since_swap <= SIM_SWAP_THRESHOLD_DAYS

    # ── Score Calculation ─────────────────────────────────────────────────
    score = 0.0
    if subscriber_match:   score += 50.0
    if sim_active:         score += 30.0
    if not sim_swap_detected: score += 20.0

    passed = subscriber_match and sim_active and not sim_swap_detected

    return {
        "passed": passed,
        "score":  round(score, 1),
        "details": {
            "subscriber_name_from_telecom": telecom_name,
            "subscriber_match":             subscriber_match,
            "sim_active":                   sim_active,
            "sim_swap_detected":            sim_swap_detected,
            "days_since_last_swap":         _days_since(last_swap),
            "operator":                     operator,
        },
    }


def _names_match(name1: str, name2: str) -> bool:
    """
    Fuzzy name match:
    - Case insensitive
    - Checks if first + last name words overlap significantly
    """
    words1 = set(name1.lower().split())
    words2 = set(name2.lower().split())
    common = words1 & words2
    # At least 1 common word (for names like "Rahul Sharma" vs "Sharma Rahul")
    return len(common) >= 1


def _days_since(iso_date_str):
    if not iso_date_str:
        return None
    delta = datetime.utcnow() - datetime.fromisoformat(iso_date_str)
    return delta.days
