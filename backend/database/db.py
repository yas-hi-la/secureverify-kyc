"""
Database setup using SQLite (no external DB needed for prototype).
All tables are created automatically on first run.
"""

import sqlite3
import os

DB_PATH = "verification.db"


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows dict-like access to rows
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── OTP Sessions Table ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT    NOT NULL UNIQUE,
            mobile_number   TEXT    NOT NULL,
            otp_hash        TEXT    NOT NULL,
            attempts        INTEGER DEFAULT 0,
            is_verified     INTEGER DEFAULT 0,
            is_locked       INTEGER DEFAULT 0,
            created_at      TEXT    NOT NULL,
            expires_at      TEXT    NOT NULL,
            last_resent_at  TEXT
        )
    """)

    # ── Customer Details Table ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT    NOT NULL,
            full_name       TEXT    NOT NULL,
            date_of_birth   TEXT    NOT NULL,
            aadhaar_number  TEXT    NOT NULL,
            pan_number      TEXT,
            mobile_number   TEXT    NOT NULL,
            created_at      TEXT    NOT NULL
        )
    """)

    # ── Verification Results Table ───────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_results (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id              TEXT    NOT NULL,
            mobile_number           TEXT    NOT NULL,

            -- Layer 1: SIM Verification
            sim_subscriber_match    INTEGER DEFAULT 0,
            sim_active              INTEGER DEFAULT 0,
            sim_swap_detected       INTEGER DEFAULT 0,
            sim_score               REAL    DEFAULT 0.0,

            -- Layer 2: Fingerprint Biometric
            fingerprint_match       INTEGER DEFAULT 0,
            liveness_passed         INTEGER DEFAULT 0,
            fingerprint_score       REAL    DEFAULT 0.0,

            -- Layer 3: KYC Cross-Check
            kyc_name_match          INTEGER DEFAULT 0,
            kyc_aadhaar_linked      INTEGER DEFAULT 0,
            kyc_pan_linked          INTEGER DEFAULT 0,
            kyc_score               REAL    DEFAULT 0.0,

            -- Final Result
            trust_score             REAL    DEFAULT 0.0,
            overall_result          TEXT    DEFAULT 'PENDING',
            failure_reason          TEXT,

            verified_at             TEXT    NOT NULL
        )
    """)

    # ── Audit Log Table ──────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            event       TEXT    NOT NULL,
            details     TEXT,
            ip_address  TEXT,
            timestamp   TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("✅ All tables initialized")
