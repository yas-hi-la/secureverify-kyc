"""
KYC Cross-Check Service (Layer 3)
-----------------------------------
In production: queries CERSAI / CKYCR (Central KYC Registry) APIs.
In this prototype: uses mock KYC records to simulate the response.

What it checks:
  - Does the name match KYC records?
  - Is the Aadhaar number linked and active?
  - Is the PAN number linked correctly?
  - Is there any existing adverse flag on this customer?
"""


# ── Mock CKYCR / CERSAI Database ──────────────────────────────────────────────
MOCK_KYC_DB = {
    "123456789012": {   # Aadhaar as key
        "kyc_name":      "Rahul Sharma",
        "pan_linked":    "ABCDE1234F",
        "aadhaar_active": True,
        "adverse_flag":  False,
        "kyc_status":    "COMPLETE",
    },
    "234567890123": {
        "kyc_name":      "Priya Nair",
        "pan_linked":    "PQRST5678G",
        "aadhaar_active": True,
        "adverse_flag":  False,
        "kyc_status":    "COMPLETE",
    },
    "000000000000": {
        "kyc_name":      None,
        "pan_linked":    None,
        "aadhaar_active": False,
        "adverse_flag":  True,
        "kyc_status":    "FLAGGED",
    },
}


def verify_kyc(full_name: str, aadhaar_number: str, pan_number: str = None) -> dict:
    """
    Cross-check customer details against KYC registry.

    Returns:
        dict with kyc_name_match, aadhaar_linked, pan_linked, score, details
    """

    record = MOCK_KYC_DB.get(aadhaar_number)

    if record:
        kyc_name        = record["kyc_name"]
        pan_in_kyc      = record["pan_linked"]
        aadhaar_active  = record["aadhaar_active"]
        adverse_flag    = record["adverse_flag"]
        kyc_status      = record["kyc_status"]
    else:
        # Unknown Aadhaar → treat as new customer (partial pass)
        kyc_name        = full_name
        pan_in_kyc      = pan_number
        aadhaar_active  = True
        adverse_flag    = False
        kyc_status      = "NEW"

    # ── Checks ────────────────────────────────────────────────────────────

    # 1. Name match
    name_match = _names_match(full_name, kyc_name) if kyc_name else False

    # 2. Aadhaar linked and active
    aadhaar_linked = aadhaar_active

    # 3. PAN match (optional — only if PAN was provided)
    pan_linked = False
    if pan_number and pan_in_kyc:
        pan_linked = pan_number.upper() == pan_in_kyc.upper()
    elif not pan_number:
        pan_linked = True   # Not provided → not penalised

    # 4. No adverse flag
    no_adverse = not adverse_flag

    # ── Score Calculation ─────────────────────────────────────────────────
    score = 0.0
    if name_match:     score += 40.0
    if aadhaar_linked: score += 30.0
    if pan_linked:     score += 20.0
    if no_adverse:     score += 10.0

    passed = name_match and aadhaar_linked and no_adverse

    return {
        "passed": passed,
        "score":  round(score, 1),
        "details": {
            "kyc_name_match":      name_match,
            "name_in_kyc":         kyc_name,
            "aadhaar_linked":      aadhaar_linked,
            "pan_linked":          pan_linked,
            "adverse_flag":        adverse_flag,
            "kyc_status":          kyc_status,
            "verification_note":   _get_note(name_match, aadhaar_linked, adverse_flag),
        },
    }


def _names_match(name1: str, name2: str) -> bool:
    """Case-insensitive name match with word overlap."""
    if not name1 or not name2:
        return False
    words1 = set(name1.lower().split())
    words2 = set(name2.lower().split())
    return len(words1 & words2) >= 1


def _get_note(name_match: bool, aadhaar_linked: bool, adverse_flag: bool) -> str:
    if adverse_flag:
        return "Customer has an adverse flag in KYC registry. Manual review required."
    if not name_match:
        return "Name mismatch between submitted details and KYC records."
    if not aadhaar_linked:
        return "Aadhaar is inactive or not linked in KYC registry."
    return "All KYC checks passed successfully."
