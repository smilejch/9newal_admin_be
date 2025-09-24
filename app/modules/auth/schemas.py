# app/modules/auth/schemas.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MenuResponse(BaseModel):
    menu_no: int
    parent_no: int
    menu_name: str
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    order_no: Optional[int] = None
    is_visible: Optional[int] = None


class MenuTreeResponse(BaseModel):
    menu_no: int
    parent_no: int
    menu_name: str
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    order_no: Optional[int] = None
    is_visible: Optional[int] = None
    children: List['MenuTreeResponse'] = []


class UserCreate(BaseModel):
    user_email: str
    user_id: str
    user_name: str
    user_password: str
    user_password_confirm: str
    company_name: str
    coupang_vendor_id: str
    contact: str


class UserOut(BaseModel):
    user_no: int
    user_id: str
    user_email: str
    user_name: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    user_id: str
    user_password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    menu: List[MenuTreeResponse]


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class SwitchCompanyRequest(BaseModel):
    switch_company_no: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    new_password_confirm: str

class ResetPasswordRequest(BaseModel):
    user_id: str
    email: str