# app/core/security.py
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.core.config import TOKEN_CONFIG

from app.modules.auth import models

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==============================
# 비밀번호 유틸
# ==============================
def hash_password(password: str) -> str:
    """bcrypt 해시 생성"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


# ==============================
# 내부 공통 유틸
# ==============================
def _generate_jwt(data: dict, secret: str, expire_delta: timedelta) -> str:
    """
    JWT 생성 공통 함수
    payload에 exp (UTC datetime)가 추가되어 인코딩 됨
    """
    payload = data.copy()
    payload.update({"exp": datetime.utcnow() + expire_delta})
    return jwt.encode(payload, secret, algorithm=TOKEN_CONFIG.ALGORITHM)


def _prune_old_refresh_tokens(db: Session, user_no: int, limit: int = 3):
    """
    유저별로 리프레시 토큰을 최근 `limit`개만 남기고 삭제 (오래된 것부터 삭제)
    """
    try:
        # 삭제할 token_no들을 먼저 조회
        token_nos_to_delete = (
            db.query(models.ComUserTokenAuth.token_no)
            .filter(models.ComUserTokenAuth.user_no == user_no)
            .order_by(models.ComUserTokenAuth.created_at.asc())
            .offset(limit)
            .all()
        )

        if token_nos_to_delete:
            # 튜플 리스트를 단순 ID 리스트로 변환
            ids_list = [token_no[0] for token_no in token_nos_to_delete]

            delete_count = (
                db.query(models.ComUserTokenAuth)
                .filter(models.ComUserTokenAuth.token_no.in_(ids_list))
                .delete(synchronize_session=False)
            )

            db.commit()
            logger.info(f"[TOKEN] Deleted {delete_count} old refresh tokens for user {user_no}")
        else:
            logger.debug(f"[TOKEN] No tokens to delete for user {user_no} (current count <= {limit})")

    except Exception as e:
        db.rollback()
        logger.exception(f"[TOKEN] Failed to prune refresh tokens for user {user_no}: {e}")
        raise
# ==============================
# 토큰 생성
# ==============================
def create_access_token(data: dict) -> str:
    """Access token 생성"""
    return _generate_jwt(data, TOKEN_CONFIG.ACCESS_TOKEN_SECRET_KEY, timedelta(minutes=TOKEN_CONFIG.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: dict, db: Session, user_agent: Optional[str]) -> str:
    """
    Refresh token 생성 및 DB에 저장.
    - user_no 필요
    - 기존 토큰이 limit 이상이면 오래된 토큰 삭제
    """
    user_no = data.get("user_no")
    if not user_no:
        raise ValueError("user_no is required in token data")

    try:
        # 오래된 토큰 자르기
        _prune_old_refresh_tokens(db, user_no)

        # JWT 생성
        encoded_jwt = _generate_jwt(data, TOKEN_CONFIG.REFRESH_TOKEN_SECRET_KEY, timedelta(days=TOKEN_CONFIG.REFRESH_TOKEN_EXPIRE_DAYS))

        new_token = models.ComUserTokenAuth(
            user_no=user_no,
            refresh_token=encoded_jwt,
            user_agent=(user_agent or "")[:512],
            created_at=datetime.utcnow(),
        )

        db.add(new_token)
        db.commit()
        # commit 후 id가 생성되어야 함
        logger.info(f"[TOKEN] Created refresh token ID={new_token.token_no} for user {user_no}")
        return encoded_jwt

    except Exception as e:
        # DB 작업 실패 시 롤백 & 로그
        try:
            db.rollback()
        except Exception:
            logger.exception("[TOKEN] rollback failed")
        logger.exception(f"[TOKEN] Refresh token creation failed for user {user_no}: {e}")
        raise


def create_token_pair(data: dict, db: Session, user_agent: Optional[str] = None) -> dict:
    """
    access / refresh 토큰 쌍 생성 (refresh는 DB에 저장됨)
    """
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data, db, user_agent)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": TOKEN_CONFIG.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ==============================
# 토큰 검증
# ==============================
def get_token_info(token: str, token_type: str):
    """
    만료되지 않은 토큰에 대해 payload 반환
    (만료시 jose.JWTError 또는 ExpiredSignatureError를 발생시킴)
    """
    secret = TOKEN_CONFIG.ACCESS_TOKEN_SECRET_KEY if token_type == "access" else TOKEN_CONFIG.REFRESH_TOKEN_SECRET_KEY
    return jwt.decode(token, secret, algorithms=[TOKEN_CONFIG.ALGORITHM])


def get_token_info_ignore_expiration(token: str, token_type: str):
    """
    만료 여부와 관계없이 토큰 payload 반환 (디버그/검증용)
    """
    secret = TOKEN_CONFIG.ACCESS_TOKEN_SECRET_KEY if token_type == "access" else TOKEN_CONFIG.REFRESH_TOKEN_SECRET_KEY
    try:
        return jwt.decode(token, secret, algorithms=[TOKEN_CONFIG.ALGORITHM], options={"verify_exp": False})
    except JWTError as e:
        # 호출측에서 HTTPException 으로 변환하여 처리하도록 함
        logger.exception("Invalid token structure in get_token_info_ignore_expiration")
        print("Invalid token structure in get_token_info_ignore_expiration")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token structure: {str(e)}")


def check_access_token(token: str, token_type: str = "access"):
    """
    토큰 유효성 검사 (예외 대신 검증결과 dict 반환)
    - 반환: {"valid": bool, "error": Optional[str], "payload": Optional[dict]}
    """
    print("Invalid token type", "payload")
    try:
        payload = get_token_info(token, token_type)
        # 토큰 타입을 payload에 포함시키는 정책이라면 확인
        if payload.get("type") and payload.get("type") != token_type:
            return {"valid": False, "error": "Invalid token type", "payload": None}

        exp = payload.get("exp")
        if exp is None:
            return {"valid": False, "error": "Token missing expiration", "payload": None}

        if datetime.utcnow().timestamp() > exp:
            # 만료된 토큰이라도 payload는 반환
            return {"valid": False, "error": "Access token expired", "payload": payload}

        return {"valid": True, "error": None, "payload": payload}
    except JWTError as e:
        logger.debug(f"Token decode error: {e}")
        return {"valid": False, "error": f"Invalid token: {str(e)}", "payload": None}


def verify_access_token(token: str, token_type: str = "access"):
    """
    토큰 검증 - 실패 시 HTTPException(401)을 던짐
    """
    result = check_access_token(token, token_type)
    if not result["valid"]:
        # result["error"]는 None이 아닐 것
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result["error"] or "Invalid token")
    return result["payload"]
