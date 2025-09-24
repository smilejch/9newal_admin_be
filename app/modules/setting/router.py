# app/modules/setting/router.py
from fastapi import APIRouter, Depends, Path, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.common.response import ApiResponse, PageResponse
from app.common.schemas.request import PaginationRequest
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.setting.schemas import SkuBase, SkuFilterRequest
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

