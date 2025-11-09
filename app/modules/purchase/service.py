from app.modules.purchase import schemas as purchase_schemas
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from sqlalchemy import and_
from app.common import response as common_response
from typing import Union, List
from app.modules.purchase import models as purchase_models
from app.modules.setting import models as set_models
from sqlalchemy.orm import aliased
from app.modules.auth import models as auth_models
from app.modules.common import models as common_models
from app.common.schemas import request as common_schemas
from app.common.response import ApiResponse, PageResponse, ResponseBuilder
from app.utils import com_code_util

def fetch_order_mst_list(
    filter: purchase_schemas.OrderMstFilterRequest,
    request: Request,
    pagination: common_schemas.PaginationRequest = Depends(),
    db: Session = Depends(get_db)
) -> ApiResponse[Union[PageResponse[purchase_schemas.OrderMstResponse], None]]:

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
    orders = query.offset(offset).limit(pagination.size).all()

    order_list = []

    for order, platform_type_name, order_mst_status_name, company_name in orders:
        order_data = purchase_schemas.OrderMstResponse.from_orm(order)
        order_data.platform_type_name = platform_type_name
        order_data.order_mst_status_name = order_mst_status_name
        order_data.company_name = company_name
        order_list.append(order_data)

    return ResponseBuilder.paged_success(
        content=order_list,
        page=pagination.page,
        size=pagination.size,
        total_elements=total_elements
    )

