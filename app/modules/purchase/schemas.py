from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from typing import List

class GrowthOrderMstFilterRequest(BaseModel):
    order_date_start: Optional[str] = None
    order_date_end: Optional[str] = None
    order_memo: Optional[str] = None
    order_mst_status_cd: Optional[str] = None
    query: Optional[str] = None

class GrowthOrderMstResponse(BaseModel):
    order_mst_no: Optional[int] = None
    company_no: Optional[int] = None
    order_date: Optional[str] = None
    order_memo: Optional[str] = None
    unconfirm_count: Optional[int] = None
    confirm_count: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None


class GrowthOrderMstCreateRequest(BaseModel):
    order_date: Optional[str] = None
    order_memo: Optional[str] = None


class OrderMstResponse(BaseModel):
    order_mst_no: Optional[int] = None
    company_no: Optional[int] = None
    order_date: Optional[str] = None
    order_memo: Optional[str] = None
    platform_type_cd: Optional[str] = None
    platform_type_name: Optional[str] = None
    order_mst_status_cd: Optional[str] = None
    order_mst_status_name: Optional[str] = None
    company_name: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderMstFilterRequest(BaseModel):
    order_date_start: Optional[str] = None
    order_date_end: Optional[str] = None
    order_memo: Optional[str] = None
    order_mst_status_cd: Optional[str] = None
    query: Optional[str] = None

class PackingItemRequest(BaseModel):
    """포장 아이템 요청 스키마"""
    order_shipment_dtl_no: int
    order_number: str
    sku_id: str
    sku_barcode: Optional[str] = None
    sku_name: str
    packing_quantity: int

class ShipmentMstStatusRequest(BaseModel):
    status: str

    class Config:
        from_attributes = True


class PackingBoxRequest(BaseModel):
    """포장 박스 요청 스키마"""
    size: str  # "small", "medium", "large"
    sizeName: str  # "소형", "중형", "대형"
    sizeNumber: int  # 1, 2, 3, ...
    displayName: str  # "중형박스1"
    items: List[PackingItemRequest]


class ShipmentPackingRequest(BaseModel):
    """쉽먼트 포장 생성 요청 스키마"""
    boxes: List[PackingBoxRequest]


class EstimateGenerateRequest(BaseModel):
    shipmentMstNos: List[int]

class ProductEstimateRequest(BaseModel):
    order_shipment_mst_no: int
    order_shipment_dtl_no: int
    center_no: str
    center_name: str
    sku_name: str
    bundle: Optional[str]
    quantity: int
    sku_id: str
    unit_price: float
    product_amount: float
    package_vinyl_spec_cd: Optional[str] = None
    package_vinyl_spec_name: Optional[str] = None
    package_amount: float
    total_amount: float

class ProductEstimateFailRequest(BaseModel):
    order_shipment_mst_no: int
    order_shipment_dtl_no: int
    center_no: str
    center_name: str
    sku_name: str
    bundle: Optional[str] = None
    quantity: int
    sku_id: str
    unit_price: float
    product_amount: float
    package_vinyl_spec_cd: Optional[str] = None
    package_vinyl_spec_name: Optional[str] = None
    package_amount: float
    total_amount: float
    error_message: str

class BoxEstimateRequest(BaseModel):
    center_no: int
    center_name: str
    package_box_spec_cd: str
    package_box_spec_name: str
    quantity: int
    unit_price: float
    amount: float

class TotalEstimateRequest(BaseModel):
    product_total_amount: float
    vinyl_total_amount: float
    box_total_amount: float
    grand_total_amount: float

class PurchaseRequestSubmit(BaseModel):
    order_mst_no: int
    product_estimates: List[ProductEstimateRequest]
    product_estimates_fail: List[ProductEstimateFailRequest]
    box_estimates: List[BoxEstimateRequest]
    total_estimates: TotalEstimateRequest

class IssueCjTackingNumberRequest(BaseModel):
    order_shipment_packing_mst_nos: List[int]

class Create1688OrderRequest(BaseModel):
    order_shipment_dtl_nos: List[int]  # 쉽먼트 DTL 번호 리스트
    message: Optional[str] = None  # 구매자 메시지


class CreatePaymentLinkRequest(BaseModel):
    """결제 링크 생성 요청"""
    order_shipment_dtl_nos: List[int]