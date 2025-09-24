# app/modules/auth/router.py
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth import schemas
from app.modules.auth import service as auth_service


auth_router = APIRouter()


# 로그인
@auth_router.post("/login", response_model=schemas.LoginResponse)
def login(
        login_data: schemas.LoginRequest,
        response: Response,
        request: Request,
        db: Session = Depends(get_db)
):
    return auth_service.login_user(login_data, response, request, db)


# 회사 변경
@auth_router.post("/switch-company", response_model=schemas.LoginResponse)
def switch(
        response: Response,
        request: Request,
        switch_company_info: schemas.SwitchCompanyRequest,
        db: Session = Depends(get_db)
):
    return auth_service.switch_company(response, request, switch_company_info.switch_company_no, db)


# 리프레시 토큰
@auth_router.post("/refresh", response_model=schemas.RefreshTokenResponse)
def refresh(
        request: Request,
        response: Response,
        db: Session = Depends(get_db)
):
    return auth_service.refresh_token(request, response, db)


@auth_router.post("/logout")
def logout(
        response: Response,
        request: Request,
        db: Session = Depends(get_db)
):
    return auth_service.logout_user(response, request, db)



# 패스워드 변경
@auth_router.post("/change-password")
def change_password(
        password_data: schemas.ChangePasswordRequest,
        request: Request,
        db: Session = Depends(get_db)
):
    return auth_service.change_password(password_data, request, db)


#패스워드 리셋
@auth_router.post("/reset-password")
async def reset_password(
    email_data: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    return await auth_service.reset_password(email_data, db)
