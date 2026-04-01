from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from database.db import SessionLocal
from database.models import Student, Embedding
from passlib.context import CryptContext
from utils.auth import create_access_token, verify_token
from recognition.arcface_embeddings import generate_embedding_from_images
from database.models import OTP

from typing import List
import json

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------
# DB
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------
# GET CURRENT STUDENT (🔥 IMPORTANT)
# ---------------------------
def get_current_student(payload: dict = Depends(verify_token)):

    student_id = payload.get("student_id")

    if student_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return student_id


# ---------------------------
# REGISTER
# ---------------------------



@router.post("/login-student")
def login_student(
    email: str,
    password: str,
    db: Session = Depends(get_db)
):

    # ✅ CLEAN INPUTS
    email = email.strip().lower()
    password = password.strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    student = db.query(Student).filter(Student.email == email).first()

    if not student:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ FIX BCRYPT LIMIT
    password = password[:72]

    if not pwd_context.verify(password, student.password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    token = create_access_token(data={"student_id": student.id})

    return {
        "access_token": token,
        "student_id": student.id,
        "name": student.name,
        "roll": student.roll_no
    }


# ---------------------------
# FACE REGISTER (🔥 PROTECTED)
# ---------------------------





@router.post("/register-complete")
async def register_complete(
    name: str = Form(...),
    roll: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    try:
        # =========================
        # CLEAN INPUTS
        # =========================
        name = name.strip()
        roll = roll.strip()
        email = email.strip().lower()
        password = password.strip()

        if not name or not roll or not email or not password:
            raise HTTPException(status_code=400, detail="All fields required")


        # =========================
        # CHECK OTP VERIFIED
        # =========================
        otp_record = db.query(OTP).filter(
        OTP.email == email,
        OTP.verified == True
        ).order_by(OTP.id.desc()).first()

        if not otp_record:
            raise HTTPException(status_code=400, detail="OTP not requested")

        if datetime.now(timezone.utc) > otp_record.expires_at:
            raise HTTPException(status_code=400, detail="OTP expired")


        # =========================
        # CHECK DUPLICATES
        # =========================
        if db.query(Student).filter(Student.roll_no == roll).first():
            raise HTTPException(status_code=400, detail="Roll already exists")

        if db.query(Student).filter(Student.email == email).first():
            raise HTTPException(status_code=400, detail="Email already exists")


        # =========================
        # HASH PASSWORD
        # =========================
        password = password[:72]
        hashed = pwd_context.hash(password)


        # =========================
        # CREATE STUDENT (NO COMMIT)
        # =========================
        student = Student(
            name=name,
            roll_no=roll,
            email=email,
            password=hashed
        )

        db.add(student)
        db.flush()


        

        # =========================
        # PROCESS IMAGES
        # =========================
        uploaded_images = []
        webcam_images = []

        for img in images:
            content = await img.read()

            if "webcam" in img.filename.lower():
                webcam_images.append(content)
            else:
                uploaded_images.append(content)


        # =========================
        # FILTER IMAGES
        # =========================
        import cv2
        import numpy as np

        def filter_images(image_list):

            good = []

            for img_bytes in image_list:

                np_arr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if img is None:
                    continue

                # blur detection
                blur_score = cv2.Laplacian(img, cv2.CV_64F).var()

                if blur_score < 50:
                    print("Skipping blurry image")
                    continue

                good.append(img_bytes)

            return good


        # 🔥 PRIORITY: UPLOAD FIRST
        good_images = filter_images(uploaded_images)

        # fallback to webcam images
        if len(good_images) == 0:
            good_images = filter_images(webcam_images)


        if len(good_images) == 0:
            raise HTTPException(
                status_code=400,
                detail="Images too blurry. Please capture clear face images"
            )


        # =========================
        # GENERATE EMBEDDING
        # =========================
        embedding = generate_embedding_from_images(good_images)
        if embedding is None:
            raise HTTPException(
                status_code=400,
                detail="Face not detected. Please upload clear front-facing images"
            )


        # =========================
        # SAVE EMBEDDING
        # =========================
        emb = Embedding(
            student_id=student.id,
            embedding_vector=json.dumps(embedding)
        )

        db.add(emb)


        # =========================
        # DELETE OTP AFTER SUCCESS
        # =========================
        db.query(OTP).filter(
        OTP.email == email
        ).delete()


        # =========================
        # FINAL COMMIT
        # =========================
        db.commit()

        return {
            "message": "Registration successful",
            "student_id": student.id
        }


    # =========================
    # ERROR HANDLING
    # =========================
    
    except Exception as e:
        db.rollback()
        print("REGISTER ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))