from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from decimal import Decimal

class ComCodeResponse(BaseModel):
    com_code: Optional[str] = None
    code_name: Optional[str] = None
    keyword1: Optional[str] = None
    keyword2: Optional[str] = None
    keyword3: Optional[str] = None

    class Config:
        from_attributes = True

class LinkedOptionsRequest(BaseModel):
    option_value: Optional[str] = None
    linked_option: Optional[str] = None
    linked_spec_id: Optional[str] = None
    linked_sku_id: Optional[int] = None
    linked_open_uid: Optional[str] = None

class ComHsCodeResponse(BaseModel):
    hs_code: str
    apply_start_date: date
    apply_end_date: Optional[date] = None
    item_name_kr: Optional[str] = None
    item_name_en: Optional[str] = None
    hs_content: Optional[str] = None
    ktsn_name: Optional[str] = None
    unit_price_qty: Optional[Decimal] = None
    unit_price_weight: Optional[Decimal] = None
    qty_unit_code: Optional[str] = None
    weight_unit_code: Optional[str] = None
    export_type_code: Optional[str] = None
    import_type_code: Optional[str] = None
    item_spec_name: Optional[str] = None
    required_spec_name: Optional[str] = None
    ref_spec_name: Optional[str] = None
    spec_description: Optional[str] = None
    spec_detail: Optional[str] = None
    unified_type_code: Optional[str] = None
    unified_type_name: Optional[str] = None

    class Config:
        from_attributes = True  # Pydantic v2

class AlibabaCreateOrderPreviewRequest(BaseModel):
    offerId: Optional[str] = None
    specId: Optional[str] = None
    quantity: Optional[str] = None
    openUid: Optional[str] = None

class AlibabaCreateOrderPreviewListRequest(BaseModel):
    requests: List[AlibabaCreateOrderPreviewRequest]


class CompanyUpdateRequest(BaseModel):
    business_registration_number: Optional[str] = None
    address: Optional[str] = None
    address_dtl: Optional[str] = None

class CompanyProfileResponse(BaseModel):
    company_name: Optional[str] = None
    coupang_vendor_id: Optional[str] = None
    business_registration_number: Optional[str] = None
    address: Optional[str] = None
    address_dtl: Optional[str] = None