from fastapi import APIRouter
from app.modules.purchase import models
from app.modules.purchase import schemas as purchase_schemas
from app.modules.purchase import service as purchase_service
from fastapi import APIRouter, Depends, Path, Request, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.common.schemas import request as common_schemas
from app.common.response import ApiResponse, PageResponse

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
