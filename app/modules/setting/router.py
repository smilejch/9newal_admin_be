# app/modules/setting/router.py
from fastapi import APIRouter, Depends, Path, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.common.response import ApiResponse, PageResponse
from app.common.schemas.request import PaginationRequest
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.setting.schemas import SkuBase, SkuFilterRequest, UserBase, UserFilterRequest, CompanyFilterRequest, CompanyBase
from app.modules.setting import service as setting_service
from typing import Union

setting_router = APIRouter()


# SKU 등록
@setting_router.post("/skus")
def create_sku(
    sku_info: SkuBase,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    return setting_service.create_sku(sku_info, request, db)


# SKU 목록 조회
@setting_router.post("/skus/search")
def fetch_sku_list(
    request: Request,
    filter: SkuFilterRequest,
    db: Session = Depends(get_db),
    pagination: PaginationRequest = Depends()
) -> ApiResponse[PageResponse[SkuBase]]:
    return setting_service.fetch_sku_list(request, filter, db, pagination)


# SKU 상세 조회
@setting_router.get("/skus/{sku_no}")
def fetch_sku(
    sku_no: Union[str, int] = Path(...),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.fetch_sku(sku_no, db)


# SKU 수정
@setting_router.put("/skus/{sku_no}")
def update_sku(
    sku_info: SkuBase,
    request: Request,
    sku_no: Union[str, int] = Path(...),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.update_sku(sku_info, sku_no, request, db)


# SKU 삭제
@setting_router.delete("/skus/{sku_no}")
def delete_sku(
    sku_no: Union[str, int] = Path(...),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.delete_sku(sku_no, db)


# SKU 엑셀 템플릿 다운로드
@setting_router.get("/skus/template/download")
def download_sku_template(
        request: Request,
        db: Session = Depends(get_db)
) -> FileResponse:
    return setting_service.download_sku_template(request, db)


# SKU 엑셀 업로드
@setting_router.post("/skus/template/upload")
async def upload_sku_excel(
    request: Request,
    file: UploadFile = File(..., description="업로드할 엑셀 파일"),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return await setting_service.upload_sku_excel(file, request, db)


# SKU 이미지 업로드
@setting_router.post("/skus/{sku_no}/images")
async def upload_sku_image(
    sku_no: int = Path(..., description="SKU 번호"),
    request: Request = None,
    file: UploadFile = File(..., description="업로드할 이미지 파일"),
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return await setting_service.upload_sku_image(sku_no, file, request, db)


@setting_router.get("/skus/{sku_no}/images")
def fetch_sku_image(
    request: Request,
    sku_no: int = Path(..., description="SKU 번호"),
    db: Session = Depends(get_db)
):
    return setting_service.fetch_sku_image(sku_no, request, db)


@setting_router.delete("/skus/{sku_no}/images")
def delete_sku_image(
    request: Request,
    sku_no: int = Path(..., description="SKU 번호"),
    db: Session = Depends(get_db)
):
    return setting_service.delete_sku_image(sku_no, request, db)


# SKU 상세 조회
@setting_router.get("/centers")
def fetch_center_list(
    request:Request,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.fetch_center_list(request, db)

# 사용자 생성
@setting_router.post("/users")
def create_user(
    user_info: UserBase,
    request: Request,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.create_user(user_info, request, db)


# 사용자 목록 조회 (페이지네이션 및 필터링)
@setting_router.post("/users/search")
def fetch_user_list(
    filter: UserFilterRequest,
    db: Session = Depends(get_db),
    pagination: PaginationRequest = Depends()
) -> ApiResponse[PageResponse[UserBase]]:
    return setting_service.fetch_user_list(filter, db, pagination)


# 사용자 상세 조회
@setting_router.get("/users/{user_no}")
def fetch_user(
    user_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.fetch_user(user_no, request, db)


# 사용자 수정
@setting_router.put("/users/{user_no}")
def update_user(
    user_info: UserBase,
    user_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.update_user(user_info, user_no, request, db)


# 사용자 삭제
@setting_router.delete("/users/{user_no}")
def delete_user(
    user_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.delete_user(user_no, request, db)

# 회사 생성
@setting_router.post("/companies")
def create_company(
    company_info: CompanyBase,
    request: Request,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.create_company(company_info, request, db)


# 회사 목록 조회 (페이지네이션 및 필터링)
@setting_router.post("/companies/search")
def fetch_company_list(
    request: Request,
    filter: CompanyFilterRequest,
    db: Session = Depends(get_db),
    pagination: PaginationRequest = Depends()
) -> ApiResponse[PageResponse[CompanyBase]]:
    return setting_service.fetch_company_list(request, filter, db, pagination)


# 회사 상세 조회
@setting_router.get("/companies/{company_no}")
def fetch_company(
    company_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.fetch_company(company_no, request, db)


# 회사 수정
@setting_router.put("/companies/{company_no}")
def update_company(
    company_info: CompanyBase,
    company_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.update_company(company_info, company_no, request, db)


# 회사 삭제
@setting_router.delete("/companies/{company_no}")
def delete_company(
    company_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return setting_service.delete_company(company_no, request, db)

# 사용자 승인
@setting_router.put("/users/{user_no}/approve")
async def approve_user(
    user_no: int = Path(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    return await setting_service.approve_user(user_no, request, db)