from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session
from database.db import SessionLocal
from database.models import Attendance , Student
from sqlalchemy import func, extract
from websocket_manager import manager
from datetime import date
import json
from datetime import datetime
from database.db import SessionLocal
from database.models import Attendance, Timetable
from utils.auth import get_current_student


from sqlalchemy import func, extract
from utils.dependencies import get_current_student_id
from pydantic import BaseModel
from typing import List
from datetime import date

class AttendanceRecord(BaseModel):
    student_id: int
    subject: str
    date: date
    period: int
    status: str

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- MARK ATTENDANCE ----------



@router.post("/submit-attendance")
def submit_attendance(records: list = Body(...), db: Session = Depends(get_db)):

    for r in records:

        date_obj = datetime.strptime(r["date"], "%Y-%m-%d").date()

        existing = db.query(Attendance).filter(
            Attendance.student_id == r["student_id"],
            Attendance.date == date_obj,
            Attendance.period == r["period"]
        ).first()

        if existing:
            existing.status = r["status"]

        else:
            new_record = Attendance(
                student_id=r["student_id"],
                subject=r["subject"],
                date=date_obj,
                period=r["period"],
                status=r["status"]
            )

            db.add(new_record)

    db.commit()

    return {"message": "Attendance saved"}


# ---------- SUMMARY ----------

@router.get("/student/attendance-summary")
def summary(
    student_id:int = Depends(get_current_student_id),
    db:Session=Depends(get_db)
):

    total = db.query(Attendance).filter(
        Attendance.student_id == student_id
    ).count()

    present = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "Present"
    ).count()

    absent = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "Absent"
    ).count()

    percentage = 0

    if total > 0:
        percentage = round((present / total) * 100)

    return {
        "total_classes": total,
        "present": present,
        "absent": absent,
        "percentage": percentage
    }


# ---------- RECENT ATTENDANCE ----------

@router.get("/student/recent-attendance")
def recent(
    student_id:int = Depends(get_current_student_id),
    db:Session=Depends(get_db)
):

    records = db.query(Attendance).filter(
        Attendance.student_id == student_id
    ).order_by(Attendance.date.desc()).limit(10).all()

    result = []

    for r in records:
        result.append({
            "date": r.date.strftime("%d %b"),
            "subject": r.subject,
            "period": r.period,
            "status": r.status
        })

    return result


# ---------- DAY ATTENDANCE ----------

@router.get("/student/day-attendance")
def day_attendance(
    date_selected: date,
    student_id: int = Depends(get_current_student),
    db: Session = Depends(get_db)
):

    # ✅ Get day name (Monday, Tuesday...)
    day_name = date_selected.strftime("%A")

    # ✅ Get timetable for that day
    timetable = db.query(Timetable).filter(
        Timetable.day_of_week == day_name,
        Timetable.start_date <= date_selected,
        Timetable.end_date >= date_selected
    ).all()

    result = []

    for t in timetable:

        # ✅ Check attendance for each period
        record = db.query(Attendance).filter(
            Attendance.student_id == student_id,
            Attendance.date == date_selected,
            Attendance.period == t.period
        ).first()

        result.append({
            "period": t.period,
            "subject": t.subject,
            "status": record.status if record else "Not Updated"
        })

    return result


# ---------- ANALYTICS ----------

from datetime import date, timedelta
from sqlalchemy import func

@router.get("/student/analytics")
def analytics(
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db)
):

    # ✅ ONLY COUNT UPDATED CLASSES
    present = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "Present"
    ).count()

    absent = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "Absent"
    ).count()

    total_classes = present + absent   # ✅ FIXED

    percentage = (present / total_classes * 100) if total_classes > 0 else 0

    return {
        "total_classes": total_classes,
        "present": present,
        "absent": absent,
        "not_updated": 0,   # optional
        "percentage": round(percentage),

        "formatted": {
            "average": f"{percentage:.2f}%",
            "present": f"{present} / {total_classes}",
            "absent": f"{absent} / {total_classes}",
            "not_updated": "Ignored"
        },

        "distribution": [
            {"name": "Present", "value": present},
            {"name": "Absent", "value": absent}
        ]
    }

# ---------- MONTHLY ATTENDANCE ----------

@router.get("/student/monthly-attendance")
def monthly(
    student_id:int = Depends(get_current_student_id),
    db:Session=Depends(get_db)
):

    from calendar import month_abbr

    data = db.query(
        extract("month", Attendance.date).label("month"),
        Attendance.status,
        func.count().label("count")
    ).filter(
        Attendance.student_id == student_id
    ).group_by(
        extract("month", Attendance.date),
        Attendance.status
    ).all()

    month_map={}

    for m,status,count in data:

        if m not in month_map:
            month_map[m]={"present":0,"total":0}

        month_map[m]["total"]+=count

        if status=="Present":
            month_map[m]["present"]+=count

    result=[]

    for m in sorted(month_map):

        total=month_map[m]["total"]
        present=month_map[m]["present"]

        percent=round((present/total)*100) if total>0 else 0

        result.append({
            "month": month_abbr[int(m)],
            "attendance": percent
        })

    return result


# ---------- SUBJECT ATTENDANCE ----------

@router.get("/student/subject-attendance")
def subject(
    student_id:int = Depends(get_current_student_id),
    db:Session=Depends(get_db)
):

    data=db.query(
        Attendance.subject,
        Attendance.status,
        func.count().label("count")
    ).filter(
        Attendance.student_id==student_id
    ).group_by(
        Attendance.subject,
        Attendance.status
    ).all()

    subject_map={}

    for subject,status,count in data:

        if subject not in subject_map:
            subject_map[subject]={"present":0,"absent":0}

        if status=="Present":
            subject_map[subject]["present"] += count   # ✅ FIX

        elif status=="Absent":
            subject_map[subject]["absent"] += count   # ✅ FIX

    result=[]

    for s in subject_map:
        total = subject_map[s]["present"] + subject_map[s]["absent"]

        if total > 0:   # ✅ IMPORTANT FILTER
            result.append({
                "subject":s,
                "present":subject_map[s]["present"],
                "absent":subject_map[s]["absent"]
            })

    return result


from fastapi import APIRouter, UploadFile, File, Form
from recognition.group_attendance import process_group_images



from typing import List
from fastapi import UploadFile, File

@router.post("/detect-faces")
async def detect_faces(
    images: List[UploadFile] = File(...)
):
    image_list = []

    # Read all uploaded images
    for image in images:
        contents = await image.read()
        image_list.append(contents)

    # Process multiple images
    attendance = process_group_images(image_list)

    return {
        "recognized_students": attendance
    }


from datetime import date
from fastapi import Depends
from sqlalchemy.orm import Session

@router.get("/attendance/update")
def update_attendance(date: date, period: int, db: Session = Depends(get_db)):

    students = db.query(Student).all()

    records = db.query(Attendance).filter(
        Attendance.date == date,
        Attendance.period == period
    ).all()

    status_map = {r.student_id: r.status for r in records}

    result = []

    for s in students:
        result.append({
            "student_id": s.id,
            "roll_no": s.roll_no,
            "name": s.name,
            "status": status_map.get(s.id, "Absent")
        })

    return result



@router.get("/attendance/status")
def attendance_status(date: str, db: Session = Depends(get_db)):

    from datetime import datetime

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()

    records = db.query(Attendance).filter(
        Attendance.date == date_obj
    ).all()

    status = {}

    for r in records:
        status[r.period] = True

    return status