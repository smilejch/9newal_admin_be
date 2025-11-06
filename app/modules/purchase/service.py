from app.modules.purchase import schemas as growth_schemas
from fastapi import Depends, Request, UploadFile, status, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from sqlalchemy import and_, func
from app.common import response as common_response
from typing import Union, List
from app.modules.purchase import models as purchase_models
from app.modules.setting import models as set_models
from sqlalchemy.orm import aliased
from app.modules.auth import models as auth_models
from app.modules.common import models as common_models
from app.common.schemas import request as common_schemas
from app.common.response import ApiResponse, PageResponse, ResponseBuilder
from app.utils.auth_util import get_authenticated_user_no
from app.utils import com_code_util, file_util
from datetime import timedelta
from app.utils import alibaba_1688_util
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from decimal import Decimal
from collections import defaultdict
from app.modules.common import schemas as module_common_schemas

def fetch_order_mst_list(
    filter: growth_schemas.OrderMstFilterRequest,
    request: Request,
    pagination: common_schemas.PaginationRequest = Depends(),
    db: Session = Depends(get_db)
) -> ApiResponse[Union[PageResponse[growth_schemas.OrderMstResponse], None]]:

    ComCode = common_models.ComCode
    ComCompany = auth_models.ComCompany

    # ComCode를 두 개의 별칭으로 생성
    ComCodePlatform = aliased(ComCode)  # platform_type용
    ComCodeStatus = aliased(ComCode)  # order_mst_status용

    query = (
        db.query(
            purchase_models.OrderMst,
            ComCodePlatform.code_name.label("platform_type_name"),
            ComCodeStatus.code_name.label("order_mst_status_name"),
            ComCompany.company_name.label("company_name")
        ).join(
            ComCodePlatform,
            purchase_models.OrderMst.platform_type_cd == ComCodePlatform.com_code
        ).join(
            ComCodeStatus,
            purchase_models.OrderMst.order_mst_status_cd == ComCodeStatus.com_code
        ).join(
            ComCompany,
            purchase_models.OrderMst.company_no == ComCompany.company_no
        ).filter(
            ComCodePlatform.parent_com_code == 'PLATFORM_TYPE_CD',
            ComCodePlatform.use_yn == 1,
            ComCodePlatform.del_yn == 0,
            ComCodeStatus.parent_com_code == 'ORDER_MST_STATUS_CD',
            ComCodeStatus.use_yn == 1,
            ComCodeStatus.del_yn == 0,
            purchase_models.OrderMst.del_yn == 0
        )
    )

    # 필터 조건 수정 - 빈 문자열 체크 추가
    if filter.order_memo and filter.order_memo.strip():
        query = query.filter(purchase_models.OrderMst.order_memo.like(f"%{filter.order_memo.strip()}%"))

    if filter.order_mst_status_cd and filter.order_mst_status_cd.strip():
        query = query.filter(purchase_models.OrderMst.order_mst_status_cd == filter.order_mst_status_cd.strip())

    # 날짜 필터링 로직 수정
    if filter.order_date_start and filter.order_date_start.strip():
        start_date = filter.order_date_start.strip()
        if filter.order_date_end and filter.order_date_end.strip():
            # 시작일과 종료일이 모두 있는 경우
            end_date = filter.order_date_end.strip()
            query = query.filter(
                purchase_models.OrderMst.order_date.between(start_date, end_date)
            )
        else:
            # 시작일만 있는 경우 - 시작일 이후 데이터
            query = query.filter(
                purchase_models.OrderMst.order_date >= start_date
            )
    elif filter.order_date_end and filter.order_date_end.strip():
        # 종료일만 있는 경우 - 종료일 이전 데이터
        end_date = filter.order_date_end.strip()
        query = query.filter(
            purchase_models.OrderMst.order_date <= end_date
        )

    query = query.order_by(purchase_models.OrderMst.updated_at.desc())

    # 전체 개수
    total_elements = query.count()

    # 페이징
    offset = (pagination.page - 1) * pagination.size
    growth_orders = query.offset(offset).limit(pagination.size).all()

    growth_order_list = []

    for order, platform_type_name, order_mst_status_name, company_name in growth_orders:
        order_data = growth_schemas.OrderMstResponse.from_orm(order)
        order_data.platform_type_name = platform_type_name
        order_data.order_mst_status_name = order_mst_status_name
        order_data.company_name = company_name
        growth_order_list.append(order_data)

    return ResponseBuilder.paged_success(
        content=growth_order_list,
        page=pagination.page,
        size=pagination.size,
        total_elements=total_elements
    )

