from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from passlib.context import CryptContext
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from database.db import SessionLocal
from database.models import Teacher, Attendance, Student, Timetable, OTP
from utils.auth import create_access_token


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
# SCHEMAS
# ---------------------------
class TeacherCreate(BaseModel):
    name: str
    teacher_id: str
    email: str
    password: str

class TeacherLogin(BaseModel):
    email: str
    password: str

class TeacherRequest(BaseModel):
    name: str
    email: str
    teacher_id: str

class TeacherSetPassword(BaseModel):
    email: str
    password: str

# ---------------------------
# AUTH
# ---------------------------
@router.post("/register-teacher")
def register_teacher(data: TeacherCreate, db: Session = Depends(get_db)):

    password = data.password.strip()[:72]   # ✅ FIX
    hashed = pwd_context.hash(password)

    teacher = Teacher(
        name=data.name,
        teacher_id=data.teacher_id,
        email=data.email,
        password=hashed
    )

    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    return {"message": "Registered", "teacher_id": teacher.id}


@router.post("/login-teacher")
def login_teacher(
    data: TeacherLogin,
    db: Session = Depends(get_db)
):

    # ✅ Normalize email (safe for upper/lower case)
    email = data.email.strip().lower()

    teacher = db.query(Teacher).filter(
        Teacher.email.ilike(email)   # 🔥 Case-insensitive match
    ).first()

    # ❌ Teacher not found
    if not teacher:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # ❌ Not approved yet
    if not teacher.approved:
        raise HTTPException(
            status_code=403,
            detail="Waiting for admin approval"
        )

    # ❌ Password not set
    if not teacher.password:
        raise HTTPException(
            status_code=403,
            detail="Password not set. Complete registration"
        )

    # ✅ Clean password
    password = data.password.strip()[:72]

    # ❌ Wrong password
    if not pwd_context.verify(
        password,
        teacher.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # ✅ Create token
    token = create_access_token(
        data={"teacher_id": teacher.id}
    )

    return {
        "access_token": token,
        "id": teacher.id,
        "name": teacher.name
    }


# ---------------------------
# DASHBOARD
# ---------------------------
@router.get("/teacher/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    today_day = datetime.today().strftime("%A")

    students = db.query(Student).count()

    classes_today = db.query(Timetable).filter(
        Timetable.day_of_week == today_day
    ).count()

    attendance_taken = db.query(Attendance.period).filter(
        Attendance.date == today
    ).distinct().count()

    pending = max(classes_today - attendance_taken, 0)

    return {
        "students": students,
        "classes_today": classes_today,
        "attendance_taken": attendance_taken,
        "pending": pending
    }


# ---------------------------
# TODAY CLASSES
# ---------------------------
@router.get("/classes/today")
def today_classes(db: Session = Depends(get_db)):
    today_day = datetime.today().strftime("%A")

    classes = db.query(Timetable).filter(
        Timetable.day_of_week == today_day
    ).all()

    result = []
    for c in classes:
        exists = db.query(Attendance).filter(
            Attendance.period == c.period,
            Attendance.date == date.today()
        ).first()

        result.append({
            "id": c.id,
            "subject": c.subject,
            "period": c.period,
            "attendance_taken": bool(exists)
        })

    return result


# ---------------------------
# INSIGHTS (🔥 FIXED)
# ---------------------------
@router.get("/teacher/insights")
def teacher_insights(db: Session = Depends(get_db)):

    today = date.today()
    last_5_days = [today - timedelta(days=i) for i in range(5)]

    students = db.query(Student).all()

    insights = []

    for student in students:

        # get attendance for last 5 days
        records = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.date.in_(last_5_days)
        ).all()

        # convert to dict for easy lookup
        attendance_map = {r.date: r.status for r in records}

        # check all 5 days absent
        consecutive_absent = True

        for d in last_5_days:
            if attendance_map.get(d) != "Absent":
                consecutive_absent = False
                break

        if consecutive_absent:
            insights.append({
                "name": student.name,
                "roll": student.roll_no,
                "days": 5
            })

    return {"insights": insights}


# ---------------------------
# CHART DATA
# ---------------------------
# ---------------------------
# CHART DATA (FINAL FIXED)
# ---------------------------
@router.get("/teacher/chart-data")
def chart_data(db: Session = Depends(get_db)):

    today = date.today()
    today_day = datetime.today().strftime("%A")

    # ---------------------------
    # TODAY PIE (COMPLETED vs PENDING)
    # ---------------------------
    classes = db.query(Timetable).filter(
        Timetable.day_of_week == today_day
    ).all()

    completed, pending = 0, 0

    for c in classes:
        exists = db.query(Attendance).filter(
            Attendance.period == c.period,
            Attendance.date == today
        ).first()

        if exists:
            completed += 1
        else:
            pending += 1

    # ---------------------------
    # WEEKLY TREND (LAST 7 DAYS 🔥)
    # ---------------------------
    week_data = []

    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)

        attendance_count = db.query(Attendance.period).filter(
            Attendance.date == day_date
        ).distinct().count()

        week_data.append({
            "day": day_date.strftime("%a"),  # Mon, Tue...
            "attendance": attendance_count
        })

    return {
        "today": [
            {"name": "Completed", "value": completed},
            {"name": "Pending", "value": pending}
        ],
        "weekly": week_data
    }

