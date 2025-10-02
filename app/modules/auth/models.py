# app/modules/auth/models.py 수정 예시
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, func, Boolean
from app.core.database import Base
from sqlalchemy.orm import relationship

# 🔹 사용자(User) 테이블
class ComUser(Base):
    __tablename__ = "COM_USER"

    user_no = Column(Integer, primary_key=True, autoincrement=True, comment="사용자 인덱스")
    user_id = Column(String(150), unique=True, index=True, comment="사용자 로그인 ID")
    company_no = Column(Integer, comment="회사 인덱스 (PK)")
    user_email = Column(String(255), unique=True, index=True, comment="사용자 이메일")
    user_password = Column(String(255), comment="비밀번호 (해시값)")
    user_name = Column(String(100), comment="사용자 이름")
    contact = Column(String(11), comment="연락처")
    user_status_cd = Column(String(30), comment="사용자 상태")
    user_role_cd = Column(String(50), comment="관리자, 사용자 권한 타입")
    approval_yn = Column(Integer, default=0, comment="승인여부 (0: 미승인, 1: 승인)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="수정일시")


# 🔹 회사(Company) 테이블
class ComCompany(Base):
    __tablename__ = "COM_COMPANY"

    company_no = Column(Integer, primary_key=True, autoincrement=True, comment="회사 인덱스 (PK)")
    company_name = Column(String(200), unique=True, index=True, comment="회사 이름")
    coupang_vendor_id = Column(String(9), comment="쿠팡 벤더아이디")
    business_registration_number = Column(String(10), comment="사업자 번호")
    company_status_cd = Column(String(30), comment="회사 상태")
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    address = Column(String(300), comment="주소")
    address_dtl = Column(String(200), comment="상세주소")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="수정일시")

# 사용자 별 토큰 관리 테이블
class ComUserTokenAuth(Base):
    __tablename__ = "COM_USER_TOKEN_AUTH"

    token_no = Column(Integer, primary_key=True, autoincrement=True, comment="토큰 No")
    user_no = Column(String(150), comment="사용자 No")
    user_agent = Column(String(250), comment="사용자 접속 User-agent")
    refresh_token = Column(String(500), comment="사용자 리프레시 토큰")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")


class AdminComUserMenu(Base):
    __tablename__ = "ADMIN_COM_USER_MENU"

    user_menu_no = Column(Integer, primary_key=True, autoincrement=True, comment="사용자별 메뉴권한 No")
    user_no = Column(Integer, comment="사용자 No")
    menu_no = Column(Integer, comment="메뉴 No")
    company_no = Column(Integer, comment="회사 No")
    created_at = Column(Integer, server_default=func.now(), comment="생성일시")

# 메뉴(Menu) 테이블
class AdminComMenu(Base):
    __tablename__ = "ADMIN_COM_MENU"

    menu_no = Column(Integer, primary_key=True, autoincrement=True, comment="메뉴 No")
    menu_name = Column(String(100), nullable=False, comment="메뉴 이름 (화면에 표시될 이름)")
    path = Column(String(255), nullable=False, comment="Vue 라우터 경로 (예: /dashboard)")
    component = Column(String(255), nullable=True, comment="Vue 컴포넌트 경로 (예: @/views/Dashboard.vue)")
    icon = Column(String(100), nullable=True, comment="아이콘 이름 (material-icons 또는 기타)")
    order_no = Column(Integer, nullable=True, default=0, comment="정렬 순서")
    is_visible = Column(Boolean, default=True, comment="메뉴 노출 여부")
    parent_no = Column(Integer, nullable=True, comment="상위 메뉴 No (자기참조)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="수정일시")


class ComMenu(Base):
    __tablename__ = "COM_MENU"

    menu_no = Column(Integer, primary_key=True, autoincrement=True, comment="메뉴 No")
    menu_name = Column(String(100), nullable=False, comment="메뉴 이름 (화면에 표시될 이름)")
    path = Column(String(255), nullable=False, comment="Vue 라우터 경로 (예: /dashboard)")
    component = Column(String(255), nullable=True, comment="Vue 컴포넌트 경로 (예: @/views/Dashboard.vue)")
    icon = Column(String(100), nullable=True, comment="아이콘 이름 (material-icons 또는 기타)")
    order_no = Column(Integer, nullable=True, default=0, comment="정렬 순서")
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    is_visible = Column(Boolean, default=True, comment="메뉴 노출 여부")
    basic_yn = Column(Integer, default=0, comment="기본메뉴 여부(0: 기본메뉴 아님, 1: 기본메뉴)")
    parent_no = Column(Integer, nullable=True, comment="상위 메뉴 No (자기참조)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="수정일시")


class ComUserMenu(Base):
    __tablename__ = "COM_USER_MENU"

    user_menu_no = Column(Integer, primary_key=True, autoincrement=True, comment="사용자별 메뉴권한 No")
    user_no = Column(Integer, comment="사용자 No")
    menu_no = Column(Integer, comment="메뉴 No")
    company_no = Column(Integer, comment="회사 No")
    created_at = Column(Integer, server_default=func.now(), comment="생성일시")

class ComUserCompany(Base):
    __tablename__ = "COM_USER_COMPANY"

    user_no = Column(Integer, primary_key=True, comment="사용자 No")
    company_no = Column(Integer, primary_key=True, comment="회사 No")
    created_at = Column(Integer, server_default=func.now(), comment="생성일시")