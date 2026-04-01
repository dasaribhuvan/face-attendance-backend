from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM")

security = HTTPBearer()


def get_current_student_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    print("TOKEN RECEIVED:", token)

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print("PAYLOAD:", payload)

        student_id = payload.get("student_id")

        if student_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return student_id

    except JWTError as e:
        print("JWT ERROR:", e)
        raise HTTPException(status_code=401, detail="Invalid token")