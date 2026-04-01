from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.db import engine, SessionLocal
from backend.database.models import Base, Admin

from backend.routes.student_routes import router as student_router
from backend.routes.teacher_routes import router as teacher_router
from backend.routes.attendance_routes import router as attendance_router
from backend.routes.timetable_routes import router as timetable_router
from backend.routes.otp import router as otp_router
from backend.routes.admin_routes import router as admin_router

import os
from dotenv import load_dotenv
from passlib.context import CryptContext

from backend.recognition.model_loader import get_face_app


# -------------------------
# LOAD ENV
# -------------------------
load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    raise Exception("Admin credentials missing in .env")


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# -------------------------
# FASTAPI APP
# -------------------------
app = FastAPI()


# -------------------------
# CREATE / UPDATE ADMIN
# -------------------------
def create_admin():

    db = SessionLocal()

    try:
        admin = db.query(Admin).first()

        if not admin:
            admin = Admin(
                name="Admin",
                email=ADMIN_EMAIL.strip().lower(),
                password=pwd_context.hash(
                    ADMIN_PASSWORD.strip()
                )
            )

            db.add(admin)

        else:
            admin.email = ADMIN_EMAIL.strip().lower()
            admin.password = pwd_context.hash(
                ADMIN_PASSWORD.strip()
            )

        db.commit()

    finally:
        db.close()


# -------------------------
# STARTUP EVENT
# -------------------------
@app.on_event("startup")
def startup():

    print("🚀 Starting Application...")

    # Create tables
    print("📦 Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Create admin
    print("👤 Creating admin...")
    create_admin()

    # Load Face Model
    print("🧠 Loading face model...")
    get_face_app()

    print("✅ Application Ready")


# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # change later for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# ROUTERS
# -------------------------
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(attendance_router)
app.include_router(timetable_router)
app.include_router(otp_router)
app.include_router(admin_router)


# -------------------------
# ROOT
# -------------------------
@app.get("/")
def home():
    return {"message": "Face Attendance API Running 🚀"}


@app.get("/health")
def health():
    return {"status": "ok"}