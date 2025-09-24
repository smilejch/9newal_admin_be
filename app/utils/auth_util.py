from fastapi import Request, HTTPException, status
from app.core.security import verify_access_token
from app.modules.auth.models import ComUser
from sqlalchemy.orm import Session
import random
import string

def get_authenticated_user_no(request: Request) -> str:
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found in cookies1"
        )

    payload = verify_access_token(token=refresh_token, token_type="refresh")
    user_no = payload.get("user_no")
    company_no = payload.get("company_no")

    if not user_no or not company_no:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다. 유효한 토큰이 아닙니다."
        )

    return user_no, company_no


def generate_temporary_password(length: int = 8) -> str:
    characters = string.ascii_letters + string.digits
    temp_password = ''.join(random.choice(characters) for _ in range(length))

    if not any(c.isalpha() for c in temp_password):
        temp_password = temp_password[:-1] + random.choice(string.ascii_letters)
    if not any(c.isdigit() for c in temp_password):
        temp_password = temp_password[:-1] + random.choice(string.digits)

    return temp_password