import smtplib
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_otp_email(to_email, otp):

    subject = "Face Attendance OTP Verification"

    body = f"""
Hello,

Your OTP for Face Attendance Registration is:

{otp}

This OTP is valid for 5 minutes.

Do not share this OTP with anyone.

Face Attendance System
"""

    msg = MIMEMultipart()
    msg["From"] = EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL, PASSWORD)

        text = msg.as_string()
        server.sendmail(EMAIL, to_email, text)

        server.quit()

        print("OTP email sent successfully")

    except Exception as e:
        print("Error sending email:", e)