"""
Mobile Number Ownership Verification System
Backend API - FastAPI + Python
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes import otp, verification, dashboard
from database.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("🔴 Server shutting down")


app = FastAPI(
    title="Mobile Number Ownership Verification API",
    description="3-Layer verification: OTP + SIM + Fingerprint + KYC",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend to call backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all route groups
app.include_router(otp.router,          prefix="/api/otp",          tags=["OTP"])
app.include_router(verification.router, prefix="/api/verify",       tags=["Verification"])
app.include_router(dashboard.router,    prefix="/api/dashboard",    tags=["Dashboard"])


@app.get("/")
def root():
    return {
        "message": "Mobile Number Ownership Verification API is running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
