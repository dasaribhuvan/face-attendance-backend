import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import OTP
from utils.send_email import send_otp_email


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# SEND OTP
# -------------------------
@router.post("/send-otp")
def send_otp(email: str, role: str, db: Session = Depends(get_db)):

    email = email.strip().lower()

    # Student Validation
    if role == "student":
        if not email.endswith("@mlrit.ac.in"):
            raise HTTPException(
                400,
                "Only MLRIT students allowed"
            )

    # Teacher Validation
    elif role == "teacher":
        if not (
            email.endswith("@mlrit.ac.in")
            or email.endswith("@mlrinstitutions.ac.in")
        ):
            raise HTTPException(
                400,
                "Only MLRIT teachers allowed"
            )

    else:
        raise HTTPException(400, "Invalid role")

    # Generate OTP
    otp = str(random.randint(100000, 999999))

    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    db_otp = OTP(
        email=email,
        otp=otp,
        expires_at=expiry,
        verified=False
    )

    db.add(db_otp)
    db.commit()

    # Send Email
    send_otp_email(email, otp)

    return {
        "message": "OTP sent successfully"
    }


# -------------------------
# VERIFY OTP
# -------------------------
@router.post("/verify-otp")
def verify_otp(
    email: str,
    otp: str,
    db: Session = Depends(get_db)
):

    email = email.strip().lower()

    record = db.query(OTP).filter(
        OTP.email == email
    ).order_by(OTP.id.desc()).first()

    if not record:
        raise HTTPException(
            400,
            "OTP not requested"
        )

    if record.otp != otp:
        raise HTTPException(
            400,
            "Invalid OTP"
        )

    if datetime.now(timezone.utc) > record.expires_at:
        raise HTTPException(
            400,
            "OTP expired"
        )

    record.verified = True
    db.commit()

    return {
        "message": "OTP verified successfully"
    }