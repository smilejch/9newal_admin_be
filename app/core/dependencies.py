# app/core/dependencies.py
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_access_token
from app.modules.auth import models
import re
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 제외할 경로 패턴
EXCLUDED_PATHS = [
    r"^/auth/login$",
    r"^/auth/logout$",
    r"^/auth/register$",
    r"^/auth/refresh$",
    r"^/auth/reset-password",
    r"^/docs.*",
    r"^/openapi\.json$",
    r"^/redoc.*",
    r"^/$",
    r"^/health$"
]

security = HTTPBearer(auto_error=False)


async def get_current_user_global(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    """
    글로벌 사용자 인증 - 특정 경로는 제외
    리프레시 토큰 자동 처리 포함
    """
    print("TES123")
    # 제외 경로 확인
    path = request.url.path
    for pattern in EXCLUDED_PATHS:
        if re.match(pattern, path):
            return None  # 인증 불필요
    # 토큰이 없으면 에러
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    try:
        # 토큰 검증
        payload = verify_access_token(credentials.credentials)

        # 사용자 조회
        user_no = payload.get("user_no")
        if user_no is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        user = db.query(models.ComUser).filter(
            models.ComUser.user_no == user_no
        ).first()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        return user

    except HTTPException as e:
        # 액세스 토큰이 만료된 경우 특별한 에러 메시지
        if "expired" in e.detail.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token expired.",
                headers={"WWW-Authenticate": "Bearer", "Token-Expired": "true"}
            )
        raise e

