from fastapi import APIRouter, Depends, Path, Request
from app.common.response import ApiResponse, PageResponse
from typing import Union
from app.modules.common import service as common_service
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.common import schemas as common_schemas

common_router = APIRouter()

@common_router.get("/products/{offer_id}/options")
async def fetch_alibaba_product_options(offer_id: Union[str, int] = Path(...),) -> ApiResponse[list]:
    return await common_service.fetch_alibaba_product_options(offer_id)


@common_router.get("/codes/{parent_com_code}")
async def fetch_common_codes(
    parent_com_code: str = Path(..., description="부모 코드 타입 "),
    db: Session = Depends(get_db)
) -> ApiResponse[list]:
    return await common_service.fetch_common_codes(parent_com_code, db)

@common_router.put("/products/{sku_no}/options")
async def update_linked_options_info(
        linked_options_request: common_schemas.LinkedOptionsRequest,
        request: Request,
        db: Session = Depends(get_db),
        sku_no: Union[str, int] = Path(...),
) -> ApiResponse[list]:
    return await common_service.update_linked_options_info(sku_no, linked_options_request, db, request)

# hs코드 불러오기
@common_router.get("/hs-codes")
def fetch_hs_codes(
        db: Session = Depends(get_db)
) -> ApiResponse[list]:
    return common_service.fetch_hs_codes(db)

@common_router.put("/company/profile")
def update_company_profile(company_request: common_schemas.CompanyUpdateRequest, request: Request, db: Session = Depends(get_db)):
    return common_service.update_company_profile(company_request, request, db)

@common_router.get("/company/profile")
def fetch_company_profile(request: Request, db: Session = Depends(get_db)):
    return common_service.fetch_company_profile(request, db)

# 회사 목록 조회
@common_router.get("/companies")
def fetch_company_list(
        db: Session = Depends(get_db)
) -> ApiResponse[list]:
    return common_service.fetch_company_list(db)