# Mobile Number Ownership Verification — Backend API

## Overview
Python FastAPI backend for the 3-layer mobile number ownership verification system.

---

## Project Structure

```
backend/
├── main.py                         ← App entry point
├── requirements.txt                ← All dependencies
├── .env.example                    ← Copy to .env and fill in your values
│
├── database/
│   └── db.py                       ← SQLite setup, table creation
│
├── models/
│   └── schemas.py                  ← Request/response Pydantic models
│
├── routes/
│   ├── otp.py                      ← OTP send / verify / resend endpoints
│   ├── verification.py             ← 3-layer deep verification endpoint
│   └── dashboard.py                ← Stats, audit logs, recent activity
│
├── services/
│   ├── otp_service.py              ← OTP generation, hashing, SMS sending
│   ├── sim_service.py              ← SIM/Telecom verification (Layer 1)
│   ├── fingerprint_service.py      ← Fingerprint biometric check (Layer 2)
│   ├── kyc_service.py              ← KYC cross-check (Layer 3)
│   └── trust_score_engine.py       ← Aggregates all 3 layers into a score
│
└── utils/
    └── audit.py                    ← DPDP-compliant audit logging
```

---

## Setup & Run

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your SMS provider keys
```

### 3. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 4. Open API docs
```
http://localhost:8000/docs
```

---

## API Endpoints

### OTP Flow
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/otp/send` | Submit customer details, send OTP |
| POST | `/api/otp/verify` | Verify OTP entered by customer |
| POST | `/api/otp/resend` | Resend OTP (30s cooldown) |
| GET  | `/api/otp/status/{session_id}` | Check session status |

### Verification
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/verify/full` | Run all 3 layers of deep verification |
| GET  | `/api/verify/result/{session_id}` | Get stored verification result |

### Dashboard
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/dashboard/stats` | Summary statistics |
| GET | `/api/dashboard/recent` | Recent verification attempts |
| GET | `/api/dashboard/audit-logs` | All audit logs |
| GET | `/api/dashboard/audit-logs/{session_id}` | Logs for specific session |

---

## Example API Flow

### Step 1: Submit customer details
```bash
curl -X POST http://localhost:8000/api/otp/send \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Rahul Sharma",
    "date_of_birth": "1990-05-15",
    "aadhaar_number": "123456789012",
    "pan_number": "ABCDE1234F",
    "mobile_number": "9876543210"
  }'
```

Response:
```json
{
  "success": true,
  "session_id": "abc-123-xyz",
  "message": "OTP sent to ****3210",
  "expires_in_sec": 300
}
```

### Step 2: Verify OTP (in DEV mode, check terminal for OTP)
```bash
curl -X POST http://localhost:8000/api/otp/verify \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123-xyz", "otp": "482910"}'
```

### Step 3: Run deep verification
```bash
curl -X POST http://localhost:8000/api/verify/full \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123-xyz", "fingerprint_token": "mock_finger_scan_abc"}'
```

Response:
```json
{
  "success": true,
  "overall_result": "VERIFIED",
  "trust_score": 87.5,
  "sim_layer":         { "passed": true,  "score": 100.0, "details": {...} },
  "fingerprint_layer": { "passed": true,  "score": 100.0, "details": {...} },
  "kyc_layer":         { "passed": true,  "score": 100.0, "details": {...} },
  "failure_reason": null,
  "message": "✅ Identity fully verified. Account can be activated."
}
```

---

## Mock Test Numbers

| Mobile | Aadhaar | Scenario |
|--------|---------|----------|
| 9876543210 | 123456789012 | ✅ All layers pass (VERIFIED) |
| 9123456789 | 234567890123 | ⚠ SIM swap detected (FLAGGED) |
| 9000000001 | 000000000000 | ❌ Name mismatch + adverse flag (REJECTED) |
| Any other  | Any other    | ✅ Generic pass (demo mode) |

---

## SMS Provider Setup

### Option A: MSG91 (Recommended for India — cheaper)
1. Sign up at https://msg91.com
2. Create an OTP template
3. Add `MSG91_AUTH_KEY` and `MSG91_TEMPLATE_ID` to `.env`

### Option B: Twilio (International)
1. Sign up at https://twilio.com
2. Get a phone number
3. Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` to `.env`

> In **development mode** (default), OTP is printed to the terminal — no SMS account needed.

---

## Compliance Note
All verification data is stored per DPDP Act 2023 requirements:
- OTPs are stored as SHA-256 hashes (never plain text)
- Mobile numbers are masked in responses
- Every action is logged to the audit trail
- Data is kept only as long as needed
