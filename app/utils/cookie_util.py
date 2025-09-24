# utils/cookie_utils.py
from fastapi import Response
from app.core.config import TOKEN_CONFIG

def set_refresh_token_cookie(response: Response, refresh_token: str):
    """리프레시 토큰을 쿠키에 설정"""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=TOKEN_CONFIG.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=False,
        samesite="strict",
        path="/",
        domain=None
    )


def delete_refresh_token_cookie(response: Response):
    """리프레시 토큰 쿠키 삭제"""
    response.delete_cookie(
        key="refresh_token",
        path="/",
        domain=None,
        secure=False,
        httponly=True,
        samesite="strict"
    )


def manage_refresh_token_cookie(response: Response, action: str, refresh_token: str = None):
    """통합 쿠키 관리 함수 (기존 호환성)"""
    if action == "set" and refresh_token:
        set_refresh_token_cookie(response, refresh_token)
    elif action == "delete":
        delete_refresh_token_cookie(response)
