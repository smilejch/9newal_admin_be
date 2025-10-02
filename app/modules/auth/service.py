from fastapi import Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    verify_password,
    hash_password,
    create_token_pair,
    get_token_info_ignore_expiration
)
from app.modules.auth import models as auth_models, schemas as auth_schemas
from app.core.dependencies import verify_access_token
from app.utils.cookie_util import set_refresh_token_cookie, delete_refresh_token_cookie
from app.utils.menu_util import build_menu_tree
from app.utils.token_util import delete_refresh_token_from_db
from app.utils import crypto_util
from app.utils import auth_util
from app.utils.auth_util import get_authenticated_user_no
from app.modules.common import service as common_service

def register_user(user_data: auth_schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. 패스워드 검증
    if len(user_data.user_password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다.")

    if user_data.user_password != user_data.user_password_confirm:
        raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다.")

    # 2. 이미 등록된 이메일 검사
    existing_user = db.query(auth_models.ComUser).filter(auth_models.ComUser.user_email == user_data.user_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

    # 3. 이미 등록된 사용자 ID 검사
    existing_user_id = db.query(auth_models.ComUser).filter(auth_models.ComUser.user_id == user_data.user_id).first()
    if existing_user_id:
        raise HTTPException(status_code=400, detail="이미 사용중인 아이디입니다.")

    # 4. 업체 중복 검사
    existing_company = db.query(auth_models.ComCompany).filter(auth_models.ComCompany.company_name == user_data.company_name).first()
    if existing_company:
        raise HTTPException(status_code=400, detail="이미 등록된 회사입니다. 직원 등록으로 이용해주세요.")

    # 5. 쿠팡 판매자코드 중복 검사
    if user_data.coupang_vendor_id:
        existing_vendor = db.query(auth_models.ComCompany).filter(
            auth_models.ComCompany.coupang_vendor_id == user_data.coupang_vendor_id).first()
        if existing_vendor:
            raise HTTPException(status_code=400, detail="이미 등록된 쿠팡 판매자코드입니다.")

    try:
        # 6. 회사 정보 먼저 생성
        new_company = auth_models.ComCompany(
            company_name=user_data.company_name,
            coupang_vendor_id=user_data.coupang_vendor_id,
            company_status_cd='PENDING'
        )
        db.add(new_company)
        db.flush()

        # 7. 개인정보 암호화
        encrypted_name = crypto_util.encrypt(user_data.user_name)
        encrypted_email = crypto_util.encrypt(user_data.user_email)
        encrypted_contact = crypto_util.encrypt(user_data.contact)

        # 8. 비밀번호 해싱 후 저장
        new_user = auth_models.ComUser(
            user_id=user_data.user_id,
            user_email=encrypted_email,
            user_password=hash_password(user_data.user_password),
            user_name=encrypted_name,
            contact=encrypted_contact,
            company_no=new_company.company_no,
            user_status_cd='PENDING',
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return auth_schemas.UserOut(
            user_no=new_user.user_no,
            user_id=new_user.user_id,
            user_email=user_data.user_email,
            user_name=user_data.user_name,
            created_at=new_user.created_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

def login_user(
        login_data: auth_schemas.LoginRequest,
        response: Response,
        request: Request,
        db: Session = Depends(get_db)
):
    # 사용자 조회
    user = db.query(auth_models.ComUser).filter(
        auth_models.ComUser.user_id == login_data.user_id
    ).first()

    # 관리자 권한 체크
    if user.user_role_cd != 'ADMIN':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자만 로그인할 수 있습니다."
        )

    if not user or not verify_password(login_data.user_password, user.user_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if user.user_status_cd == 'PENDING':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="계정이 아직 승인 대기중입니다. 관리자의 승인을 기다려주세요."
        )

    if user.user_status_cd == 'SUSPENDED':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="계정이 이용 중지되었습니다. 자세한 내용은 관리자에게 문의하세요."
        )

    if user.user_status_cd != 'ACTIVE':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"계정 상태를 확인하세요."
        )

    try:
        decrypted_user_name = crypto_util.decrypt(user.user_name) if user.user_name else ""
    except Exception as e:
        decrypted_user_name = "복호화 실패"

    main_company_info = None
    selected_company_no = user.company_no

    # JWT 페이로드의 정보로 새 액세스 토큰 생성
    token_data = {
        "user_no": user.user_no,
        "user_name": decrypted_user_name,
        "company_no": selected_company_no
    }

    user_agent = request.headers.get("user-agent")
    tokens = create_token_pair(data=token_data, db=db, user_agent=user_agent)

    # 리프레시 토큰을 HttpOnly 쿠키에 저장 (보안 강화)
    set_refresh_token_cookie(response=response, refresh_token=tokens["refresh_token"])

    # 사용자/회사 기준 메뉴 셋팅
    menus = build_menu_tree(db=db, user_no=user.user_no, company_no=selected_company_no)

    return {
        "access_token": tokens["access_token"],
        "token_type": tokens["token_type"],
        "menu": menus
    }


def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    쿠키의 JWT 리프레시 토큰으로 액세스 토큰 재발행
    """
    # 쿠키에서 리프레시 토큰 추출
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found in cookies2"
        )


    # DB에 refresh_token 존재 여부 먼저 확인 (user_no 기반)
    try:
        # 만료 여부 상관없이 payload 추출
        payload_precheck = get_token_info_ignore_expiration(refresh_token, "refresh")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token format"
        )

    user_no_precheck = payload_precheck.get("user_no")
    company_no = payload_precheck.get("company_no")

    if not user_no_precheck:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload"
        )

    db_token = db.query(auth_models.ComUserTokenAuth).filter(
        auth_models.ComUserTokenAuth.user_no == user_no_precheck,
        auth_models.ComUserTokenAuth.refresh_token == refresh_token
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found in DB"
        )

    # JWT 리프레시 토큰 검증 (자동으로 만료 체크됨)
    try:
        payload = verify_access_token(token=refresh_token, token_type="refresh")
    except HTTPException:

        # 리프레시 토큰이 만료되거나 유효하지 않은 경우 쿠키 삭제
        invalidate_refresh_token(refresh_token, response, db)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or invalid. Please login again."
        )

    # JWT 페이로드에서 사용자 정보 직접 추출
    user_no = payload.get("user_no")
    companies = payload.get("companies", [])

    if not user_no:
        # 유효하지 않은 페이로드일 경우에도 쿠키 삭제
        invalidate_refresh_token(refresh_token=refresh_token, response=response, db=db)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload"
        )

    # 사용자 존재 여부만 간단히 확인
    user = db.query(auth_models.ComUser).filter(
        auth_models.ComUser.user_no == user_no
    ).first()

    if not user:
        # 사용자가 존재하지 않을 경우에도 쿠키 삭제
        invalidate_refresh_token(refresh_token, response, db)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    main_company_info = db.query(auth_models.ComCompany).filter(
        auth_models.ComCompany.company_no == company_no
    ).first()

    try:
        decrypted_user_name = crypto_util.decrypt(user.user_name) if user.user_name else ""
    except Exception as e:
        decrypted_user_name = "복호화 실패"

    # JWT 페이로드의 정보로 새 액세스 토큰 생성
    token_data = {
        "user_no": user_no,
        "user_name": decrypted_user_name,
        "company_no": main_company_info.company_no,
        "company_name": main_company_info.company_name,
        "coupang_vendor_id": main_company_info.coupang_vendor_id,
        "companies": companies
    }

    user_agent = request.headers.get("user-agent")
    tokens = create_token_pair(data=token_data, db=db, user_agent=user_agent)

    # 한번 사용한 refresh_token 은 DB 에서 삭제 처리
    delete_refresh_token_from_db(refresh_token=refresh_token, db=db)

    # 새로운 리프레시 토큰을 HttpOnly 쿠키에 저장
    set_refresh_token_cookie(response, tokens["refresh_token"])

    # 사용자 정보 포함해서 반환
    user_out = auth_schemas.UserOut.from_orm(user)

    return {
        "access_token": tokens["access_token"],
        "token_type": tokens["token_type"],
        "expires_in": tokens["expires_in"],
        "user": user_out
    }


def logout_user(
        response: Response,
        request: Request,
        db: Session = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")

    # 리프레시 토큰 쿠키 삭제 및 db 삭제
    invalidate_refresh_token(refresh_token, response, db)

    return {"message": "Successfully logged out"}


def switch_company(
    response: Response,
    request: Request,
    switch_company_no: int,
    db: Session = Depends(get_db)
):
    # 리프레시 토큰 삭제
    refresh_token = request.cookies.get("refresh_token")
    invalidate_refresh_token(refresh_token, response, db)

    # 새로운 토큰 발급, 리프레시 토큰 발급
    payload = get_token_info_ignore_expiration(refresh_token, "refresh")
    main_company_info = db.query(auth_models.ComCompany).filter(
        auth_models.ComCompany.company_no == switch_company_no
    ).first()

    token_data = {
        "user_no": payload.get("user_no"),
        "user_name": payload.get("user_name"),
        "company_no": switch_company_no,
        "company_name": main_company_info.company_name,
        "coupang_vendor_id": main_company_info.coupang_vendor_id,
        "companies": payload.get("companies")
    }

    user_agent = request.headers.get("user-agent")
    tokens = create_token_pair(data=token_data, db=db, user_agent=user_agent)

    # 리프레시 토큰을 HttpOnly 쿠키에 저장 (보안 강화)
    set_refresh_token_cookie(response=response, refresh_token=tokens["refresh_token"])

    # 사용자/회사 기준 메뉴 셋팅
    menus = build_menu_tree(db=db, user_no=payload.get("user_no"), company_no=switch_company_no)

    return {
        "access_token": tokens["access_token"],
        "token_type": tokens["token_type"],
        "menu": menus
    }


# 토큰 삭제 처리
def invalidate_refresh_token(refresh_token, response, db):
    delete_refresh_token_cookie(response=response)
    delete_refresh_token_from_db(refresh_token=refresh_token, db=db)

# 패스워드변경
def change_password(password_data: auth_schemas.ChangePasswordRequest, request: Request, db: Session):
        user_no, company_no = get_authenticated_user_no(request)

        current_user = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_no == user_no
        ).first()

        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다."
            )

        # 3. 사용자 상태 확인
        if current_user.user_status_cd != 'ACTIVE':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="계정 상태를 확인하세요."
            )

        # 4. 새 비밀번호 확인
        if password_data.new_password != password_data.new_password_confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="새 비밀번호가 일치하지 않습니다."
            )

        # 5. 현재 비밀번호 검증
        if not verify_password(password_data.current_password, current_user.user_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 비밀번호가 올바르지 않습니다."
            )

        # 6. 현재 비밀번호와 새 비밀번호가 같은지 확인
        if password_data.current_password == password_data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="새 비밀번호는 현재 비밀번호와 달라야 합니다."
            )

        try:
            current_user.user_password = hash_password(password_data.new_password)
            db.commit()

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="비밀번호 변경 중 오류가 발생했습니다."
            )


async def reset_password(reset_data: auth_schemas.ResetPasswordRequest, db: Session):
    try:
        normalized_email = reset_data.email.strip().lower()
        user_id = reset_data.user_id.strip()

        target_user = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_id == user_id,
            auth_models.ComUser.user_status_cd == 'ACTIVE'
        ).first()

        if target_user and target_user.user_email:
            try:
                decrypted_email = crypto_util.decrypt(target_user.user_email)
                if decrypted_email.lower() == normalized_email:

                    temp_password = auth_util.generate_temporary_password()

                    try:
                        decrypted_name = crypto_util.decrypt(target_user.user_name) if target_user.user_name else "사용자"
                    except:
                        decrypted_name = "사용자"

                    target_user.user_password = hash_password(temp_password)
                    db.commit()

                    email_subject = "[9NEWALL] 임시 비밀번호 안내"
                    email_content = f"""
안녕하세요.
임시 비밀번호를 안내드립니다.
임시 비밀번호: {temp_password}
보안을 위해 로그인 후 반드시 비밀번호를 변경해주세요.
감사합니다.
"""
                    await common_service.send_mail(normalized_email, email_subject, email_content)
            except Exception:
                pass

        return {
            "message": "아이디와 이메일이 일치하면 임시 비밀번호를 전송했습니다."
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="비밀번호 재설정 중 오류가 발생했습니다."
        )