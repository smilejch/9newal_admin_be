from fastapi import APIRouter
from app.modules.purchase import models
from app.modules.purchase import schemas as purchase_schemas
from app.modules.purchase import service as purchase_service
from fastapi import APIRouter, Depends, Path, Request, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.common.schemas import request as common_schemas
from app.common.response import ApiResponse, PageResponse
from typing import Union

purchase_router = APIRouter()

# 로그인
@purchase_router.post("/orders/search")
def fetch_rocket_order_mst_list(
    filter: purchase_schemas.OrderMstFilterRequest,
    request: Request,
    db: Session = Depends(get_db),
    pagination: common_schemas.PaginationRequest = Depends()
) -> ApiResponse[PageResponse[purchase_schemas.OrderMstResponse]]:
    return purchase_service.fetch_order_mst_list(filter, request, pagination, db)


# 쉽먼트(센터) 조회
@purchase_router.get("/orders/{order_mst_no}/shipments")
def fetch_growth_shipment_mst(
    request: Request,
    order_mst_no: int = Path(...),
    db: Session = Depends(get_db)
) -> ApiResponse[Union[dict, None]]:
    return purchase_service.fetch_purchase_shipment_mst(request, order_mst_no, db)

# 구매정보 전체 조회
@purchase_router.get("/orders/{order_mst_no}/purchase")
def fetch_shipment_dtl_all_list(
    request: Request,
    order_mst_no: Union[str, int] = Path(...),
    db: Session = Depends(get_db),
    pagination: common_schemas.PaginationRequest = Depends()
) -> ApiResponse[Union[PageResponse[dict], None]]:
    return purchase_service.fetch_shipment_dtl_all_list(order_mst_no, request, pagination, db)


# 특정 구매정보 조회
@purchase_router.get("/shipments/{order_shipment_mst_no}/purchase")
def fetch_shipment_dtl_list(
    request: Request,
    order_shipment_mst_no: Union[str, int] = Path(...),
    db: Session = Depends(get_db),
    pagination: common_schemas.PaginationRequest = Depends()
) -> ApiResponse[Union[PageResponse[dict], None]]:
    return purchase_service.fetch_shipment_dtl_list(order_shipment_mst_no, request, pagination, db)


@purchase_router.get("/shipments/{shipment_mst_no}/estimate-products")
async def fetch_shipment_estimate_products(
        shipment_mst_no: int,
        request: Request,
        pagination: common_schemas.PaginationRequest = Depends(),
        db: Session = Depends(get_db)
):
    return purchase_service.fetch_shipment_estimate_product_list(shipment_mst_no, request, pagination, db)

@purchase_router.get("/shipments/{order_mst_no}/estimate-products-all")
async def fetch_shipment_estimate_products_all(
        order_mst_no: int,
        request: Request,
        pagination: common_schemas.PaginationRequest = Depends(),
        db: Session = Depends(get_db)
):
    return purchase_service.fetch_shipment_estimate_product_list_all(order_mst_no, request, pagination, db)

@purchase_router.get("/shipments/estimates/{order_mst_no}")
def fetch_estimate_mst_list(
    request: Request,
    order_mst_no: Union[str, int] = Path(..., description="발주서 번호"),
    pagination: common_schemas.PaginationRequest = Depends(),
    db: Session = Depends(get_db)
) -> ApiResponse[Union[PageResponse[dict], None]]:
    """견적서 목록 조회"""
    return purchase_service.fetch_estimate_mst_list(order_mst_no, pagination, request, db)

@purchase_router.get("/shipments/estimates/{order_shipment_estimate_no}/detail")
def fetch_estimate_dtl(
    request: Request,
    order_shipment_estimate_no: Union[str, int] = Path(..., description="견적서 번호"),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    """견적서 상세 조회"""
    return purchase_service.fetch_estimate_dtl(order_shipment_estimate_no, request, db)


@purchase_router.get("/shipments/estimates/{order_mst_no}/deposit-confirm")
def update_(
    request: Request,
    order_mst_no: Union[str, int] = Path(..., description="발주서 번호"),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return purchase_service.fetch_estimate_dtl(order_mst_no, request, db)


@purchase_router.put("/shipments/estimates/{order_shipment_estimate_no}/deposit-confirm")
async def confirm_estimate_deposit(
        order_shipment_estimate_no: int,
        request: Request,
        db: Session = Depends(get_db)
):
    return purchase_service.confirm_estimate_deposit(
        order_shipment_estimate_no=order_shipment_estimate_no,
        request=request,
        db=db
    )

@purchase_router.get("/orders/{order_mst_no}/shipments/download")
async def download_shipment_dtl_excel(
        order_mst_no: int,
        request: Request,
        db: Session = Depends(get_db)
):
    """Growth 쉽먼트 박스 구성 엑셀 다운로드"""
    return await purchase_service.download_shipment_dtl_excel(
        order_mst_no,
        request,
        db
    )

@purchase_router.get("/shipments/estimates/{order_mst_no}/download")
async def download_shipment_estimate_excel(
        order_mst_no: int,
        request: Request,
        db: Session = Depends(get_db)
):
    """Growth 쉽먼트 박스 구성 엑셀 다운로드"""
    return await purchase_service.download_shipment_estimate_excel(
        order_mst_no,
        request,
        db
    )

@purchase_router.get("/shipments/{order_mst_no}/estimate-products-all/download")
async def download_shipment_estimate_product_all_excel(
        order_mst_no: int,
        request: Request,
        db: Session = Depends(get_db)
):
    """Growth 쉽먼트 박스 구성 엑셀 다운로드"""
    return await purchase_service.download_shipment_estimate_product_all_excel(
        order_mst_no,
        request,
        db
    )

@purchase_router.post("/orders/{order_mst_no}/1688-tracking-number/upload")
async def upload_1688_tracking_number(
    request: Request,
    order_mst_no: Union[str, int] = Path(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return await purchase_service.upload_1688_tracking_number(order_mst_no, file, request, db)


@purchase_router.post("/shipments/cj-tracking-number/issue")
async def issue_cj_tracking_number(
        request: Request,
        Issue_tracking_number_request: purchase_schemas.IssueCjTackingNumberRequest,
        db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    """CJ 운송장 번호 발급"""
    return await purchase_service.issue_cj_tracking_number(
        Issue_tracking_number_request,
        request,
        db
    )

@purchase_router.post("/shipments/1688-order/create")
async def create_1688_order(
    request: Request,
    create_order_request: purchase_schemas.Create1688OrderRequest,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    """1688 실제 주문 생성 (DTL 번호 기준)"""
    return await purchase_service.create_1688_order(
        create_order_request,
        request,
        db
    )
