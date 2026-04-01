from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Integer,
    String,
    ForeignKey,
    DateTime,
    UniqueConstraint
)

from database.db import Base


# -------------------------
# STUDENT
# -------------------------
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    roll_no = Column(String, unique=True)
    email = Column(String, unique=True)
    password = Column(String)


# -------------------------
# TEACHER
# -------------------------
class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String)
    email = Column(String, unique=True, index=True)
    teacher_id = Column(String)

    password = Column(String, nullable=True)

    approved = Column(Boolean, default=False)
    rejected = Column(Boolean, default=False)   # ADD THIS
    email_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

# -------------------------
# EMBEDDING
# -------------------------
class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    embedding_vector = Column(String)


# -------------------------
# ATTENDANCE
# -------------------------
class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    subject = Column(String)
    date = Column(Date)
    period = Column(Integer)
    status = Column(String)

    __table_args__ = (
        UniqueConstraint(
            'student_id',
            'date',
            'period',
            name='unique_attendance'
        ),
    )


# -------------------------
# TIMETABLE
# -------------------------
class Timetable(Base):

    __tablename__ = "timetable"

    id = Column(Integer, primary_key=True, index=True)

    subject = Column(String, nullable=False)
    period = Column(Integer, nullable=False)
    day_of_week = Column(String, nullable=False)

    teacher_id = Column(Integer)

    start_date = Column(Date)
    end_date = Column(Date)


# -------------------------
# OTP
# -------------------------
class OTP(Base):
    __tablename__ = "otp"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, index=True)
    otp = Column(String)

    verified = Column(Boolean, default=False)

    expires_at = Column(
        DateTime(timezone=True)
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


# -------------------------
# ADMIN
# -------------------------
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)   