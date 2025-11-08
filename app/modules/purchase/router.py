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
async def get_shipment_estimate_products(
        shipment_mst_no: int,
        request: Request,
        pagination: common_schemas.PaginationRequest = Depends(),
        db: Session = Depends(get_db)
):
    return purchase_service.fetch_shipment_estimate_product_list(shipment_mst_no, request, pagination, db)

