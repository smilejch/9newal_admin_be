# app/modules/setting/schemas.py
from pydantic import BaseModel
from typing import Optional, Union, List
from decimal import Decimal
from datetime import datetime


class SkuBase(BaseModel):
    """SKU 기본 스키마"""
    sku_no: Optional[Union[int,str]] = None
    sku_id: str
    exposure_id: Optional[str] = None
    bundle: Optional[Union[str, int]] = None
    sku_name: Optional[str] = None
    link: Optional[str] = None
    option_value: Optional[str] = None
    linked_option: Optional[str] = None
    barcode: Optional[str] = None
    multiple_value: Optional[int] = 1
    package_unit_quantity: Optional[str] = None
    cn_name: Optional[str] = None
    package_vinyl_spec_cd: Optional[str] = None
    package_vinyl_spec_name: Optional[str] = None
    en_name: Optional[str] = None
    hs_code: Optional[str] = None
    en_name_for_cn: Optional[str] = None
    hs_code_cn: Optional[str] = None
    fta_cd: Optional[str] = None
    fta_name: Optional[str] = None
    material: Optional[str] = None
    length_mm: Optional[Decimal] = None
    width_mm: Optional[Decimal] = None
    height_mm: Optional[Decimal] = None
    weight_g: Optional[Decimal] = None
    delivery_status_cd: Optional[str] = None
    delivery_status_name: Optional[str] = None
    sale_price: Optional[Decimal] = None
    cost_yuan: Optional[Decimal] = None
    cost_krw: Optional[Decimal] = None
    supply_price: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    image_path: Optional[str] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    company_no: Optional[int] = None
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


class SkuFilterRequest(BaseModel):
    sku_id: Optional[str] = None
    exposure_id: Optional[str] = None
    sku_name: Optional[str] = None
    barcode: Optional[str] = None
    company_no: Optional[List[int]] = None  # 회사 번호 배열 추가


# schemas.py에 스키마 정의
class CenterBase(BaseModel):
    center_no: int
    company_no: int
    center_initial: str
    center_name: str

    # ... 다른 필드들

    class Config:
        from_attributes = True  # SQLAlchemy 모델에서 변환 가능


class UserBase(BaseModel):
    """사용자 기본 스키마"""
    user_no: Optional[Union[int, str]] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_password: Optional[str] = None  # 생성/수정 시에만 사용
    user_name: Optional[str] = None
    contact: Optional[str] = None
    user_status_cd: Optional[str] = None
    user_status_name: Optional[str] = None
    user_role_cd: Optional[str] = None
    user_role_name: Optional[str] = None
    approval_yn: Optional[int] = None
    company_no: Optional[int] = None
    company_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserFilterRequest(BaseModel):
    """사용자 필터 요청"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    contact: Optional[str] = None
    user_status_cd: Optional[str] = None
    company_no: Optional[List[int]] = None

class CompanyBase(BaseModel):
    """회사 기본 스키마"""
    company_no: Optional[Union[int, str]] = None
    company_name: Optional[str] = None
    coupang_vendor_id: Optional[str] = None
    business_registration_number: Optional[str] = None
    company_status_cd: Optional[str] = None
    company_status_name: Optional[str] = None  # 조회 시에만 사용
    address: Optional[str] = None
    address_dtl: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompanyFilterRequest(BaseModel):
    """회사 필터 요청"""
    company_name: Optional[str] = None
    coupang_vendor_id: Optional[str] = None
    business_registration_number: Optional[str] = None
    address: Optional[str] = None
    company_status_cd: Optional[str] = None