# ---------------------------
# LOW ATTENDANCE
# ---------------------------
@router.get("/teacher/low-attendance")
def low_attendance(db: Session = Depends(get_db)):

    data = db.query(
        Student.id,
        Student.name,
        Student.roll_no,
        func.count(Attendance.id).label("total"),
        func.sum(
            case(
                (Attendance.status == "Present", 1),
                else_=0
            )
        ).label("present")
    ).join(
        Attendance, Attendance.student_id == Student.id
    ).group_by(Student.id).all()

    result = []

    for s in data:
        percentage = (s.present / s.total) * 100 if s.total else 0

        if percentage < 50:
            result.append({
                "name": s.name,
                "roll": s.roll_no,
                "percentage": round(percentage, 2)
            })

    return result



# ---------------------------
# GET ALL STUDENTS 🔥
# ---------------------------
@router.get("/students")
def get_students(db: Session = Depends(get_db)):

    students = db.query(Student).all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "roll_no": s.roll_no,
            "image": None  # optional
        }
        for s in students
    ]





# ---------------------------
# SMART STUDENT ANALYSIS 🔥🔥
# ---------------------------
from collections import defaultdict
from fastapi import HTTPException

@router.get("/teacher/student-analysis/{student_id}")
def student_analysis(student_id: int, db: Session = Depends(get_db)):

    student = db.query(Student).filter(Student.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    records = db.query(Attendance).filter(
        Attendance.student_id == student_id
    ).order_by(Attendance.date).all()

    total = len(records)
    present = sum(1 for r in records if r.status == "Present")
    absent = total - present

    percentage = (present / total * 100) if total else 0

    # ---------- STREAK ----------
    current_streak = 0
    last_status = None

    for r in reversed(records):
        if last_status is None:
            last_status = r.status

        if r.status == last_status:
            current_streak += 1
        else:
            break

    # ---------- TREND ----------
    last5 = records[-5:]
    present_count = sum(1 for r in last5 if r.status == "Present")

    if present_count >= 4:
        trend = "Improving 📈"
    elif present_count <= 2:
        trend = "Declining 📉"
    else:
        trend = "Stable ➖"

    # ---------- RISK ----------
    if percentage < 50:
        risk = "HIGH 🚨"
    elif percentage < 75:
        risk = "MEDIUM ⚠"
    else:
        risk = "LOW ✅"

    # ---------- PREDICTION ----------
    if percentage >= 75 and trend == "Improving 📈":
        prediction = "Excellent 🔥"
    elif percentage >= 60:
        prediction = "Safe ✅"
    elif percentage >= 40:
        prediction = "At Risk ⚠"
    else:
        prediction = "Critical 🚨"

    consistency = percentage

    # ---------- INSIGHTS ----------
    insights = []

    if percentage < 50:
        insights.append("🚨 Critical attendance level")
    if trend == "Declining 📉":
        insights.append("📉 Attendance is decreasing recently")
    if current_streak >= 3 and last_status == "Absent":
        insights.append("🔥 Absent for multiple consecutive days")

    # ---------- SUGGESTIONS ----------
    suggestions = []

    if percentage < 75:
        suggestions.append("📢 Conduct parent meeting")
        suggestions.append("📝 Assign extra sessions")
    if trend == "Declining 📉":
        suggestions.append("📊 Monitor daily attendance closely")

    # ---------- DISTRIBUTION ----------
    distribution = [
        {"name": "Present", "value": present},
        {"name": "Absent", "value": absent}
    ]

    # ---------- MONTHLY ----------
    month_map = {}

    for r in records:
        month = r.date.strftime("%b")
        if month not in month_map:
            month_map[month] = {"present": 0, "total": 0}

        month_map[month]["total"] += 1
        if r.status == "Present":
            month_map[month]["present"] += 1

    monthly = []
    for m, v in month_map.items():
        pct = (v["present"] / v["total"] * 100) if v["total"] else 0
        monthly.append({"month": m, "value": round(pct, 2)})

    # ---------- SUBJECT-WISE (🔥 FIXED) ----------
    subject_map = defaultdict(lambda: {"present": 0, "total": 0})

    for r in records:
        subject_map[r.subject]["total"] += 1
        if r.status == "Present":
            subject_map[r.subject]["present"] += 1

    subjects = []
    ledger = []

    for subject, val in subject_map.items():
        total_s = val["total"]
        present_s = val["present"]

        pct = (present_s / total_s * 100) if total_s else 0

        subjects.append({
            "subject": subject,
            "percentage": round(pct, 2)
        })

        ledger.append({
            "subject": subject,
            "attended": present_s,
            "total": total_s
        })

    # ---------- FINAL RESPONSE ----------
    return {
        "student": {
            "name": student.name,
            "roll": student.roll_no
        },
        "stats": {
            "total": total,
            "present": present,
            "absent": absent,
            "percentage": round(percentage, 2)
        },
        "advanced": {
            "risk": risk,
            "trend": trend,
            "streak": current_streak,
            "prediction": prediction,
            "consistency": round(consistency, 2)
        },
        "distribution": distribution,
        "monthly": monthly,
        "subjects": subjects,
        "ledger": ledger,
        "insights": insights,
        "suggestions": suggestions
    }



# -----------------------------
# DOWNLOAD STUDENT REPORT (PDF)
# -----------------------------






@router.post("/teacher/request")
def teacher_request(
    data: TeacherRequest,
    db: Session = Depends(get_db)
):

    email = data.email.strip().lower()

    # Check OTP verified
    otp = db.query(OTP).filter(
        OTP.email == email,
        OTP.verified == True
    ).order_by(OTP.id.desc()).first()

    if not otp:
        raise HTTPException(
            400,
            "Email not verified"
        )

    # Check already exists
    existing = db.query(Teacher).filter(
        Teacher.email == email
    ).first()

    if existing:
        raise HTTPException(
            400,
            "Request already sent"
        )

    teacher = Teacher(
    name=data.name,
    email=email,
    teacher_id=data.teacher_id,
    approved=False,
    rejected=False,   # ADD
    email_verified=True
)

    db.add(teacher)
    db.commit()

    return {
        "message": "Request sent to admin"
    }


from utils.auth import create_access_token


class TeacherLogin(BaseModel):
    email: str
    password: str


@router.post("/teacher/login")
def teacher_login(
    data: TeacherLogin,
    db: Session = Depends(get_db)
):

    teacher = db.query(Teacher).filter(
        Teacher.email == data.email
    ).first()

    if not teacher:
        raise HTTPException(
            401,
            "Invalid credentials"
        )

    if not teacher.approved:
        raise HTTPException(
            403,
            "Admin approval pending"
        )

    if not pwd_context.verify(
        data.password,
        teacher.password
    ):
        raise HTTPException(
            401,
            "Invalid credentials"
        )

    token = create_access_token(
        data={"teacher_id": teacher.id}
    )

    return {
        "access_token": token,
        "name": teacher.name
    }


@router.get("/teacher/status")
def teacher_status(email: str, db: Session = Depends(get_db)):

    email = email.strip().lower()

    teacher = db.query(Teacher).filter(
        Teacher.email == email
    ).first()

    # New user
    if not teacher:
        return {"status": "new"}

    # Waiting
    if not teacher.approved and not teacher.rejected:
        return {"status": "waiting"}

    # Rejected
    if teacher.rejected:
        return {"status": "rejected"}

    # Approved but password not set
    if teacher.approved and not teacher.password:
        return {"status": "approved"}

    # Active
    return {"status": "active"}



class TeacherSetPassword(BaseModel):
    email: str
    password: str


@router.post("/teacher/set-password")
def set_password(
    data: TeacherSetPassword,
    db: Session = Depends(get_db)
):

    email = data.email.strip().lower()

    teacher = db.query(Teacher).filter(
        Teacher.email == email
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=404,
            detail="Teacher not found"
        )

    hashed = pwd_context.hash(data.password)

    teacher.password = hashed

    db.commit()

    return {
        "message": "Password set successfully"
    }