def fetch_purchase_shipment_mst(
        request: Request,
        order_mst_no: int,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    try:

        shipment_mst_list = db.query(
            purchase_models.OrderShipmentMst
        ).filter(
            purchase_models.OrderShipmentMst.order_mst_no == order_mst_no,
            purchase_models.OrderShipmentMst.del_yn == 0
        ).order_by(
            purchase_models.OrderShipmentMst.estimated_yn.desc()
        ).all()
        # tabs 리스트를 for 루프 밖에서 초기화
        tabs = []

        for shipment_mst in shipment_mst_list:
            # 플랫폼 타입에 따른 구분
            if shipment_mst.platform_type_cd == "GROWTH":
                sub_label = shipment_mst.inbound_no
            else:
                sub_label = shipment_mst.edd

            tab = {
                "order_shipment_mst_no": shipment_mst.order_shipment_mst_no,
                "order_mst_no": shipment_mst.order_mst_no,
                "center_no": shipment_mst.center_no,
                "label": f"{shipment_mst.display_center_name}({sub_label})",
                "estimated_yn": shipment_mst.estimated_yn,
                "status": shipment_mst.order_shipment_mst_status_cd
            }
            tabs.append(tab)

        # data 변수를 for 루프 밖에서 정의
        data = {
            "tabs": tabs,
            "total_count": len(tabs),
            "order_mst_no": order_mst_no
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message=f"쉽먼트 목록이 정상적으로 출력되었습니다. (총 {len(tabs)}건)"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"쉽먼트 목록 출력 중 오류가 발생했습니다: {str(e)}"
        )


def fetch_shipment_dtl_list(
        order_shipment_mst_no: Union[str, int],
        request: Request,
        pagination: common_schemas.PaginationRequest,
        db: Session
) -> common_response.ApiResponse[Union[PageResponse[dict], None]]:
    """쉽먼트 마스터 번호로 특정 쉽먼트 DTL 조회 (MST, PACKING_DTL 정보 포함)"""
    try:
        # 쉽먼트 마스터 존재 확인
        existing_shipment_mst = db.query(purchase_models.OrderShipmentMst).filter(
            purchase_models.OrderShipmentMst.order_shipment_mst_no == order_shipment_mst_no,
            purchase_models.OrderShipmentMst.del_yn == 0
        ).first()

        if not existing_shipment_mst:
            raise HTTPException(
                status_code=400,
                detail="해당 쉽먼트를 찾을 수 없습니다.",
            )

        # center_name 서브쿼리
        center_subquery = db.query(set_models.SetCenter.center_name).filter(
            set_models.SetCenter.center_no == purchase_models.OrderShipmentMst.center_no,
            set_models.SetCenter.del_yn == 0
        ).scalar_subquery()

        # MST, DTL, PACKING_DTL, PACKING_MST LEFT OUTER JOIN 쿼리 구성
        query = db.query(
            purchase_models.OrderShipmentMst,
            purchase_models.OrderShipmentDtl,
            purchase_models.OrderShipmentPackingDtl,
            purchase_models.OrderShipmentPackingMst,
            center_subquery.label("center_name")
        ).join(
            purchase_models.OrderShipmentDtl,
            purchase_models.OrderShipmentMst.order_shipment_mst_no == purchase_models.OrderShipmentDtl.order_shipment_mst_no
        ).outerjoin(
            purchase_models.OrderShipmentPackingDtl,
            and_(
                purchase_models.OrderShipmentDtl.order_shipment_dtl_no == purchase_models.OrderShipmentPackingDtl.order_shipment_dtl_no,
                purchase_models.OrderShipmentPackingDtl.del_yn == 0  # JOIN 조건에 del_yn 포함
            )
        ).outerjoin(
            purchase_models.OrderShipmentPackingMst,
            and_(
                purchase_models.OrderShipmentPackingDtl.order_shipment_packing_mst_no == purchase_models.OrderShipmentPackingMst.order_shipment_packing_mst_no,
                purchase_models.OrderShipmentPackingMst.del_yn == 0  # JOIN 조건에 del_yn 포함
            )
        ).filter(
            purchase_models.OrderShipmentMst.order_shipment_mst_no == order_shipment_mst_no,
            purchase_models.OrderShipmentMst.del_yn == 0,
            purchase_models.OrderShipmentDtl.del_yn == 0
            # PACKING_DTL 필터 조건은 JOIN 조건으로 이동하여 LEFT JOIN이 제대로 동작하도록 함
        ).order_by(
            purchase_models.OrderShipmentDtl.created_at.desc(),
            purchase_models.OrderShipmentPackingDtl.created_at.desc()
        )

        # 전체 개수
        total_elements = query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 결과 데이터 변환
        dtl_data_list = []
        for mst, dtl, packing_dtl, packing_mst, center_name in results:
            combined_data = {
                # MST 정보
                "order_shipment_mst_no": mst.order_shipment_mst_no,
                "order_mst_no": mst.order_mst_no,
                "center_no": mst.center_no,
                "center_name": center_name,
                "edd": mst.edd,
                "order_shipment_mst_status_cd": mst.order_shipment_mst_status_cd,
                "mst_created_at": mst.created_at,
                "mst_created_by": mst.created_by,
                "mst_updated_at": mst.updated_at,
                "mst_updated_by": mst.updated_by,

                # DTL 정보
                "order_shipment_dtl_no": dtl.order_shipment_dtl_no,
                "order_shipment_packing_mst_no": dtl.order_shipment_packing_mst_no,
                "company_no": dtl.company_no,
                "order_number": dtl.order_number,
                "transport_type": dtl.transport_type,
                "sku_id": dtl.sku_id,
                "sku_barcode": dtl.sku_barcode,
                "sku_name": dtl.sku_name,
                "confirmed_quantity": dtl.confirmed_quantity,
                "shipped_quantity": dtl.shipped_quantity,
                "link": dtl.link,
                "option_type": dtl.option_type,
                "option_value": dtl.option_value,
                "linked_option": dtl.linked_option,
                "linked_spec_id": dtl.linked_spec_id,
                "linked_sku_id": dtl.linked_sku_id,
                "linked_open_uid": dtl.linked_open_uid,
                "multiple_value": dtl.multiple_value,
                "length_mm": float(dtl.length_mm) if dtl.length_mm else None,
                "width_mm": float(dtl.width_mm) if dtl.width_mm else None,
                "height_mm": float(dtl.height_mm) if dtl.height_mm else None,
                "weight_g": float(dtl.weight_g) if dtl.weight_g else None,
                "inspected_quantity": dtl.inspected_quantity,
                "packing_tracking_number": dtl.purchase_tracking_number,
                "virtual_packed_yn": dtl.virtual_packed_yn,
                "del_yn": dtl.del_yn,

                # PACKING_DTL 정보 (LEFT JOIN으로 가져온 값들)
                "order_shipment_packing_dtl_no": packing_dtl.order_shipment_packing_dtl_no if packing_dtl else None,
                "packing_quantity": packing_dtl.packing_quantity if packing_dtl else None,
                "tracking_number": packing_dtl.tracking_number if packing_dtl else None,

                # PACKING_MST 정보 (박스 정보)
                "box_name": packing_mst.box_name if packing_mst else None,
                "package_box_spec_cd": packing_mst.package_box_spec_cd if packing_mst else None,

                # PACKING_DTL 생성/수정 정보
                "packing_dtl_created_at": packing_dtl.created_at if packing_dtl else None,
                "packing_dtl_created_by": packing_dtl.created_by if packing_dtl else None,
                "packing_dtl_updated_at": packing_dtl.updated_at if packing_dtl else None,
                "packing_dtl_updated_by": packing_dtl.updated_by if packing_dtl else None
            }
            dtl_data_list.append(combined_data)

        return ResponseBuilder.paged_success(
            content=dtl_data_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"쉽먼트 DTL 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )

def fetch_shipment_estimate_product_list(
        order_shipment_mst_no: Union[str, int],
        request: Request,
        pagination: common_schemas.PaginationRequest,
        db: Session
) -> common_response.ApiResponse[Union[PageResponse[dict], None]]:
    """쉽먼트 마스터 번호로 견적 상품 정보 조회 (estimated_yn이 1일 때)"""
    try:
        # 쉽먼트 마스터 존재 확인
        existing_shipment_mst = db.query(purchase_models.OrderShipmentMst).filter(
            purchase_models.OrderShipmentMst.order_shipment_mst_no == order_shipment_mst_no,
            purchase_models.OrderShipmentMst.del_yn == 0
        ).first()

        if not existing_shipment_mst:
            raise HTTPException(
                status_code=400,
                detail="해당 쉽먼트를 찾을 수 없습니다.",
            )

        # estimated_yn 확인
        if existing_shipment_mst.estimated_yn != 1:
            raise HTTPException(
                status_code=400,
                detail="견적이 생성되지 않은 쉽먼트입니다.",
            )

        # center_name 서브쿼리
        center_subquery = db.query(set_models.SetCenter.center_name).filter(
            set_models.SetCenter.center_no == purchase_models.OrderShipmentMst.center_no,
            set_models.SetCenter.del_yn == 0
        ).scalar_subquery()

        # 필요한 컬럼만 명시적으로 선택 (중복 컬럼은 label로 구분)
        query = (db.query(
            # EstimateProduct 컬럼
            purchase_models.OrderShipmentEstimateProduct.order_shipment_estimate_product_no,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_estimate_no,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_mst_no,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_dtl_no,
            purchase_models.OrderShipmentEstimateProduct.company_no,
            purchase_models.OrderShipmentEstimateProduct.center_no,
            purchase_models.OrderShipmentEstimateProduct.sku_id,
            purchase_models.OrderShipmentEstimateProduct.sku_name,
            purchase_models.OrderShipmentEstimateProduct.bundle,
            purchase_models.OrderShipmentEstimateProduct.purchase_quantity,
            purchase_models.OrderShipmentEstimateProduct.product_unit_price,
            purchase_models.OrderShipmentEstimateProduct.product_total_amount.label("product_product_total_amount"),
            # 별칭 지정
            purchase_models.OrderShipmentEstimateProduct.package_vinyl_spec_cd,
            purchase_models.OrderShipmentEstimateProduct.package_vinyl_spec_unit_price,
            purchase_models.OrderShipmentEstimateProduct.package_vinyl_spec_total_amount,
            purchase_models.OrderShipmentEstimateProduct.fail_yn,
            purchase_models.OrderShipmentEstimateProduct.total_amount.label("product_total_amount"),  # 별칭 지정
            purchase_models.OrderShipmentEstimateProduct.remark,
            purchase_models.OrderShipmentEstimateProduct.platform_type_cd.label("product_platform_type_cd"),
            purchase_models.OrderShipmentEstimateProduct.created_at.label("product_created_at"),
            purchase_models.OrderShipmentEstimateProduct.created_by.label("product_created_by"),
            purchase_models.OrderShipmentEstimateProduct.updated_at.label("product_updated_at"),
            purchase_models.OrderShipmentEstimateProduct.updated_by.label("product_updated_by"),

            # Estimate 컬럼
            purchase_models.OrderShipmentEstimate.estimate_id,
            purchase_models.OrderShipmentEstimate.estimate_date,
            purchase_models.OrderShipmentEstimate.product_total_amount.label("estimate_product_total_amount"),  # 별칭 지정
            purchase_models.OrderShipmentEstimate.vinyl_total_amount,
            purchase_models.OrderShipmentEstimate.box_total_amount,
            purchase_models.OrderShipmentEstimate.estimate_total_amount,

            # ShipmentMst 컬럼
            purchase_models.OrderShipmentMst.inbound_id,
            purchase_models.OrderShipmentMst.inbound_no,
            purchase_models.OrderShipmentMst.display_center_name,
            purchase_models.OrderShipmentMst.edd,
            purchase_models.OrderShipmentMst.order_shipment_mst_status_cd,
            purchase_models.OrderShipmentMst.estimated_yn,
            center_subquery.label("center_name"),

            # ShipmentDtl 컬럼 (선택적)
            purchase_models.OrderShipmentDtl.order_number,
            purchase_models.OrderShipmentDtl.sku_barcode,
            purchase_models.OrderShipmentDtl.confirmed_quantity,
            purchase_models.OrderShipmentDtl.shipped_quantity,
            purchase_models.OrderShipmentDtl.link,
            purchase_models.OrderShipmentDtl.option_type,
            purchase_models.OrderShipmentDtl.option_value,
            purchase_models.OrderShipmentDtl.length_mm,
            purchase_models.OrderShipmentDtl.width_mm,
            purchase_models.OrderShipmentDtl.height_mm,
            purchase_models.OrderShipmentDtl.weight_g,
            purchase_models.OrderShipmentDtl.coupang_option_name,
            purchase_models.OrderShipmentDtl.coupang_product_id,
            purchase_models.OrderShipmentDtl.coupang_option_id,
            purchase_models.OrderShipmentDtl.transport_type,
            purchase_models.OrderShipmentDtl.confirmed_quantity,

            # PackingDtl 컬럼
            purchase_models.OrderShipmentPackingDtl.box_name,
            purchase_models.OrderShipmentPackingDtl.packing_quantity
        ).join(
            purchase_models.OrderShipmentEstimate,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_estimate_no == purchase_models.OrderShipmentEstimate.order_shipment_estimate_no
        ).join(
            purchase_models.OrderShipmentMst,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_mst_no == purchase_models.OrderShipmentMst.order_shipment_mst_no
        ).outerjoin(
            purchase_models.OrderShipmentDtl,
            and_(
                purchase_models.OrderShipmentEstimateProduct.order_shipment_dtl_no == purchase_models.OrderShipmentDtl.order_shipment_dtl_no,
                purchase_models.OrderShipmentDtl.del_yn == 0
            )
        ).outerjoin(
            purchase_models.OrderShipmentPackingDtl,
            and_(
                purchase_models.OrderShipmentDtl.order_shipment_dtl_no == purchase_models.OrderShipmentPackingDtl.order_shipment_dtl_no,
                purchase_models.OrderShipmentPackingDtl.del_yn == 0  # JOIN 조건에 del_yn 포함
            )
        ).filter(
            purchase_models.OrderShipmentEstimateProduct.order_shipment_mst_no == order_shipment_mst_no,
            purchase_models.OrderShipmentEstimateProduct.del_yn == 0,
            purchase_models.OrderShipmentEstimate.del_yn == 0,
            purchase_models.OrderShipmentMst.del_yn == 0
        ).order_by(
            purchase_models.OrderShipmentEstimateProduct.created_at.desc()
        ))

        # 전체 개수
        total_elements = query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 결과 데이터 변환
        estimate_product_list = []
        for row in results:
            combined_data = {
                # 견적 상품 정보
                "order_shipment_estimate_product_no": row.order_shipment_estimate_product_no,
                "order_shipment_estimate_no": row.order_shipment_estimate_no,
                "order_shipment_mst_no": row.order_shipment_mst_no,
                "order_shipment_dtl_no": row.order_shipment_dtl_no,
                "company_no": row.company_no,
                "center_no": row.center_no,
                "center_name": row.center_name,
                "sku_id": row.sku_id,
                "sku_name": row.sku_name,
                "bundle": row.bundle,
                "purchase_quantity": row.purchase_quantity,
                "product_unit_price": float(row.product_unit_price) if row.product_unit_price else 0.0,
                "product_product_total_amount": float(
                    row.product_product_total_amount) if row.product_product_total_amount else 0.0,
                "package_vinyl_spec_cd": row.package_vinyl_spec_cd,
                "package_vinyl_spec_unit_price": float(
                    row.package_vinyl_spec_unit_price) if row.package_vinyl_spec_unit_price else 0.0,
                "package_vinyl_spec_total_amount": float(
                    row.package_vinyl_spec_total_amount) if row.package_vinyl_spec_total_amount else 0.0,
                "fail_yn": row.fail_yn,
                "total_amount": float(row.product_total_amount) if row.product_total_amount else 0.0,
                "remark": row.remark,
                "platform_type_cd": row.product_platform_type_cd,

                # 견적서 정보
                "estimate_id": row.estimate_id,
                "estimate_date": row.estimate_date,
                "estimate_total_amount": float(row.estimate_total_amount) if row.estimate_total_amount else 0.0,
                "estimate_product_total_amount": float(
                    row.estimate_product_total_amount) if row.estimate_product_total_amount else 0.0,
                "vinyl_total_amount": float(row.vinyl_total_amount) if row.vinyl_total_amount else 0.0,
                "box_total_amount": float(row.box_total_amount) if row.box_total_amount else 0.0,

                # 쉽먼트 MST 정보
                "inbound_id": row.inbound_id,
                "inbound_no": row.inbound_no,
                "display_center_name": row.display_center_name,
                "edd": row.edd,
                "order_shipment_mst_status_cd": row.order_shipment_mst_status_cd,
                "estimated_yn": row.estimated_yn,

                # 쉽먼트 DTL 정보
                "order_number": row.order_number,
                "sku_barcode": row.sku_barcode if row.sku_barcode else None,
                "confirmed_quantity": row.confirmed_quantity if row.confirmed_quantity else None,
                "shipped_quantity": row.shipped_quantity if row.shipped_quantity else None,
                "link": row.link if row.link else None,
                "option_type": row.option_type if row.option_type else None,
                "option_value": row.option_value if row.option_value else None,
                "length_mm": float(row.length_mm) if row.length_mm else None,
                "width_mm": float(row.width_mm) if row.width_mm else None,
                "height_mm": float(row.height_mm) if row.height_mm else None,
                "weight_g": float(row.weight_g) if row.weight_g else None,
                "coupang_option_name": row.coupang_option_name if row.coupang_option_name else None,
                "coupang_product_id": row.coupang_product_id if row.coupang_product_id else None,
                "coupang_option_id": row.coupang_option_id if row.coupang_option_id else None,
                "transport_type": row.transport_type if row.transport_type else None,
                "packing_quantity": row.packing_quantity if row.packing_quantity else None,

                # Packing 정보
                "box_name": row.box_name if row.box_name else None,

                # 생성/수정 정보
                "created_at": row.product_created_at,
                "created_by": row.product_created_by,
                "updated_at": row.product_updated_at,
                "updated_by": row.product_updated_by
            }
            estimate_product_list.append(combined_data)

        return ResponseBuilder.paged_success(
            content=estimate_product_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"견적 상품 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )
    

def fetch_shipment_dtl_all_list(
    order_mst_no: Union[str, int],
    request: Request,
    pagination: common_schemas.PaginationRequest,
    db: Session
) -> common_response.ApiResponse[Union[PageResponse[dict], None]]:
    """발주서 마스터 번호로 모든 쉽먼트 DTL 조회 (MST, PACKING_DTL 정보 포함)"""
    try:
        # 발주서 마스터 존재 확인
        existing_growth_order_mst = db.query(purchase_models.OrderMst).filter(
            purchase_models.OrderMst.order_mst_no == order_mst_no,
            purchase_models.OrderMst.del_yn == 0
        ).first()

        if not existing_growth_order_mst:
            raise HTTPException(
                status_code=400,
                detail="해당 발주서를 찾을 수 없습니다."
            )

        # center_name 서브쿼리
        center_subquery = db.query(set_models.SetCenter.center_name).filter(
            set_models.SetCenter.center_no == purchase_models.OrderShipmentMst.center_no,
            set_models.SetCenter.del_yn == 0
        ).scalar_subquery()

        # MST, DTL, PACKING_DTL, PACKING_MST LEFT OUTER JOIN 쿼리 구성
        query = db.query(
            purchase_models.OrderShipmentMst,
            purchase_models.OrderShipmentDtl,
            purchase_models.OrderShipmentPackingDtl,
            purchase_models.OrderShipmentPackingMst,
            center_subquery.label("center_name")
        ).join(
            purchase_models.OrderShipmentDtl,
            purchase_models.OrderShipmentMst.order_shipment_mst_no == purchase_models.OrderShipmentDtl.order_shipment_mst_no
        ).outerjoin(
            purchase_models.OrderShipmentPackingDtl,
            and_(
                purchase_models.OrderShipmentDtl.order_shipment_dtl_no == purchase_models.OrderShipmentPackingDtl.order_shipment_dtl_no,
                purchase_models.OrderShipmentPackingDtl.del_yn == 0  # JOIN 조건에 del_yn 포함
            )
        ).outerjoin(
            purchase_models.OrderShipmentPackingMst,
            and_(
                purchase_models.OrderShipmentPackingDtl.order_shipment_packing_mst_no == purchase_models.OrderShipmentPackingMst.order_shipment_packing_mst_no,
                purchase_models.OrderShipmentPackingMst.del_yn == 0  # JOIN 조건에 del_yn 포함
            )
        ).filter(
            purchase_models.OrderShipmentMst.order_mst_no == order_mst_no,
            purchase_models.OrderShipmentMst.del_yn == 0,
            purchase_models.OrderShipmentDtl.del_yn == 0
            # PACKING_DTL 필터 조건은 JOIN 조건으로 이동하여 LEFT JOIN이 제대로 동작하도록 함
        ).order_by(
            purchase_models.OrderShipmentMst.estimated_yn.desc(),
            purchase_models.OrderShipmentDtl.created_at.desc(),
            purchase_models.OrderShipmentPackingDtl.created_at.desc()
        )

        # 전체 개수
        total_elements = query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 공통코드
        shipment_status_com_code_dict = com_code_util.get_com_code_dict_by_parent_code("ORDER_SHIPMENT_MST_STATUS_CD", db)

        # 결과 데이터 변환
        dtl_data_list = []
        for mst, dtl, packing_dtl, packing_mst, center_name in results:
            com_code = shipment_status_com_code_dict.get(mst.order_shipment_mst_status_cd)
            combined_data = {
                # MST 정보
                "order_shipment_mst_no": mst.order_shipment_mst_no,
                "order_mst_no": mst.order_mst_no,
                "center_no": mst.center_no,
                "estimated_yn": mst.estimated_yn,
                "center_name": center_name,
                "edd": mst.edd,
                "order_shipment_mst_status_cd": mst.order_shipment_mst_status_cd,
                "order_shipment_mst_status_name": com_code.code_name,
                "order_shipment_mst_status_color": com_code.keyword1,
                "mst_created_at": mst.created_at,
                "mst_created_by": mst.created_by,
                "mst_updated_at": mst.updated_at,
                "mst_updated_by": mst.updated_by,

                # DTL 정보
                "order_shipment_dtl_no": dtl.order_shipment_dtl_no,
                "order_shipment_packing_mst_no": dtl.order_shipment_packing_mst_no,
                "company_no": dtl.company_no,
                "order_number": dtl.order_number,
                "transport_type": dtl.transport_type,
                "sku_id": dtl.sku_id,
                "sku_barcode": dtl.sku_barcode,
                "sku_name": dtl.sku_name,
                "confirmed_quantity": dtl.confirmed_quantity,
                "purchase_tracking_number": dtl.purchase_tracking_number,  # SHIPMENT_DTL의 1688 운송장번호
                "shipped_quantity": dtl.shipped_quantity,
                "link": dtl.link,
                "option_type": dtl.option_type,
                "option_value": dtl.option_value,
                "linked_option": dtl.linked_option,
                "linked_spec_id": dtl.linked_spec_id,
                "linked_sku_id": dtl.linked_sku_id,
                "linked_open_uid": dtl.linked_open_uid,
                "multiple_value": dtl.multiple_value,
                "length_mm": float(dtl.length_mm) if dtl.length_mm else None,
                "width_mm": float(dtl.width_mm) if dtl.width_mm else None,
                "height_mm": float(dtl.height_mm) if dtl.height_mm else None,
                "weight_g": float(dtl.weight_g) if dtl.weight_g else None,
                "inspected_quantity": dtl.inspected_quantity,
                "virtual_packed_yn": dtl.virtual_packed_yn,
                "dtl_created_at": dtl.created_at,
                "dtl_created_by": dtl.created_by,
                "dtl_updated_at": dtl.updated_at,
                "dtl_updated_by": dtl.updated_by,

                # PACKING_DTL 정보 (LEFT JOIN으로 가져온 값들)
                "order_shipment_packing_dtl_no": packing_dtl.order_shipment_packing_dtl_no if packing_dtl else None,
                "packing_quantity": packing_dtl.packing_quantity if packing_dtl else None,
                "packing_tracking_number": packing_dtl.tracking_number if packing_dtl else None,  # PACKING_DTL의 tracking_number

                # PACKING_MST 정보 (박스 정보)
                "box_name": packing_mst.box_name if packing_mst else None,
                "package_box_spec_cd": packing_mst.package_box_spec_cd if packing_mst else None,

                # PACKING_DTL 생성/수정 정보
                "packing_dtl_created_at": packing_dtl.created_at if packing_dtl else None,
                "packing_dtl_created_by": packing_dtl.created_by if packing_dtl else None,
                "packing_dtl_updated_at": packing_dtl.updated_at if packing_dtl else None,
                "packing_dtl_updated_by": packing_dtl.updated_by if packing_dtl else None
            }
            dtl_data_list.append(combined_data)

        return ResponseBuilder.paged_success(
            content=dtl_data_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"쉽먼트 DTL 전체 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


def fetch_shipment_estimate_product_list_all(
        order_mst_no: Union[str, int],
        request: Request,
        pagination: common_schemas.PaginationRequest,
        db: Session
) -> common_response.ApiResponse[Union[PageResponse[dict], None]]:
    """발주서 마스터 번호로 모든 견적 상품 정보 조회 (estimated_yn이 1인 모든 shipment의 견적 데이터)"""
    try:
        # 발주서 마스터 존재 확인
        existing_order_mst = db.query(purchase_models.OrderMst).filter(
            purchase_models.OrderMst.order_mst_no == order_mst_no,
            purchase_models.OrderMst.del_yn == 0
        ).first()

        if not existing_order_mst:
            raise HTTPException(
                status_code=400,
                detail="해당 발주서를 찾을 수 없습니다.",
            )

        # center_name 서브쿼리
        center_subquery = db.query(set_models.SetCenter.center_name).filter(
            set_models.SetCenter.center_no == purchase_models.OrderShipmentMst.center_no,
            set_models.SetCenter.del_yn == 0
        ).scalar_subquery()

        # 필요한 컬럼만 명시적으로 선택 (중복 컬럼은 label로 구분)
        query = (db.query(
            # EstimateProduct 컬럼
            purchase_models.OrderShipmentEstimateProduct.order_shipment_estimate_product_no,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_estimate_no,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_mst_no,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_dtl_no,
            purchase_models.OrderShipmentEstimateProduct.company_no,
            purchase_models.OrderShipmentEstimateProduct.center_no,
            purchase_models.OrderShipmentEstimateProduct.sku_id,
            purchase_models.OrderShipmentEstimateProduct.sku_name,
            purchase_models.OrderShipmentEstimateProduct.bundle,
            purchase_models.OrderShipmentEstimateProduct.purchase_quantity,
            purchase_models.OrderShipmentEstimateProduct.product_unit_price,
            purchase_models.OrderShipmentEstimateProduct.product_total_amount.label("product_product_total_amount"),
            purchase_models.OrderShipmentEstimateProduct.package_vinyl_spec_cd,
            purchase_models.OrderShipmentEstimateProduct.package_vinyl_spec_unit_price,
            purchase_models.OrderShipmentEstimateProduct.package_vinyl_spec_total_amount,
            purchase_models.OrderShipmentEstimateProduct.fail_yn,
            purchase_models.OrderShipmentEstimateProduct.total_amount.label("product_total_amount"),
            purchase_models.OrderShipmentEstimateProduct.remark,
            purchase_models.OrderShipmentEstimateProduct.platform_type_cd.label("product_platform_type_cd"),
            purchase_models.OrderShipmentEstimateProduct.created_at.label("product_created_at"),
            purchase_models.OrderShipmentEstimateProduct.created_by.label("product_created_by"),
            purchase_models.OrderShipmentEstimateProduct.updated_at.label("product_updated_at"),
            purchase_models.OrderShipmentEstimateProduct.updated_by.label("product_updated_by"),

            # Estimate 컬럼
            purchase_models.OrderShipmentEstimate.order_mst_no,
            purchase_models.OrderShipmentEstimate.estimate_id,
            purchase_models.OrderShipmentEstimate.estimate_date,
            purchase_models.OrderShipmentEstimate.product_total_amount.label("estimate_product_total_amount"),
            purchase_models.OrderShipmentEstimate.vinyl_total_amount,
            purchase_models.OrderShipmentEstimate.box_total_amount,
            purchase_models.OrderShipmentEstimate.estimate_total_amount,

            # ShipmentMst 컬럼
            purchase_models.OrderShipmentMst.inbound_id,
            purchase_models.OrderShipmentMst.inbound_no,
            purchase_models.OrderShipmentMst.display_center_name,
            purchase_models.OrderShipmentMst.edd,
            purchase_models.OrderShipmentMst.order_shipment_mst_status_cd,
            purchase_models.OrderShipmentMst.estimated_yn,
            center_subquery.label("center_name"),

            # ShipmentDtl 컬럼 (선택적)
            purchase_models.OrderShipmentDtl.order_number,
            purchase_models.OrderShipmentDtl.sku_barcode,
            purchase_models.OrderShipmentDtl.confirmed_quantity.label("dtl_confirmed_quantity"),
            purchase_models.OrderShipmentDtl.shipped_quantity,
            purchase_models.OrderShipmentDtl.link,
            purchase_models.OrderShipmentDtl.option_type,
            purchase_models.OrderShipmentDtl.option_value,
            purchase_models.OrderShipmentDtl.length_mm,
            purchase_models.OrderShipmentDtl.width_mm,
            purchase_models.OrderShipmentDtl.height_mm,
            purchase_models.OrderShipmentDtl.weight_g,
            purchase_models.OrderShipmentDtl.coupang_option_name,
            purchase_models.OrderShipmentDtl.coupang_product_id,
            purchase_models.OrderShipmentDtl.coupang_option_id,
            purchase_models.OrderShipmentDtl.transport_type,
            purchase_models.OrderShipmentDtl.linked_open_uid,

            # PackingDtl 컬럼
            purchase_models.OrderShipmentPackingDtl.packing_quantity,
            purchase_models.OrderShipmentPackingDtl.box_name
        ).join(
            purchase_models.OrderShipmentEstimate,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_estimate_no == purchase_models.OrderShipmentEstimate.order_shipment_estimate_no
        ).join(
            purchase_models.OrderShipmentMst,
            purchase_models.OrderShipmentEstimateProduct.order_shipment_mst_no == purchase_models.OrderShipmentMst.order_shipment_mst_no
        ).outerjoin(
            purchase_models.OrderShipmentDtl,
            and_(
                purchase_models.OrderShipmentEstimateProduct.order_shipment_dtl_no == purchase_models.OrderShipmentDtl.order_shipment_dtl_no,
                purchase_models.OrderShipmentDtl.del_yn == 0
            )
        ).outerjoin(
            purchase_models.OrderShipmentPackingDtl,
            and_(
                purchase_models.OrderShipmentDtl.order_shipment_dtl_no == purchase_models.OrderShipmentPackingDtl.order_shipment_dtl_no,
                purchase_models.OrderShipmentPackingDtl.del_yn == 0
            )
        ).filter(
            purchase_models.OrderShipmentEstimate.order_mst_no == order_mst_no,  # ✅ order_mst_no로 필터링
            purchase_models.OrderShipmentEstimateProduct.del_yn == 0,
            purchase_models.OrderShipmentEstimate.del_yn == 0,
            purchase_models.OrderShipmentMst.del_yn == 0
        ).order_by(
            purchase_models.OrderShipmentMst.estimated_yn.desc(),  # estimated_yn 내림차순
            purchase_models.OrderShipmentEstimateProduct.created_at.desc()
        ))

        # 전체 개수
        total_elements = query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 결과 데이터 변환
        estimate_product_list = []
        for row in results:
            combined_data = {
                # 견적 상품 정보
                "order_shipment_estimate_product_no": row.order_shipment_estimate_product_no,
                "order_shipment_estimate_no": row.order_shipment_estimate_no,
                "order_shipment_mst_no": row.order_shipment_mst_no,
                "order_shipment_dtl_no": row.order_shipment_dtl_no,
                "company_no": row.company_no,
                "center_no": row.center_no,
                "center_name": row.center_name,
                "sku_id": row.sku_id,
                "sku_name": row.sku_name,
                "bundle": row.bundle,
                "purchase_quantity": row.purchase_quantity,
                "product_unit_price": float(row.product_unit_price) if row.product_unit_price else 0.0,
                "product_product_total_amount": float(row.product_product_total_amount) if row.product_product_total_amount else 0.0,
                "package_vinyl_spec_cd": row.package_vinyl_spec_cd,
                "package_vinyl_spec_unit_price": float(row.package_vinyl_spec_unit_price) if row.package_vinyl_spec_unit_price else 0.0,
                "package_vinyl_spec_total_amount": float(row.package_vinyl_spec_total_amount) if row.package_vinyl_spec_total_amount else 0.0,
                "fail_yn": row.fail_yn,
                "total_amount": float(row.product_total_amount) if row.product_total_amount else 0.0,
                "remark": row.remark,
                "platform_type_cd": row.product_platform_type_cd,

                # 견적서 정보
                "order_mst_no": row.order_mst_no,
                "estimate_id": row.estimate_id,
                "estimate_date": row.estimate_date,
                "estimate_total_amount": float(row.estimate_total_amount) if row.estimate_total_amount else 0.0,
                "estimate_product_total_amount": float(row.estimate_product_total_amount) if row.estimate_product_total_amount else 0.0,
                "vinyl_total_amount": float(row.vinyl_total_amount) if row.vinyl_total_amount else 0.0,
                "box_total_amount": float(row.box_total_amount) if row.box_total_amount else 0.0,

                # 쉽먼트 MST 정보
                "inbound_id": row.inbound_id,
                "inbound_no": row.inbound_no,
                "display_center_name": row.display_center_name,
                "edd": row.edd,
                "order_shipment_mst_status_cd": row.order_shipment_mst_status_cd,
                "estimated_yn": row.estimated_yn,

                # 쉽먼트 DTL 정보
                "order_number": row.order_number if row.order_number else None,
                "sku_barcode": row.sku_barcode if row.sku_barcode else None,
                "confirmed_quantity": row.dtl_confirmed_quantity if row.dtl_confirmed_quantity else None,
                "shipped_quantity": row.shipped_quantity if row.shipped_quantity else None,
                "link": row.link if row.link else None,
                "option_type": row.option_type if row.option_type else None,
                "option_value": row.option_value if row.option_value else None,
                "length_mm": float(row.length_mm) if row.length_mm else None,
                "width_mm": float(row.width_mm) if row.width_mm else None,
                "height_mm": float(row.height_mm) if row.height_mm else None,
                "weight_g": float(row.weight_g) if row.weight_g else None,
                "coupang_option_name": row.coupang_option_name if row.coupang_option_name else None,
                "coupang_product_id": row.coupang_product_id if row.coupang_product_id else None,
                "coupang_option_id": row.coupang_option_id if row.coupang_option_id else None,
                "transport_type": row.transport_type if row.transport_type else None,
                "linked_open_uid": row.linked_open_uid if row.linked_open_uid else None,

                # Packing 정보
                "packing_quantity": row.packing_quantity if row.packing_quantity else None,
                "box_name": row.box_name if row.box_name else None,

                # 생성/수정 정보
                "created_at": row.product_created_at,
                "created_by": row.product_created_by,
                "updated_at": row.product_updated_at,
                "updated_by": row.product_updated_by
            }
            estimate_product_list.append(combined_data)

        return ResponseBuilder.paged_success(
            content=estimate_product_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"견적 상품 전체 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )