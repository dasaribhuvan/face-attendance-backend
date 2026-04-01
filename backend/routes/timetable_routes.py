from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date, timedelta

from database.db import SessionLocal
from database.models import Timetable

router = APIRouter()


# -----------------------------
# DATABASE SESSION
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# REQUEST MODELS
# -----------------------------
class ClassCreate(BaseModel):
    subject: str
    period: int
    day_of_week: str
    teacher_id: int
    start_date: date   # ✅ Only this needed


class ClassUpdate(BaseModel):
    subject: str
    period: int


# -----------------------------
# ADD CLASS (AUTO 4-MONTH VALIDITY)
# -----------------------------
@router.post("/teacher/add-class")
def add_class(data: ClassCreate, db: Session = Depends(get_db)):

    # ✅ Auto calculate 4 months (approx 120 days)
    end_date = data.start_date + timedelta(days=120)

    # ✅ Prevent overlapping timetable in same semester
    existing = db.query(Timetable).filter(
        Timetable.day_of_week == data.day_of_week,
        Timetable.period == data.period,
        Timetable.teacher_id == data.teacher_id,
        Timetable.start_date <= end_date,
        Timetable.end_date >= data.start_date
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Period already exists in this semester"
        )

    # ✅ Create new class
    new_class = Timetable(
        subject=data.subject,
        period=data.period,
        day_of_week=data.day_of_week,
        teacher_id=data.teacher_id,
        start_date=data.start_date,
        end_date=end_date
    )

    db.add(new_class)
    db.commit()
    db.refresh(new_class)

    return {
        "message": "Class added successfully (valid for 4 months)",
        "data": {
            "id": new_class.id,
            "subject": new_class.subject,
            "period": new_class.period,
            "day_of_week": new_class.day_of_week,
            "start_date": new_class.start_date,
            "end_date": new_class.end_date
        }
    }


# -----------------------------
# GET TIMETABLE BY DAY + DATE
# -----------------------------
@router.get("/timetable/day")
def get_day(day: str, current_date: date, db: Session = Depends(get_db)):

    classes = db.query(Timetable).filter(
        Timetable.day_of_week == day,
        Timetable.start_date <= current_date,
        Timetable.end_date >= current_date
    ).order_by(Timetable.period).all()

    return classes


# -----------------------------
# UPDATE CLASS
# -----------------------------
@router.put("/teacher/update-class/{id}")
def update_class(id: int, data: ClassUpdate, db: Session = Depends(get_db)):

    c = db.query(Timetable).filter(Timetable.id == id).first()

    if not c:
        raise HTTPException(status_code=404, detail="Class not found")

    c.subject = data.subject
    c.period = data.period

    db.commit()

    return {"message": "Class updated successfully"}


# -----------------------------
# DELETE CLASS
# -----------------------------
@router.delete("/teacher/delete-class/{id}")
def delete_class(id: int, db: Session = Depends(get_db)):

    c = db.query(Timetable).filter(Timetable.id == id).first()

    if not c:
        raise HTTPException(status_code=404, detail="Class not found")

    db.delete(c)
    db.commit()

    return {"message": "Class deleted successfully"}