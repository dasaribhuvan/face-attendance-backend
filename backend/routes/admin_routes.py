from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel

from database.db import SessionLocal
from database.models import Admin
from utils.auth import create_access_token
from database.models import Teacher
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

router = APIRouter()

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AdminLogin(BaseModel):
    email: str
    password: str


@router.post("/admin/login")
def admin_login(
    data: AdminLogin,
    db: Session = Depends(get_db)
):

    email = data.email.strip().lower()
    password = data.password.strip()

    admin = db.query(Admin).filter(
        Admin.email == email
    ).first()

    # Debug prints
    print("LOGIN EMAIL:", email)
    print("ENV EMAIL:", ADMIN_EMAIL)
    print("DB ADMIN:", admin.email if admin else "None")

    if not admin:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not pwd_context.verify(
        password,
        admin.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token(
        data={"admin_id": admin.id}
    )

    return {
        "access_token": token,
        "name": admin.name
    }


@router.get("/admin/pending-teachers")
def pending_teachers(db: Session = Depends(get_db)):

    teachers = db.query(Teacher).filter(
        Teacher.approved == False,
        Teacher.rejected == False
    ).all()

    return teachers

@router.post("/admin/approve/{teacher_id}")
def approve_teacher(
    teacher_id: int,
    db: Session = Depends(get_db)
):

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id
    ).first()

    if not teacher:
        raise HTTPException(
            404,
            "Teacher not found"
        )

    teacher.approved = True

    db.commit()

    return {
        "message": "Teacher approved"
    }



@router.post("/admin/reject/{teacher_id}")
def reject_teacher(
    teacher_id: int,
    db: Session = Depends(get_db)
):

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=404,
            detail="Teacher not found"
        )

    teacher.rejected = True
    teacher.approved = False

    db.commit()

    return {
        "message": "Teacher rejected"
    }



@router.get("/admin/approved-teachers")
def approved_teachers(db: Session = Depends(get_db)):

    teachers = db.query(Teacher).filter(
        Teacher.approved == True
    ).all()

    return teachers


@router.get("/admin/all-teachers")
def all_teachers(db: Session = Depends(get_db)):

    teachers = db.query(Teacher).all()

    return teachers


@router.post("/admin/reject/{teacher_id}")
def reject_teacher(
    teacher_id: int,
    db: Session = Depends(get_db)
):

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id
    ).first()

    if not teacher:
        raise HTTPException(
            404,
            "Teacher not found"
        )

    teacher.rejected = True
    teacher.approved = False

    db.commit()

    return {
        "message": "Teacher rejected"
    }

