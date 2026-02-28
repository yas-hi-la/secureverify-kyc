"""
Trust Score Engine
-------------------
Takes results from all 3 verification layers and computes:
  - A final trust score (0–100)
  - An overall result: VERIFIED / FLAGGED / REJECTED
  - A human-readable failure reason (if any)

Scoring weights:
  SIM Verification     →  35%
  Fingerprint Biometric →  40%
  KYC Cross-Check      →  25%
"""

# Layer weights
WEIGHT_SIM         = 0.35
WEIGHT_FINGERPRINT = 0.40
WEIGHT_KYC         = 0.25

# Thresholds
VERIFIED_THRESHOLD = 70.0   # Score >= 70 → VERIFIED
FLAGGED_THRESHOLD  = 40.0   # Score 40–69 → FLAGGED for manual review
# Score < 40 → REJECTED


def calculate_trust_score(sim_result: dict, fingerprint_result: dict, kyc_result: dict) -> dict:
    """
    Aggregate layer scores into a final trust score and result.

    Args:
        sim_result:         Output from sim_service.verify_sim()
        fingerprint_result: Output from fingerprint_service.verify_fingerprint()
        kyc_result:         Output from kyc_service.verify_kyc()

    Returns:
        dict with trust_score, overall_result, failure_reason
    """

    sim_score         = sim_result.get("score", 0.0)
    fingerprint_score = fingerprint_result.get("score", 0.0)
    kyc_score         = kyc_result.get("score", 0.0)

    # Weighted average
    trust_score = (
        sim_score         * WEIGHT_SIM +
        fingerprint_score * WEIGHT_FINGERPRINT +
        kyc_score         * WEIGHT_KYC
    )
    trust_score = round(trust_score, 1)

    # Determine result
    all_passed = (
        sim_result.get("passed", False) and
        fingerprint_result.get("passed", False) and
        kyc_result.get("passed", False)
    )

    if all_passed and trust_score >= VERIFIED_THRESHOLD:
        overall_result = "VERIFIED"
        failure_reason = None
    elif trust_score >= FLAGGED_THRESHOLD:
        overall_result = "FLAGGED"
        failure_reason = _build_failure_reason(sim_result, fingerprint_result, kyc_result)
    else:
        overall_result = "REJECTED"
        failure_reason = _build_failure_reason(sim_result, fingerprint_result, kyc_result)

    return {
        "trust_score":    trust_score,
        "overall_result": overall_result,
        "failure_reason": failure_reason,
        "layer_scores": {
            "sim":         sim_score,
            "fingerprint": fingerprint_score,
            "kyc":         kyc_score,
        },
    }


def _build_failure_reason(sim_result: dict, fingerprint_result: dict, kyc_result: dict) -> str:
    """Build a human-readable failure reason by checking which layers failed."""
    reasons = []

    # SIM failures
    sim_details = sim_result.get("details", {})
    if not sim_details.get("subscriber_match"):
        reasons.append("SIM subscriber name does not match customer name")
    if sim_details.get("sim_swap_detected"):
        reasons.append("Recent SIM swap detected (within 7 days)")
    if not sim_details.get("sim_active"):
        reasons.append("SIM card is inactive")

    # Fingerprint failures
    fp_details = fingerprint_result.get("details", {})
    if not fp_details.get("fingerprint_match"):
        reasons.append("Fingerprint does not match Aadhaar biometric record")
    if not fp_details.get("liveness_passed"):
        reasons.append("Liveness detection failed — possible spoof attempt")

    # KYC failures
    kyc_details = kyc_result.get("details", {})
    if not kyc_details.get("kyc_name_match"):
        reasons.append("Name mismatch with KYC registry")
    if not kyc_details.get("aadhaar_linked"):
        reasons.append("Aadhaar not active in KYC registry")
    if kyc_details.get("adverse_flag"):
        reasons.append("Customer has an adverse flag in KYC records")

    return "; ".join(reasons) if reasons else "Verification did not meet minimum threshold"
