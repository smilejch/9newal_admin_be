from fastapi import Depends, Request, status, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, or_
from app.utils import file_util, com_code_util
from app.utils import crypto_util
from app.utils import  email_util
from app.core.security import hash_password
import pandas as pd

import os
import platform
from datetime import datetime
import tempfile

from app.common import response as common_response
from app.common.schemas.request import PaginationRequest
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.setting.schemas import SkuBase, SkuFilterRequest, UserBase, CenterBase, UserFilterRequest, CompanyFilterRequest, CompanyBase
from app.modules.setting import models as setting_models
from app.modules.common import models as common_models
from app.modules.auth import models as auth_models
from typing import Union
from app.utils.auth_util import get_authenticated_user_no
from app.modules.common import service as common_service

def create_sku(
        sku_info: SkuBase,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    try:
        user_no, _ = get_authenticated_user_no(request)  # company_no는 사용하지 않음

        # ✅ 회사 번호 검증 (프론트에서 넘어온 값 사용)
        company_no = sku_info.company_no
        if not company_no:
            raise HTTPException(
                status_code=400,
                detail="회사 번호는 필수 입력 항목입니다."
            )

        # SKU ID 8자리 숫자 검증
        sku_id = sku_info.sku_id
        if not sku_id or sku_id.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="SKU ID는 필수 입력 항목입니다."
            )

        sku_id = sku_id.strip()

        # 소수점이 있는 경우 정수 부분만 추출 (예: 12345678.0 -> 12345678)
        sku_id_error = False
        if '.' in sku_id:
            try:
                sku_id_float = float(sku_id)
                if sku_id_float.is_integer():
                    sku_id = str(int(sku_id_float))
                else:
                    sku_id_error = True

            except ValueError:
                sku_id_error = True

        # 8자리 숫자인지 검증
        if not (sku_id.isdigit() and len(sku_id) == 8):
            sku_id_error = True

        if sku_id_error:
            raise HTTPException(
                status_code=400,
                detail=f"SKU ID는 8자리 숫자여야 합니다. 입력값: '{sku_id}'"
            )

        # Bundle 값 검증 및 변환
        bundle = getattr(sku_info, 'bundle', None)

        bundle_error = False
        bundle_error_msg = ""
        if bundle is not None and bundle != '':
            # 문자열인 경우 숫자로 변환 시도
            if isinstance(bundle, str):
                bundle = bundle.strip()
                if bundle == '':
                    bundle = None
                elif bundle.isdigit():
                    bundle = int(bundle)
                else:
                    bundle_error = True
                    bundle_error_msg = f"bundle은 숫자만 입력 가능합니다. 입력값: '{bundle}'"
            # 숫자가 아닌 다른 타입인 경우
            elif not isinstance(bundle, (int, float)):
                bundle_error = True
                bundle_error_msg = f"bundle은 None 또는 숫자만 입력 가능합니다."
            # float인 경우 정수로 변환
            elif isinstance(bundle, float):
                if bundle.is_integer():
                    bundle = int(bundle)
                else:
                    bundle_error = True
                    bundle_error_msg = f"bundle은 정수만 입력 가능합니다. 입력값: {bundle}"
        else:
            bundle = None

        if bundle_error:
            raise HTTPException(
                status_code=400,
                detail=bundle_error_msg
            )

        # ✅ 바코드 일관성 검증 추가
        barcode = getattr(sku_info, 'barcode', None)
        if barcode:
            barcode = str(barcode).strip()

            # 해당 SKU ID로 이미 등록된 다른 바코드가 있는지 확인
            existing_sku_with_barcode = db.query(setting_models.SetSku).filter(
                setting_models.SetSku.sku_id == sku_id,
                setting_models.SetSku.company_no == company_no,
                setting_models.SetSku.del_yn == 0,
                setting_models.SetSku.barcode.isnot(None),
                setting_models.SetSku.barcode != barcode  # 다른 바코드인 경우
            ).first()

            if existing_sku_with_barcode:
                raise HTTPException(
                    status_code=400,
                    detail=f"SKU ID '{sku_id}'는 이미 다른 바코드('{existing_sku_with_barcode.barcode}')로 등록되어 있습니다. "
                           f"입력된 바코드: '{barcode}'"
                )

        # 중복 체크 로직 (SKU ID + Bundle 조합)
        existing_sku_query = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.sku_id == sku_id,
            setting_models.SetSku.company_no == company_no,
            setting_models.SetSku.del_yn == 0
        )

        # bundle이 None이면 bundle이 None인 것들만 체크
        if bundle is None:
            existing_sku = existing_sku_query.filter(
                setting_models.SetSku.bundle.is_(None)
            ).first()
        else:
            # bundle이 있으면 정확히 일치하는 것 체크
            existing_sku = existing_sku_query.filter(
                setting_models.SetSku.bundle == bundle
            ).first()

        if existing_sku:
            bundle_msg = f"(bundle: {bundle})" if bundle is not None else "(bundle: 없음)"
            raise HTTPException(
                status_code=400,
                detail=f"이미 존재하는 SKU ID입니다. sku_id: {sku_id} {bundle_msg}"
            )

        # ✅ 바코드가 없는 경우 기존 바코드 상속
        if not barcode:
            # 해당 SKU ID의 다른 bundle에서 바코드 가져오기
            existing_sku_for_barcode = db.query(setting_models.SetSku).filter(
                setting_models.SetSku.sku_id == sku_id,
                setting_models.SetSku.company_no == company_no,
                setting_models.SetSku.del_yn == 0,
                setting_models.SetSku.barcode.isnot(None)
            ).first()

            if existing_sku_for_barcode:
                barcode = existing_sku_for_barcode.barcode

        # Pydantic 모델을 dict로 변환 후 setting_models.SetSku 생성
        sku_dict = sku_info.dict(exclude_unset=True, exclude={'sku_no', 'option_type', 'company_name'})

        # 검증된 값들 설정
        sku_dict['sku_id'] = sku_id
        sku_dict['bundle'] = bundle
        sku_dict['barcode'] = barcode  # 검증된 바코드 설정
        sku_dict['company_no'] = company_no  # 프론트에서 넘어온 회사 번호

        # 생성자 정보 추가
        sku_dict['created_by'] = user_no

        new_sku = setting_models.SetSku(**sku_dict)

        db.add(new_sku)
        db.commit()
        db.refresh(new_sku)

        # 정상적으로 저장된 값 셋팅
        data = {
            "sku_no": new_sku.sku_no,
            "company_no": new_sku.company_no,
            "sku_id": new_sku.sku_id,
            "sku_name": new_sku.sku_name,
            "bundle": new_sku.bundle,
            "barcode": new_sku.barcode,  # 바코드 포함
            "created_at": new_sku.created_at
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="SKU가 성공적으로 등록되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise  # HTTPException은 그대로 전파
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


def fetch_sku_list(
        request: Request,
        filter: SkuFilterRequest,
        db: Session = Depends(get_db),
        pagination: PaginationRequest = Depends()
) -> common_response.ApiResponse[Union[common_response.PageResponse[SkuBase], None]]:
    try:

        # 포장비닐규격 공통코드 서브쿼리 생성
        package_vinyl_subquery = db.query(common_models.ComCode.code_name).filter(
            common_models.ComCode.com_code == setting_models.SetSku.package_vinyl_spec_cd,
            common_models.ComCode.parent_com_code == "PACKAGE_VINYL_SPEC_CD",
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).scalar_subquery()

        # FTA 공통코드 서브쿼리 생성
        fta_subquery = db.query(common_models.ComCode.code_name).filter(
            common_models.ComCode.com_code == setting_models.SetSku.fta_cd,
            common_models.ComCode.parent_com_code == "FTA_CD",
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).scalar_subquery()

        # 납품여부 공통코드 서브쿼리 생성
        delivery_status_subquery = db.query(common_models.ComCode.code_name).filter(
            common_models.ComCode.com_code == setting_models.SetSku.delivery_status_cd,
            common_models.ComCode.parent_com_code == "DELIVERY_STATUS_CD",
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).scalar_subquery()

        # 쿼리 생성 및 기본 필터 (회사 정보 JOIN 추가)
        query = db.query(
            setting_models.SetSku,
            package_vinyl_subquery.label("package_vinyl_spec_name"),
            fta_subquery.label("fta_name"),
            delivery_status_subquery.label("delivery_status_name"),
            auth_models.ComCompany.company_name
        ).outerjoin(
            auth_models.ComCompany,
            setting_models.SetSku.company_no == auth_models.ComCompany.company_no
        ).filter(
            setting_models.SetSku.del_yn == 0
        )

        # company_no 필터 적용 (리스트가 비어있지 않은 경우)
        if filter.company_no and len(filter.company_no) > 0:
            query = query.filter(setting_models.SetSku.company_no.in_(filter.company_no))

        # SkuFilterRequest 조건 동적 적용 (LIKE 검색)
        for filter_field, filter_value in filter.dict().items():
            # company_no는 이미 처리했으므로 스킵
            if filter_field == 'company_no':
                continue

            # 필터 값이 None이거나 빈 문자열이 아닌 경우에만 조건 적용
            if filter_value is not None and str(filter_value).strip() != '':
                # setting_models.SetSku 모델에 해당 필드가 존재하는지 확인
                if hasattr(setting_models.SetSku, filter_field):
                    model_column = getattr(setting_models.SetSku, filter_field)
                    query = query.filter(model_column.like(f"%{str(filter_value).strip()}%"))
                else:
                    print(f"Warning: Field '{filter_field}' not found in setting_models.SetSku model")

        query = query.order_by(desc(setting_models.SetSku.sku_id), desc(setting_models.SetSku.bundle))

        # 전체 개수 (서브쿼리 없이 카운트)
        count_query = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.del_yn == 0
        )

        # company_no 필터 적용 (count_query에도)
        if filter.company_no and len(filter.company_no) > 0:
            count_query = count_query.filter(setting_models.SetSku.company_no.in_(filter.company_no))

        # 같은 필터 조건 적용
        for filter_field, filter_value in filter.dict().items():
            # company_no는 이미 처리했으므로 스킵
            if filter_field == 'company_no':
                continue

            if filter_value is not None and str(filter_value).strip() != '':
                if hasattr(setting_models.SetSku, filter_field):
                    model_column = getattr(setting_models.SetSku, filter_field)
                    count_query = count_query.filter(model_column.like(f"%{str(filter_value).strip()}%"))

        total_elements = count_query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 결과를 딕셔너리 리스트로 변환
        sku_list = []
        for result in results:
            # result에서 각 컬럼 추출
            sku = result.SetSku if hasattr(result, 'SetSku') else result[0]
            package_vinyl_spec_name = result.package_vinyl_spec_name if hasattr(result, 'package_vinyl_spec_name') else \
            result[1]
            fta_name = result.fta_name if hasattr(result, 'fta_name') else result[2]
            delivery_status_name = result.delivery_status_name if hasattr(result, 'delivery_status_name') else result[3]
            company_name = result.company_name if hasattr(result, 'company_name') else result[4]

            # SKU를 딕셔너리로 변환
            sku_dict = SkuBase.from_orm(sku).dict()

            # 서브쿼리 및 JOIN 결과 추가
            sku_dict['package_vinyl_spec_name'] = package_vinyl_spec_name
            sku_dict['fta_name'] = fta_name
            sku_dict['delivery_status_name'] = delivery_status_name
            sku_dict['company_name'] = company_name

            sku_list.append(sku_dict)

        return common_response.ResponseBuilder.paged_success(
            content=sku_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except Exception as e:
        print(str(e))
        raise HTTPException(
            status_code=400,
            detail=f"SKU 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


def fetch_sku(
        sku_no: Union[str, int],
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    try:
        # ID로 SKU 조회 (회사 정보 JOIN)
        result = db.query(
            setting_models.SetSku,
            auth_models.ComCompany.company_name
        ).outerjoin(
            auth_models.ComCompany,
            setting_models.SetSku.company_no == auth_models.ComCompany.company_no
        ).filter(
            setting_models.SetSku.sku_no == sku_no,
            setting_models.SetSku.del_yn == 0
        ).first()

        if not result:
            raise HTTPException(
                status_code=400,
                detail=f"ID {sku_no}에 해당하는 SKU를 찾을 수 없습니다."
            )

        # result에서 SKU와 회사명 추출
        sku = result[0]
        company_name = result[1]

        # SKU 데이터를 dict로 변환
        data = {
            "sku_no": sku.sku_no,
            "company_no": sku.company_no,
            "company_name": company_name,
            "sku_id": sku.sku_id,
            "exposure_id": sku.exposure_id,
            "bundle": sku.bundle,
            "sku_name": sku.sku_name,
            "link": sku.link,
            "option_value": sku.option_value,
            "linked_option": sku.linked_option,
            "barcode": sku.barcode,
            "multiple_value": sku.multiple_value,
            "package_unit_quantity": sku.package_unit_quantity,
            "cn_name": sku.cn_name,
            "package_vinyl_spec_cd": sku.package_vinyl_spec_cd,
            "en_name": sku.en_name,
            "hs_code": sku.hs_code,
            "en_name_for_cn": sku.en_name_for_cn,
            "hs_code_cn": sku.hs_code_cn,
            "fta_cd": sku.fta_cd,
            "material": sku.material,
            "length_mm": sku.length_mm,
            "width_mm": sku.width_mm,
            "height_mm": sku.height_mm,
            "weight_g": sku.weight_g,
            "delivery_status_cd": sku.delivery_status_cd,
            "sale_price": sku.sale_price,
            "cost_yuan": sku.cost_yuan,
            "cost_krw": sku.cost_krw,
            "supply_price": sku.supply_price,
            "margin": sku.margin,
            "created_at": sku.created_at,
            "updated_at": sku.updated_at,
            "created_by": sku.created_by,
            "updated_by": sku.updated_by,
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="SKU 상세 조회가 완료되었습니다."
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SKU 조회 중 오류가 발생했습니다: {str(e)}"
        )


# SKU 수정
def update_sku(
        sku_info: SkuBase,
        sku_no: Union[str, int],
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    try:

        user_no, company_no = get_authenticated_user_no(request)

        # 업데이트할 SKU 찾기
        existing_sku = db.query(setting_models.SetSku).filter(setting_models.SetSku.sku_no == sku_no).first()

        if not existing_sku:
            raise HTTPException(
                status_code=400,
                detail=f"ID {sku_no}에 해당하는 SKU를 찾을 수 없습니다."
            )

        # Pydantic 모델을 dict로 변환 (None 값 제외)
        update_dict = sku_info.dict(exclude_unset=True)

        # 업데이트할 필드가 있는지 확인
        if not update_dict:
            raise HTTPException(
                status_code=400,
                detail="업데이트할 필드가 없습니다."
            )

        # link 변경 여부 확인
        link_changed = False
        if 'link' in update_dict:
            new_link = update_dict['link']
            existing_link = existing_sku.link

            # 새 링크와 기존 링크가 다른 경우
            if new_link != existing_link:
                link_changed = True

        # 기존 레코드 업데이트
        for field, value in update_dict.items():
            if hasattr(existing_sku, field):
                setattr(existing_sku, field, value)

        # link가 변경된 경우 연동 관련 필드들을 null로 설정
        if link_changed:
            existing_sku.linked_option = None
            existing_sku.linked_spec_id = None
            existing_sku.linked_sku_id = None
            existing_sku.linked_open_uid = None
            existing_sku.option_type = "MANUAL"

        # updated_at 필드가 있다면 현재 시간으로 설정
        if hasattr(existing_sku, 'updated_at'):
            from datetime import datetime
            existing_sku.updated_at = datetime.now()

        if hasattr(existing_sku, 'updated_by'):
            existing_sku.updated_by = user_no

        db.commit()
        db.refresh(existing_sku)

        # 업데이트된 데이터 반환
        data = {
            "sku_no": existing_sku.sku_no,
            "sku_id": existing_sku.sku_id,
            "sku_name": existing_sku.sku_name,
            "link": existing_sku.link,
            "updated_at": existing_sku.updated_at,
            "updated_fields": list(update_dict.keys()),  # 어떤 필드가 업데이트되었는지
            "link_changed": link_changed,  # 링크 변경 여부
            "linked_fields_reset": link_changed  # 연동 필드 초기화 여부
        }

        message = "SKU가 성공적으로 수정되었습니다."
        if link_changed:
            message += " (링크 변경으로 인해 연동 정보가 초기화되었습니다.)"

        return common_response.ResponseBuilder.success(
            data=data,
            message=message
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"SKU 수정 중 오류가 발생했습니다: {str(e)}"
        )


# SKU 삭제
def delete_sku(
        sku_no: Union[str, int],
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    try:
        # 삭제할 SKU 찾기
        sku = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.sku_no == sku_no,
            setting_models.SetSku.del_yn == 0
        ).first()

        if not sku:
            raise HTTPException(
                status_code=400,
                detail=f"삭제할 수 없는 SKU입니다. (ID: {sku_no})"
            )

        # 논리적 삭제
        sku.del_yn = 1
        db.commit()

        data = {
            "sku_no": sku_no,
            "deleted": True
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="SKU가 성공적으로 삭제되었습니다."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"SKU 삭제 중 오류가 발생했습니다: {str(e)}"
        )


# 더 간단한 방법: 직접 공통코드를 조회해서 매핑하는 버전
def download_sku_template(
        request: Request,
        db: Session = Depends(get_db)
) -> FileResponse:
    try:
        # SKU 템플릿 헤더 정의
        template_headers = [
            "SKU ID", "노출 ID", "묶음", "상품명", "링크",
            "옵션", "연동옵션", "바코드",
            "판매 구성 수량", "포장 개수",
            "중문명", "포장비닐규격", "영문명",
            "HS코드번호", "영문명(중국용)", "HS코드번호(중국용)", "FTA", "재질",
            "길이(mm)", "넓이(mm)", "높이(mm)", "중량(g)",
            "납품여부", "판매가격", "원가-위안화", "원가-원화",
            "공급가", "마진"
        ]

        user_no, company_no = get_authenticated_user_no(request)

        # 포장비닐규격 공통코드를 미리 조회해서 매핑 생성
        package_vinyl_codes = db.query(common_models.ComCode).filter(
            common_models.ComCode.parent_com_code == 'PACKAGE_VINYL_SPEC_CD',  # 실제 부모 코드에 맞게 수정
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).all()

        package_vinyl_code_to_name = {code.com_code: code.code_name for code in package_vinyl_codes}

        # FTA 공통코드를 미리 조회해서 매핑 생성
        fta_codes = db.query(common_models.ComCode).filter(
            common_models.ComCode.parent_com_code == 'FTA_CD',  # 실제 부모 코드에 맞게 수정
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).all()

        fta_code_to_name = {code.com_code: code.code_name for code in fta_codes}

        # 납품여부 공통코드를 미리 조회해서 매핑 생성
        delivery_status_codes = db.query(common_models.ComCode).filter(
            common_models.ComCode.parent_com_code == 'DELIVERY_STATUS_CD',  # 실제 부모 코드에 맞게 수정
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).all()

        delivery_status_code_to_name = {code.com_code: code.code_name for code in delivery_status_codes}

        # 실제 데이터 조회 (del_yn = 0인 것만)
        skus = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.del_yn == 0,
            setting_models.SetSku.company_no == company_no
        ).all()

        # 데이터를 리스트로 변환
        data_list = []
        for sku in skus:
            # 포장비닐규격 코드를 이름으로 변환
            package_vinyl_spec_name = None
            if sku.package_vinyl_spec_cd and sku.package_vinyl_spec_cd in package_vinyl_code_to_name:
                package_vinyl_spec_name = package_vinyl_code_to_name[sku.package_vinyl_spec_cd]

            # FTA 코드를 이름으로 변환
            fta_name = None
            if sku.fta_cd and sku.fta_cd in fta_code_to_name:
                fta_name = fta_code_to_name[sku.fta_cd]

            # 납품여부 코드를 이름으로 변환
            delivery_status_name = None
            if sku.delivery_status_cd and sku.delivery_status_cd in delivery_status_code_to_name:
                delivery_status_name = delivery_status_code_to_name[sku.delivery_status_cd]

            data_list.append([
                sku.sku_id,
                sku.exposure_id,
                sku.bundle,
                sku.sku_name,
                sku.link,
                sku.option_value,
                sku.linked_option,
                sku.barcode,
                sku.multiple_value,
                sku.package_unit_quantity,
                sku.cn_name,
                package_vinyl_spec_name,  # 변환된 이름 사용
                sku.en_name,
                sku.hs_code,
                sku.en_name_for_cn,
                sku.hs_code_cn,
                fta_name,
                sku.material,
                sku.length_mm,
                sku.width_mm,
                sku.height_mm,
                sku.weight_g,
                delivery_status_name,
                sku.sale_price,
                sku.cost_yuan,
                sku.cost_krw,
                sku.supply_price,
                sku.margin,
            ])

        # DataFrame 생성
        df = pd.DataFrame(data_list, columns=template_headers)

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            temp_path = tmp_file.name

        # 엑셀 파일로 저장
        df.to_excel(temp_path, index=False, sheet_name='SKU_Data')

        # 파일명 생성 (현재 날짜 포함)
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sku_data_{current_time}.xlsx"

        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"SKU 데이터 다운로드 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SKU 데이터 다운로드 중 오류가 발생했습니다: {str(e)}"
        )


async def upload_sku_excel(
        file: UploadFile,
        request: Request,
        db: Session
) -> common_response.ApiResponse[Union[dict, None]]:
    try:
        user_no, company_no = get_authenticated_user_no(request)

        # SKU 엑셀 파일의 예상 헤더 정의 (기존과 동일)
        expected_headers = [
            "SKU ID",
            '노출 ID',
            '상품명',
            '링크'
        ]

        # 컬럼 매핑 정의 (기존과 동일)
        column_mapping = {
            "SKU ID": "sku_id",
            "노출 ID": "exposure_id",
            "묶음": "bundle",
            "상품명": "sku_name",
            "옵션": "option_value",
            "연동옵션": "linked_option",
            "링크": "link",
            "바코드": "barcode",
            "판매 구성 수량": "multiple_value",
            "포장 개수": "package_unit_quantity",
            "중문명": "cn_name",
            "포장비닐규격": "package_vinyl_spec_cd",
            "영문명": "en_name",
            "HS코드번호": "hs_code",
            "영문명(중국용)": "en_name_for_cn",
            "HS코드번호(중국용)": "hs_code_cn",
            "FTA": "fta_cd",
            "재질": "material",
            "길이(mm)": "length_mm",
            "넓이(mm)": "width_mm",
            "높이(mm)": "height_mm",
            "중량(g)": "weight_g",
            "납품여부": "delivery_status_cd",
            "판매가격": "sale_price",
            "원가-위안화": "cost_yuan",
            "원가-원화": "cost_krw",
            "공급가": "supply_price",
            "마진": "margin",
        }

        reverse_column_mapping = {v: k for k, v in column_mapping.items()}
        price_fields = ["sale_price", "cost_yuan", "cost_krw", "supply_price"]
        integer_fields = ["multiple_value"]
        decimal_fields = [
            "length_mm", "width_mm", "height_mm", "weight_g",
            "margin", "sale_price", "cost_yuan", "cost_krw", "supply_price"
        ]
        exclude_from_db = ["linked_option"]

        # 엑셀 파일 읽기
        records = await common_service.read_excel_file(
            file,
            expected_headers=expected_headers,
            column_mapping=column_mapping,
        )

        # ✅ 성능 최적화 1: 기존 SKU 데이터를 미리 메모리에 로드
        print(f"기존 SKU 데이터 로드 시작... (회사: {company_no})")
        existing_skus_query = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.company_no == company_no,
            setting_models.SetSku.del_yn == 0
        ).all()

        # 딕셔너리로 변환하여 빠른 조회 가능하게 함
        existing_skus = {}
        existing_sku_barcodes = {}  # 바코드 검증용

        for sku in existing_skus_query:
            key = f"{sku.sku_id}_{sku.bundle}" if sku.bundle is not None else f"{sku.sku_id}_None"
            existing_skus[key] = sku

            # 바코드가 있는 SKU들 저장
            if sku.barcode:
                existing_sku_barcodes[sku.sku_id] = sku.barcode

        print(f"기존 SKU {len(existing_skus)}개 로드 완료")

        # ✅ 성능 최적화 2: 공통코드도 미리 로드
        vinyl_codes = com_code_util.get_com_code_dict_by_parent_code("PACKAGE_VINYL_SPEC_CD", db)
        fta_codes = com_code_util.get_com_code_dict_by_parent_code("FTA_CD", db)
        delivery_codes = com_code_util.get_com_code_dict_by_parent_code("DELIVERY_STATUS_CD", db)

        error_count = 0
        error_details = []
        duplicate_keys = set()
        file_sku_barcode_map = {}

        # 배치 처리용 리스트
        records_to_insert = []
        records_to_update = []

        # 각 레코드를 순회하며 검증 (DB 조회 없이)
        for index, record in enumerate(records):
            try:
                # 진행 상황 출력 (1000개마다)
                if (index + 1) % 1000 == 0:
                    print(f"검증 진행: {index + 1}/{len(records)}")

                sku_id = record.get("sku_id")
                bundle = record.get("bundle")
                barcode = record.get("barcode")
                record["company_no"] = company_no

                row_has_error = False

                # SKU ID 검증 (기존 로직)
                if sku_id is None or pd.isna(sku_id) or str(sku_id).strip() == "":
                    error_count += 1
                    sku_id_field_name = reverse_column_mapping.get("sku_id", "SKU ID")
                    file_util.add_error(error_details, index, f"{sku_id_field_name}는 필수 입력 항목입니다.")
                    row_has_error = True
                else:
                    # SKU ID 형식 검증 (기존 로직 유지)
                    sku_id_str = str(sku_id).strip()
                    if '.' in sku_id_str:
                        try:
                            sku_id_float = float(sku_id_str)
                            if sku_id_float.is_integer():
                                sku_id_str = str(int(sku_id_float))
                            else:
                                raise ValueError("소수점이 포함된 SKU ID는 허용되지 않습니다.")
                        except ValueError:
                            error_count += 1
                            sku_id_field_name = reverse_column_mapping.get("sku_id", "SKU ID")
                            file_util.add_error(error_details, index,
                                                f"{sku_id_field_name}는 8자리 숫자여야 합니다. (현재값: {sku_id})")
                            row_has_error = True

                    if not (sku_id_str.isdigit() and len(sku_id_str) == 8):
                        error_count += 1
                        sku_id_field_name = reverse_column_mapping.get("sku_id", "SKU ID")
                        file_util.add_error(error_details, index, f"{sku_id_field_name}는 8자리 숫자여야 합니다. (현재값: {sku_id})")
                        row_has_error = True
                    else:
                        record["sku_id"] = sku_id_str
                        sku_id = sku_id_str

                # ✅ 바코드 검증 최적화 (메모리에서 조회)
                if barcode and str(barcode).strip() != '' and not pd.isna(barcode):
                    barcode = str(barcode).strip()

                    # 파일 내 일관성 검증
                    if sku_id in file_sku_barcode_map:
                        existing_barcode = file_sku_barcode_map[sku_id]
                        if existing_barcode != barcode:
                            error_count += 1
                            barcode_field_name = reverse_column_mapping.get("barcode", "바코드")
                            file_util.add_error(
                                error_details,
                                index,
                                f"SKU ID '{sku_id}'의 {barcode_field_name}가 일치하지 않습니다. "
                            )
                            row_has_error = True
                    else:
                        file_sku_barcode_map[sku_id] = barcode

                    # ✅ DB 바코드 검증도 메모리에서 처리
                    if sku_id and not row_has_error:
                        existing_barcode = existing_sku_barcodes.get(sku_id)
                        if existing_barcode and existing_barcode != barcode:
                            error_count += 1
                            barcode_field_name = reverse_column_mapping.get("barcode", "바코드")
                            file_util.add_error(
                                error_details,
                                index,
                                f"SKU ID '{sku_id}'는 이미 다른 {barcode_field_name}('{existing_barcode}')로 등록되어 있습니다. "
                                f"입력된 {barcode_field_name}: '{barcode}'"
                            )
                            row_has_error = True
                        elif not barcode and existing_barcode:
                            record["barcode"] = existing_barcode

                    record["barcode"] = barcode
                else:
                    # 기존 바코드가 있으면 사용
                    if sku_id and sku_id in existing_sku_barcodes:
                        record["barcode"] = existing_sku_barcodes[sku_id]
                    else:
                        record["barcode"] = None

                # ✅ 공통코드 검증도 메모리에서 처리
                package_vinyl_spec_name = record.get("package_vinyl_spec_cd")
                if package_vinyl_spec_name and str(package_vinyl_spec_name).strip() != '':
                    code_found = False
                    for code, code_info in vinyl_codes.items():
                        if code_info.code_name == package_vinyl_spec_name:
                            record["package_vinyl_spec_cd"] = code
                            code_found = True
                            break

                    if not code_found:
                        error_count += 1
                        file_util.add_error(error_details, index, f"포장비닐규격 '{package_vinyl_spec_name}'을 찾을 수 없습니다.")
                        row_has_error = True

                # FTA 코드 검증
                fta_name = record.get("fta_cd")
                if fta_name and str(fta_name).strip() != '':
                    code_found = False
                    for code, code_info in fta_codes.items():
                        if code_info.code_name == fta_name:
                            record["fta_cd"] = code
                            code_found = True
                            break

                    if not code_found:
                        error_count += 1
                        file_util.add_error(error_details, index, f"FTA '{fta_name}'을 찾을 수 없습니다.")
                        row_has_error = True
                else:
                    record["fta_cd"] = None

                # 납품여부 코드 검증
                delivery_status_name = record.get("delivery_status_cd")
                if delivery_status_name and str(delivery_status_name).strip() != '':
                    code_found = False
                    for code, code_info in delivery_codes.items():
                        if code_info.code_name == delivery_status_name:
                            record["delivery_status_cd"] = code
                            code_found = True
                            break

                    if not code_found:
                        error_count += 1
                        file_util.add_error(error_details, index, f"납품여부 '{delivery_status_name}'을 찾을 수 없습니다.")
                        row_has_error = True
                else:
                    record["delivery_status_cd"] = None

                # 나머지 검증 로직 (기존과 동일)
                for field in price_fields:
                    if field in record:
                        record[field] = file_util.clean_price_field(record[field])

                for field in integer_fields:
                    if field in record and record[field] is not None:
                        value = record[field]
                        if not pd.isna(value) and str(value).strip() != "":
                            try:
                                if isinstance(value, str):
                                    value = value.strip()
                                    if not value.replace('-', '').replace('.', '').isdigit():
                                        field_name = reverse_column_mapping.get(field)
                                        raise ValueError(f"{field_name}는 정수만 입력 가능합니다.")
                                record[field] = int(float(value))
                            except (ValueError, TypeError):
                                error_count += 1
                                field_name = reverse_column_mapping.get(field)
                                file_util.add_error(error_details, index, f"{field_name}는 정수만 입력 가능합니다. (현재값: {value})")
                                row_has_error = True

                for field in decimal_fields:
                    if field in record and record[field] is not None:
                        value = record[field]
                        if not pd.isna(value) and str(value).strip() != "":
                            try:
                                if isinstance(value, str):
                                    value = value.strip()
                                    try:
                                        float(value)
                                    except ValueError:
                                        field_name = reverse_column_mapping.get(field)
                                        raise ValueError(f"{field_name}는 숫자만 입력 가능합니다.")
                                record[field] = float(value)
                            except (ValueError, TypeError):
                                error_count += 1
                                field_name = reverse_column_mapping.get(field)
                                file_util.add_error(error_details, index, f"{field_name}는 숫자만 입력 가능합니다. (현재값: {value})")
                                row_has_error = True

                if row_has_error:
                    continue

                # DB에 저장하지 않는 필드들 제거
                for field in exclude_from_db:
                    if field in record:
                        del record[field]

                # 묶음 처리
                if pd.isna(bundle) or str(bundle).strip() == "" or bundle == 'nan':
                    bundle = None
                    key = f"{sku_id}_None"
                else:
                    try:
                        bundle = int(float(bundle))
                        key = f"{sku_id}_{bundle}"
                    except (ValueError, TypeError):
                        error_count += 1
                        bundle_field_name = reverse_column_mapping.get("bundle", "묶음")
                        file_util.add_error(error_details, index, f"{bundle_field_name}은 숫자만 입력 가능합니다. (현재값: {bundle})")
                        continue

                # 파일 내 중복 키 검증
                if key in duplicate_keys:
                    error_count += 1
                    file_util.add_error(error_details, index, f"중복된 키입니다. (SKU ID: {sku_id}, 묶음: {bundle})")
                    continue

                duplicate_keys.add(key)
                record["bundle"] = bundle

                # 기존 데이터 확인도 메모리에서 처리
                if key in existing_skus:
                    # 업데이트 대상
                    existing_sku = existing_skus[key]

                    # 링크 변경 여부 확인
                    existing_link = existing_sku.link
                    new_link = record.get("link")
                    link_changed = (new_link != existing_link)

                    # 업데이트 정보 저장
                    update_info = {
                        'sku_object': existing_sku,
                        'record': record,
                        'link_changed': link_changed,
                        'user_no': user_no
                    }
                    records_to_update.append(update_info)
                else:
                    # 신규 삽입 대상
                    record['created_by'] = user_no
                    record['created_at'] = datetime.now()
                    records_to_insert.append(record)

            except Exception as row_error:
                error_count += 1
                error_details.append(f"행 {index + 2}: {str(row_error)}")
                continue

        print(f"검증 완료. 삽입: {len(records_to_insert)}개, 업데이트: {len(records_to_update)}개")

        # 유효성 검사
        if error_details:
            return file_util.handle_error(
                db=db,
                message="엑셀 데이터 처리 중 오류가 발생했습니다.",
                error_details=error_details,
                error_count=len(error_details)
            )


        # 신규 데이터 일괄 삽입, 배치 처리로 DB 작업 최적화
        if records_to_insert:
            print(f"신규 데이터 {len(records_to_insert)}개 삽입 중...")
            db.bulk_insert_mappings(setting_models.SetSku, records_to_insert)

        # 기존 데이터 업데이트
        if records_to_update:
            print(f"기존 데이터 {len(records_to_update)}개 업데이트 중...")
            for update_info in records_to_update:
                existing_sku = update_info['sku_object']
                record = update_info['record']
                link_changed = update_info['link_changed']
                user_no = update_info['user_no']

                # 모든 필드 업데이트
                for field, value in record.items():
                    if hasattr(existing_sku, field):
                        setattr(existing_sku, field, value)

                # 링크가 변경된 경우 연동 관련 필드들 초기화
                if link_changed:
                    existing_sku.linked_option = None
                    existing_sku.linked_spec_id = None
                    existing_sku.linked_sku_id = None
                    existing_sku.linked_open_uid = None
                    existing_sku.option_type = "MANUAL"

                existing_sku.updated_by = user_no
                existing_sku.updated_at = datetime.now()

        db.commit()
        print("DB 작업 완료!")

        return common_response.ResponseBuilder.success(
            data=None,
            message=f"SKU 엑셀 파일이 성공적으로 업로드되었습니다. (신규: {len(records_to_insert)}개, 업데이트: {len(records_to_update)}개)"
        )

    except Exception as e:
        db.rollback()
        return file_util.handle_error(
            db=db,
            message="엑셀 데이터 처리 중 오류가 발생했습니다.",
            error_details=[{str(e)}],
            error_count=1
        )

# SKU 이미지 업로드 (단일)
async def upload_sku_image(
        sku_no: Union[str, int],
        file: UploadFile,
        request: Request,
        db: Session
) -> common_response.ApiResponse[Union[dict, None]]:
    try:
        user_no, company_no = get_authenticated_user_no(request)

        # SKU 존재 확인
        existing_sku = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.sku_no == sku_no,
            setting_models.SetSku.company_no == company_no,
            setting_models.SetSku.del_yn == 0
        ).first()

        if not existing_sku:
            raise HTTPException(
                status_code=400,
                detail=f"SKU {sku_no}를 찾을 수 없습니다."
            )

        # 파일 유효성 검사
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="이미지 파일만 업로드 가능합니다.",
            )

        # 파일 크기 제한 (예: 10MB)
        max_file_size = 10 * 1024 * 1024  # 10MB
        file_content = await file.read()
        if len(file_content) > max_file_size:
            raise HTTPException(
                status_code=400,
                detail="파일 크기는 10MB를 초과할 수 없습니다."
            )

        # 환경변수 기반 경로 설정
        current_os = platform.system().lower()
        if current_os in ['darwin', 'windows']:  # 로컬 개발환경
            upload_dir = "./uploads/images/sku"
            web_path_prefix = "/static/images/sku"
        else:  # 서버 환경 (Linux)
            # 환경변수에서 경로 가져오기
            upload_dir = os.getenv('SKU_IMAGE_PATH', '/var/www/uploads/images/sku')
            web_path_prefix = "/uploads/images/sku"

        os.makedirs(upload_dir, exist_ok=True)

        # 파일명 생성 (sku_id와 bundle 기반)
        bundle_suffix = f"_{existing_sku.bundle}" if existing_sku.bundle is not None else ""
        file_extension = os.path.splitext(file.filename)[1]
        safe_filename = f"{existing_sku.sku_id}{bundle_suffix}{file_extension}"
        file_path = os.path.join(upload_dir, safe_filename)

        # 파일 저장
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        # 웹 접근 가능한 경로 생성
        web_accessible_path = f"{web_path_prefix}/{safe_filename}"

        # DB의 image_path 필드 업데이트
        existing_sku.image_path = web_accessible_path
        existing_sku.updated_by = user_no
        existing_sku.updated_at = datetime.now()

        db.commit()
        db.refresh(existing_sku)

        data = {
            "sku_no": sku_no,
            "original_filename": file.filename,
            "saved_filename": safe_filename,
            "file_path": file_path,
            "image_path": web_accessible_path,
            "file_size": len(file_content),
            "content_type": file.content_type,
            "uploaded_at": datetime.now(),
            "uploaded_by": user_no
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="이미지가 성공적으로 업로드되었습니다."
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"이미지 업로드 중 오류가 발생했습니다: {str(e)}"
        )

# 수정된 get_sku_image 함수
def fetch_sku_image(
        sku_no: int,
        request: Request,
        db: Session
) -> common_response.ApiResponse[Union[dict, None]]:
    """SKU의 첫 번째 이미지 정보 반환"""
    try:
        # 인증 정보 가져오기
        user_no, company_no = get_authenticated_user_no(request)

        # SKU 정보 조회 (회사 필터 추가)
        sku = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.sku_no == sku_no,
            setting_models.SetSku.company_no == company_no,
            setting_models.SetSku.del_yn == 0
        ).first()

        if not sku:
            raise HTTPException(
                status_code=400,
                detail="SKU를 찾을 수 없습니다."
            )

        # 환경변수 기반 설정
        current_os = platform.system().lower()
        if current_os in ['darwin', 'windows']:  # 로컬 개발환경
            base_url = "http://localhost:8000"
            file_base_path = "./uploads"
        else:  # 서버 환경 (Linux)
            # 환경변수에서 URL과 경로 가져오기
            base_url = os.getenv('NEWALL_BACKEND_URL', 'https://9newall.com')
            file_base_path = os.getenv('SKU_IMAGE_PATH', '/var/www/uploads/images/sku').replace('/images/sku', '')

        # 이미지 정보 기본 구조
        result = {
            "sku_no": sku_no,
            "has_image": False,
            "image_path": None,
            "full_image_url": None,  # 전체 URL 추가
            "file_exists": False,
            "file_path": None,
            "file_size": 0,
            "message": "등록된 이미지가 없습니다.",
        }

        # image_path이 없거나 빈 문자열인 경우
        if not sku.image_path or sku.image_path.strip() == "":
            return common_response.ResponseBuilder.success(
                data=result,
                message="이미지 정보 조회가 완료되었습니다."
            )

        # 첫 번째 이미지 경로 추출
        first_image_path = sku.image_path.split(',')[0].strip()

        if not first_image_path:
            return common_response.ResponseBuilder.success(
                data=result,
                message="이미지 정보 조회가 완료되었습니다."
            )

        # 이미지 경로가 존재함
        result["has_image"] = True
        result["image_path"] = first_image_path

        # 전체 URL 생성
        if current_os in ['darwin', 'windows']:  # 로컬
            result["full_image_url"] = f"{base_url}{first_image_path}"
        else:  # 서버
            result["full_image_url"] = f"{base_url}{first_image_path}"

        # 실제 파일 경로 변환
        if current_os in ['darwin', 'windows']:
            file_path = first_image_path.replace('/static/', f'{file_base_path}/')
        else:
            file_path = first_image_path.replace('/uploads/', f'{file_base_path}/')

        result["file_path"] = file_path

        # 파일 존재 확인
        if os.path.exists(file_path):
            result["file_exists"] = True
            result["file_size"] = os.path.getsize(file_path)
            result["message"] = "이미지가 존재합니다."
        else:
            result["message"] = "이미지 경로는 등록되어 있으나 파일이 존재하지 않습니다."

        return common_response.ResponseBuilder.success(
            data=result,
            message="이미지 정보 조회가 완료되었습니다."
        )

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400,
            detail=f"이미지 정보 조회 중 오류가 발생했습니다: {str(e)}",
        )

# SKU 이미지 삭제
def delete_sku_image(
        sku_no: Union[str, int],
        request: Request,
        db: Session
) -> common_response.ApiResponse[Union[dict, None]]:
    """SKU의 이미지를 삭제하고 DB에서 image_path를 None으로 설정"""
    try:
        user_no, company_no = get_authenticated_user_no(request)

        # SKU 존재 확인
        existing_sku = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.sku_no == sku_no,
            setting_models.SetSku.company_no == company_no,
            setting_models.SetSku.del_yn == 0
        ).first()

        if not existing_sku:
            raise HTTPException(
                status_code=400,
                detail=f"SKU {sku_no}를 찾을 수 없습니다."
            )

        # 삭제할 이미지 경로 저장
        deleted_image_path = existing_sku.image_path or ""

        if existing_sku.image_path and existing_sku.image_path.strip():
            # 환경변수 기반 실제 파일 경로 설정
            current_os = platform.system().lower()

            if current_os in ['darwin', 'windows']:
                file_path = existing_sku.image_path.replace('/static/', './uploads/')
            else:
                file_base_path = os.getenv('SKU_IMAGE_PATH', '/var/www/uploads/images/sku').replace('/images/sku', '')
                file_path = existing_sku.image_path.replace('/uploads/', f'{file_base_path}/')

            # 파일 삭제 시도
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as file_error:
                    print(f"파일 삭제 실패: {file_path}, 오류: {str(file_error)}")

        # DB에서 image_path를 None으로 설정
        existing_sku.image_path = None
        existing_sku.updated_by = user_no
        existing_sku.updated_at = datetime.now()

        db.commit()
        db.refresh(existing_sku)

        data = {
            "image_path": deleted_image_path
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="SKU 이미지가 성공적으로 삭제되었습니다."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"이미지 삭제 중 오류가 발생했습니다: {str(e)}"
        )


def fetch_center_list(
        request: Request,
        db: Session
) -> common_response.ApiResponse[Union[dict, None]]:
    """센터 목록 조회"""
    try:
        user_no, company_no = get_authenticated_user_no(request)

        # 센터 목록 조회 (회사별, 삭제되지 않은 것만)
        centers = db.query(setting_models.SetCenter).filter(
            setting_models.SetCenter.company_no == company_no,
            setting_models.SetCenter.del_yn == 0
        ).order_by(desc(setting_models.SetCenter.center_no)).all()

        # 센터 데이터를 dict 리스트로 변환
        center_list = [CenterBase.from_orm(center) for center in centers]

        data = {
            "centers": center_list,
            "total_count": len(center_list)
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="센터 목록 조회가 완료되었습니다."
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"센터 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


def create_user(
        user_info: UserBase,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """사용자 생성"""
    try:
        current_user_no, company_no = get_authenticated_user_no(request)

        # 필수 필드 검증
        if not user_info.user_id or not user_info.user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="사용자 ID는 필수 입력 항목입니다."
            )

        if not user_info.user_email or not str(user_info.user_email).strip():
            raise HTTPException(
                status_code=400,
                detail="이메일은 필수 입력 항목입니다."
            )

        if not user_info.user_password or not user_info.user_password.strip():
            raise HTTPException(
                status_code=400,
                detail="비밀번호는 필수 입력 항목입니다."
            )

        if not user_info.user_name or not user_info.user_name.strip():
            raise HTTPException(
                status_code=400,
                detail="사용자 이름은 필수 입력 항목입니다."
            )

        # 비밀번호 길이 검증
        if len(user_info.user_password) < 8:
            raise HTTPException(
                status_code=400,
                detail="비밀번호는 8자 이상이어야 합니다."
            )

        # 중복 체크 - user_id
        existing_user_by_id = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_id == user_info.user_id.strip()
        ).first()

        if existing_user_by_id:
            raise HTTPException(
                status_code=400,
                detail=f"이미 사용중인 아이디입니다: {user_info.user_id}"
            )

        # 중복 체크 - user_email
        encrypted_input_email = crypto_util.encrypt(str(user_info.user_email).strip())

        existing_user_by_email = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_email == encrypted_input_email
        ).first()

        if existing_user_by_email:
            raise HTTPException(
                status_code=400,
                detail=f"이미 등록된 이메일입니다: {user_info.user_email}"
            )

        # Pydantic 모델을 dict로 변환
        user_dict = user_info.dict(exclude_unset=True,
                                   exclude={'user_no', 'company_name', 'user_status_name', 'user_role_name'})

        # 개인정보 암호화
        encrypted_name = crypto_util.encrypt(user_info.user_name.strip())
        encrypted_email = crypto_util.encrypt(str(user_info.user_email).strip())
        encrypted_contact = crypto_util.encrypt(user_info.contact.strip()) if user_info.contact else None

        # 비밀번호 해싱
        hashed_password = hash_password(user_info.user_password)

        # 암호화된 데이터로 교체
        user_dict['user_name'] = encrypted_name
        user_dict['user_email'] = encrypted_email
        user_dict['user_password'] = hashed_password
        if encrypted_contact:
            user_dict['contact'] = encrypted_contact

        # 회사 번호 설정
        if not user_dict.get('company_no'):
            user_dict['company_no'] = company_no

        # 사용자 상태 설정 (기본값)
        if not user_dict.get('user_status_cd'):
            user_dict['user_status_cd'] = 'PENDING'

        # 관리자 페이지에서 만든 사용자는 바로 승인
        user_dict["approval_yn"] = 1

        # 새 사용자 생성
        new_user = auth_models.ComUser(**user_dict)

        db.add(new_user)
        db.flush()  # user_no를 얻기 위해 flush

        # ComUserCompany에 레코드 추가
        if new_user.company_no:
            new_user_company = auth_models.ComUserCompany(
                user_no=new_user.user_no,
                company_no=new_user.company_no
            )
            db.add(new_user_company)

        # 회사 정보 조회 및 메뉴 설정
        platform_type_cd = None
        added_menus_count = 0

        if new_user.company_no:
            company = db.query(auth_models.ComCompany).filter(
                auth_models.ComCompany.company_no == new_user.company_no
            ).first()

            if company and hasattr(company, 'platform_type_cd'):
                platform_type_cd = company.platform_type_cd

            # 메뉴 조회 (basic_yn = 1 또는 platform_type_cd 매칭)
            menu_query = db.query(auth_models.ComMenu).filter(
                or_(
                    auth_models.ComMenu.basic_yn == 1,
                    auth_models.ComMenu.platform_type_cd == platform_type_cd if platform_type_cd else False
                )
            )

            menus = menu_query.all()

            # 사용자 메뉴 등록
            for menu in menus:
                new_user_menu = auth_models.ComUserMenu(
                    user_no=new_user.user_no,
                    menu_no=menu.menu_no,
                    company_no=new_user.company_no
                )
                db.add(new_user_menu)
                added_menus_count += 1

        db.commit()
        db.refresh(new_user)

        # 응답 데이터
        data = {
            "user_no": new_user.user_no,
            "user_id": new_user.user_id,
            "user_email": user_info.user_email,
            "user_name": user_info.user_name,
            "contact": user_info.contact,
            "user_status_cd": new_user.user_status_cd,
            "company_no": new_user.company_no,
            "platform_type_cd": platform_type_cd,
            "added_menus_count": added_menus_count,
            "created_at": new_user.created_at
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="사용자가 성공적으로 등록되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"사용자 생성 중 오류가 발생했습니다: {str(e)}"
        )

def fetch_user_list(
        filter: UserFilterRequest,
        db: Session = Depends(get_db),
        pagination: PaginationRequest = Depends()
) -> common_response.ApiResponse[Union[common_response.PageResponse[UserBase], None]]:
    """사용자 목록 조회"""
    try:
        # 사용자 상태 공통코드 미리 조회
        user_status_codes = com_code_util.get_com_code_dict_by_parent_code("USER_STATUS_CD", db)
        user_role_codes = com_code_util.get_com_code_dict_by_parent_code("USER_ROLE_CD", db)

        # 기본 쿼리 (회사 정보 JOIN 추가)
        query = db.query(
            auth_models.ComUser,
            auth_models.ComCompany.company_name
        ).outerjoin(
            auth_models.ComCompany,
            auth_models.ComUser.company_no == auth_models.ComCompany.company_no
        )

        # UserFilterRequest 조건 동적 적용
        # user_id는 암호화되지 않으므로 LIKE 검색 가능
        if filter.user_id:
            query = query.filter(auth_models.ComUser.user_id.like(f"%{filter.user_id.strip()}%"))

        # 이메일, 이름, 연락처는 암호화되어 있어 LIKE 검색 불가
        # 필요시 모든 데이터를 가져와서 복호화 후 필터링해야 함
        if filter.user_email or filter.user_name or filter.contact:
            # 암호화된 필드 검색은 성능상 문제가 있을 수 있음
            # 전체 데이터를 가져와서 메모리에서 필터링하거나
            # 검색 기능을 제한하는 것을 권장
            pass

        if filter.user_status_cd:
            query = query.filter(auth_models.ComUser.user_status_cd == filter.user_status_cd)

        # 정렬 (최신 순)
        query = query.order_by(desc(auth_models.ComUser.user_no))

        # 전체 개수 계산 (JOIN 없이)
        count_query = db.query(auth_models.ComUser)

        if filter.user_id:
            count_query = count_query.filter(auth_models.ComUser.user_id.like(f"%{filter.user_id.strip()}%"))

        if filter.user_status_cd:
            count_query = count_query.filter(auth_models.ComUser.user_status_cd == filter.user_status_cd)

        # company_no 필터 적용 (리스트가 비어있지 않은 경우)
        if filter.company_no and len(filter.company_no) > 0:
            query = query.filter(auth_models.ComUser.company_no.in_(filter.company_no))

        total_elements = count_query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 결과를 딕셔너리 리스트로 변환 (복호화, 비밀번호 제외)
        user_list = []
        for result in results:
            # result에서 User와 company_name 추출
            user = result[0]
            company_name = result[1]

            # 개인정보 복호화
            decrypted_name = crypto_util.decrypt(user.user_name) if user.user_name else None
            decrypted_email = crypto_util.decrypt(user.user_email) if user.user_email else None
            decrypted_contact = crypto_util.decrypt(user.contact) if user.contact else None

            # 사용자 상태 코드명 변환
            user_status_name = None
            if user.user_status_cd and user_status_codes:
                status_code = user_status_codes.get(user.user_status_cd)
                if status_code:
                    user_status_name = status_code.code_name

            # 사용자 권한 코드명 변환
            user_role_name = None
            if user.user_role_cd and user_role_codes:
                role_code = user_role_codes.get(user.user_role_cd)
                if role_code:
                    user_role_name = role_code.code_name

            user_dict = {
                "user_no": user.user_no,
                "user_id": user.user_id,
                "user_email": decrypted_email,
                "user_name": decrypted_name,
                "contact": decrypted_contact,
                "user_status_cd": user.user_status_cd,
                "user_status_name": user_status_name,
                "user_role_cd": user.user_role_cd,
                "user_role_name": user_role_name,
                "approval_yn": user.approval_yn,
                "company_no": user.company_no,
                "company_name": company_name,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
            user_list.append(user_dict)

        return common_response.ResponseBuilder.paged_success(
            content=user_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except Exception as e:
        print(str(e))
        raise HTTPException(
            status_code=400,
            detail=f"사용자 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )

def fetch_user(
        user_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """사용자 상세 조회"""
    try:
        # 사용자 조회
        user = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_no == user_no
        ).first()

        if not user:
            raise HTTPException(
                status_code=400,
                detail=f"ID {user_no}에 해당하는 사용자를 찾을 수 없습니다."
            )

        # 개인정보 복호화
        decrypted_name = crypto_util.decrypt(user.user_name) if user.user_name else None
        decrypted_email = crypto_util.decrypt(user.user_email) if user.user_email else None
        decrypted_contact = crypto_util.decrypt(user.contact) if user.contact else None

        # 사용자 데이터를 dict로 변환 (비밀번호 제외)
        data = {
            "user_no": user.user_no,
            "user_id": user.user_id,
            "user_email": decrypted_email,
            "user_name": decrypted_name,
            "contact": decrypted_contact,
            "user_status_cd": user.user_status_cd,
            "company_no": user.company_no,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="사용자 상세 조회가 완료되었습니다."
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"사용자 조회 중 오류가 발생했습니다: {str(e)}"
        )


def update_user(
        user_info: UserBase,
        user_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """사용자 수정"""
    try:
        # 업데이트할 사용자 찾기
        existing_user = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_no == user_no
        ).first()

        if not existing_user:
            raise HTTPException(
                status_code=400,
                detail=f"ID {user_no}에 해당하는 사용자를 찾을 수 없습니다."
            )

        # Pydantic 모델을 dict로 변환
        update_dict = user_info.dict(exclude_unset=True,
                                     exclude={'user_no', 'company_name', 'user_status_name', 'user_role_name'})

        # 업데이트할 필드가 있는지 확인
        if not update_dict:
            raise HTTPException(
                status_code=400,
                detail="업데이트할 필드가 없습니다."
            )

        # user_id 중복 체크 (자기 자신 제외)
        if 'user_id' in update_dict:
            duplicate_user_id = db.query(auth_models.ComUser).filter(
                auth_models.ComUser.user_id == update_dict['user_id'],
                auth_models.ComUser.user_no != user_no
            ).first()

            if duplicate_user_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"이미 사용중인 아이디입니다: {update_dict['user_id']}"
                )

        # user_email 중복 체크
        if 'user_email' in update_dict:
            encrypted_email = crypto_util.encrypt(update_dict['user_email'])
            duplicate_email = db.query(auth_models.ComUser).filter(
                auth_models.ComUser.user_email == encrypted_email,
                auth_models.ComUser.user_no != user_no
            ).first()

            if duplicate_email:
                raise HTTPException(
                    status_code=400,
                    detail=f"이미 등록된 이메일입니다: {update_dict['user_email']}"
                )

            update_dict['user_email'] = encrypted_email

        # 이름 암호화
        if 'user_name' in update_dict:
            update_dict['user_name'] = crypto_util.encrypt(update_dict['user_name'])

        # 연락처 암호화
        if 'contact' in update_dict:
            update_dict['contact'] = crypto_util.encrypt(update_dict['contact'])

        # 비밀번호가 있으면 검증 후 해싱
        if 'user_password' in update_dict and update_dict['user_password']:
            if len(update_dict['user_password']) < 8:
                raise HTTPException(
                    status_code=400,
                    detail="비밀번호는 8자 이상이어야 합니다."
                )
            update_dict['user_password'] = hash_password(update_dict['user_password'])

        # 원본 데이터 저장 (응답용)
        original_data = {
            'user_email': user_info.user_email if user_info.user_email else None,
            'user_name': user_info.user_name if user_info.user_name else None,
            'contact': user_info.contact if user_info.contact else None
        }

        # company_no 변경 체크
        company_changed = False
        old_company_no = existing_user.company_no
        new_company_no = update_dict.get('company_no')

        if 'company_no' in update_dict and old_company_no != new_company_no:
            company_changed = True

        # 기존 레코드 업데이트
        for field, value in update_dict.items():
            if hasattr(existing_user, field):
                setattr(existing_user, field, value)

        # updated_at 필드 업데이트
        if hasattr(existing_user, 'updated_at'):
            existing_user.updated_at = datetime.now()

        # company_no가 변경된 경우
        platform_type_cd = None
        added_menus_count = 0

        if company_changed:
            # 기존 ComUserCompany 레코드 삭제
            if old_company_no:
                db.query(auth_models.ComUserCompany).filter(
                    auth_models.ComUserCompany.user_no == user_no,
                    auth_models.ComUserCompany.company_no == old_company_no
                ).delete()

            # 기존 ComUserMenu 레코드 삭제 (모든 메뉴 권한 삭제)
            db.query(auth_models.ComUserMenu).filter(
                auth_models.ComUserMenu.user_no == user_no
            ).delete()

            # 새 ComUserCompany 레코드 추가
            if new_company_no:
                # 중복 체크
                existing_user_company = db.query(auth_models.ComUserCompany).filter(
                    auth_models.ComUserCompany.user_no == user_no,
                    auth_models.ComUserCompany.company_no == new_company_no
                ).first()

                if not existing_user_company:
                    new_user_company = auth_models.ComUserCompany(
                        user_no=user_no,
                        company_no=new_company_no
                    )
                    db.add(new_user_company)

                # 새 회사 정보 조회
                company = db.query(auth_models.ComCompany).filter(
                    auth_models.ComCompany.company_no == new_company_no
                ).first()

                if company and hasattr(company, 'platform_type_cd'):
                    platform_type_cd = company.platform_type_cd

                # 메뉴 조회 (basic_yn = 1 또는 platform_type_cd 매칭)
                menu_query = db.query(auth_models.ComMenu).filter(
                    or_(
                        auth_models.ComMenu.basic_yn == 1,
                        auth_models.ComMenu.platform_type_cd == platform_type_cd if platform_type_cd else False
                    )
                )

                menus = menu_query.all()

                # 새 사용자 메뉴 등록
                for menu in menus:
                    new_user_menu = auth_models.ComUserMenu(
                        user_no=user_no,
                        menu_no=menu.menu_no,
                        company_no=new_company_no
                    )
                    db.add(new_user_menu)
                    added_menus_count += 1

        db.commit()
        db.refresh(existing_user)

        # 업데이트된 데이터 반환
        data = {
            "user_no": existing_user.user_no,
            "user_id": existing_user.user_id,
            "user_email": original_data['user_email'],
            "user_name": original_data['user_name'],
            "contact": original_data['contact'],
            "user_status_cd": existing_user.user_status_cd,
            "company_no": existing_user.company_no,
            "company_changed": company_changed,
            "platform_type_cd": platform_type_cd if company_changed else None,
            "added_menus_count": added_menus_count if company_changed else 0,
            "updated_at": existing_user.updated_at,
            "updated_fields": list(update_dict.keys())
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="사용자가 성공적으로 수정되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"사용자 수정 중 오류가 발생했습니다: {str(e)}"
        )

def delete_user(
        user_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """사용자 삭제 (물리적 삭제)"""
    try:
        current_user_no, company_no = get_authenticated_user_no(request)

        # 본인 삭제 방지
        if current_user_no == user_no:
            raise HTTPException(
                status_code=400,
                detail="본인 계정은 삭제할 수 없습니다."
            )

        # 삭제할 사용자 찾기
        user = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_no == user_no
        ).first()

        if not user:
            raise HTTPException(
                status_code=400,
                detail=f"삭제할 수 없는 사용자입니다. (ID: {user_no})"
            )

        # 물리적 삭제
        db.delete(user)
        db.commit()

        data = {
            "user_no": user_no,
            "deleted": True
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="사용자가 성공적으로 삭제되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"사용자 삭제 중 오류가 발생했습니다: {str(e)}"
        )

def create_company(
        company_info: CompanyBase,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """회사 생성"""
    try:
        current_user_no, _ = get_authenticated_user_no(request)

        # 필수 필드 검증
        if not company_info.company_name or not company_info.company_name.strip():
            raise HTTPException(
                status_code=400,
                detail="회사 이름은 필수 입력 항목입니다."
            )

        # 중복 체크 - company_name
        existing_company_by_name = db.query(auth_models.ComCompany).filter(
            auth_models.ComCompany.company_name == company_info.company_name.strip()
        ).first()

        if existing_company_by_name:
            raise HTTPException(
                status_code=400,
                detail=f"이미 존재하는 회사명입니다: {company_info.company_name}"
            )

        # 쿠팡 벤더아이디 중복 체크 (있는 경우만)
        if company_info.coupang_vendor_id and company_info.coupang_vendor_id.strip():
            existing_vendor = db.query(auth_models.ComCompany).filter(
                auth_models.ComCompany.coupang_vendor_id == company_info.coupang_vendor_id.strip()
            ).first()

            if existing_vendor:
                raise HTTPException(
                    status_code=400,
                    detail=f"이미 등록된 쿠팡 판매자코드입니다: {company_info.coupang_vendor_id}"
                )

        # Pydantic 모델을 dict로 변환
        company_dict = company_info.dict(exclude_unset=True, exclude={'company_no', 'company_status_name'})

        # 회사 상태 설정 (기본값)
        if not company_dict.get('company_status_cd'):
            company_dict['company_status_cd'] = 'ACTIVE'

        # 새 회사 생성
        new_company = auth_models.ComCompany(**company_dict)

        db.add(new_company)
        db.commit()
        db.refresh(new_company)

        # 응답 데이터
        data = {
            "company_no": new_company.company_no,
            "company_name": new_company.company_name,
            "coupang_vendor_id": new_company.coupang_vendor_id,
            "business_registration_number": new_company.business_registration_number,
            "company_status_cd": new_company.company_status_cd,
            "address": new_company.address,
            "address_dtl": new_company.address_dtl,
            "created_at": new_company.created_at
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="회사가 성공적으로 등록되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"회사 생성 중 오류가 발생했습니다: {str(e)}"
        )


def fetch_company_list(
        request: Request,
        filter: CompanyFilterRequest,
        db: Session = Depends(get_db),
        pagination: PaginationRequest = Depends()
) -> common_response.ApiResponse[Union[common_response.PageResponse[CompanyBase], None]]:
    """회사 목록 조회"""
    try:
        # 회사 상태 공통코드 미리 조회
        company_status_codes = com_code_util.get_com_code_dict_by_parent_code("COMPANY_STATUS_CD", db)

        # 기본 쿼리
        query = db.query(auth_models.ComCompany)

        # CompanyFilterRequest 조건 동적 적용 (LIKE 검색)
        if filter.company_name:
            query = query.filter(auth_models.ComCompany.company_name.like(f"%{filter.company_name.strip()}%"))

        if filter.coupang_vendor_id:
            query = query.filter(auth_models.ComCompany.coupang_vendor_id.like(f"%{filter.coupang_vendor_id.strip()}%"))

        if filter.business_registration_number:
            query = query.filter(auth_models.ComCompany.business_registration_number.like(f"%{filter.business_registration_number.strip()}%"))

        if filter.address:
            query = query.filter(auth_models.ComCompany.address.like(f"%{filter.address.strip()}%"))

        if filter.company_status_cd:
            query = query.filter(auth_models.ComCompany.company_status_cd == filter.company_status_cd)

        # 정렬 (최신 순)
        query = query.order_by(desc(auth_models.ComCompany.company_no))

        # 전체 개수 계산
        count_query = db.query(auth_models.ComCompany)

        if filter.company_name:
            count_query = count_query.filter(auth_models.ComCompany.company_name.like(f"%{filter.company_name.strip()}%"))

        if filter.coupang_vendor_id:
            count_query = count_query.filter(auth_models.ComCompany.coupang_vendor_id.like(f"%{filter.coupang_vendor_id.strip()}%"))

        if filter.business_registration_number:
            count_query = count_query.filter(auth_models.ComCompany.business_registration_number.like(f"%{filter.business_registration_number.strip()}%"))

        if filter.company_status_cd:
            count_query = count_query.filter(auth_models.ComCompany.company_status_cd == filter.company_status_cd)

        total_elements = count_query.count()

        # 페이징
        offset = (pagination.page - 1) * pagination.size
        results = query.offset(offset).limit(pagination.size).all()

        # 결과를 딕셔너리 리스트로 변환
        company_list = []
        for company in results:
            # 회사 상태 코드명 변환
            company_status_name = None
            if company.company_status_cd and company_status_codes:
                status_code = company_status_codes.get(company.company_status_cd)
                if status_code:
                    company_status_name = status_code.code_name

            company_dict = {
                "company_no": company.company_no,
                "company_name": company.company_name,
                "coupang_vendor_id": company.coupang_vendor_id,
                "business_registration_number": company.business_registration_number,
                "company_status_cd": company.company_status_cd,
                "company_status_name": company_status_name,  # 상태 코드명 추가
                "address": company.address,
                "address_dtl": company.address_dtl,
                "created_at": company.created_at,
                "updated_at": company.updated_at
            }
            company_list.append(company_dict)

        return common_response.ResponseBuilder.paged_success(
            content=company_list,
            page=pagination.page,
            size=pagination.size,
            total_elements=total_elements
        )

    except Exception as e:
        print(str(e))
        raise HTTPException(
            status_code=400,
            detail=f"회사 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


def fetch_company(
        company_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """회사 상세 조회"""
    try:
        # 회사 조회
        company = db.query(auth_models.ComCompany).filter(
            auth_models.ComCompany.company_no == company_no
        ).first()

        if not company:
            raise HTTPException(
                status_code=400,
                detail=f"ID {company_no}에 해당하는 회사를 찾을 수 없습니다."
            )

        # 회사 데이터를 dict로 변환
        data = {
            "company_no": company.company_no,
            "company_name": company.company_name,
            "coupang_vendor_id": company.coupang_vendor_id,
            "business_registration_number": company.business_registration_number,
            "company_status_cd": company.company_status_cd,
            "address": company.address,
            "address_dtl": company.address_dtl,
            "created_at": company.created_at,
            "updated_at": company.updated_at
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="회사 상세 조회가 완료되었습니다."
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"회사 조회 중 오류가 발생했습니다: {str(e)}"
        )


def update_company(
        company_info: CompanyBase,
        company_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """회사 수정"""
    try:
        # 업데이트할 회사 찾기
        existing_company = db.query(auth_models.ComCompany).filter(
            auth_models.ComCompany.company_no == company_no
        ).first()

        if not existing_company:
            raise HTTPException(
                status_code=400,
                detail=f"ID {company_no}에 해당하는 회사를 찾을 수 없습니다."
            )

        # Pydantic 모델을 dict로 변환 (None 값 제외)
        update_dict = company_info.dict(exclude_unset=True, exclude={'company_no', 'company_status_name'})

        # 업데이트할 필드가 있는지 확인
        if not update_dict:
            raise HTTPException(
                status_code=400,
                detail="업데이트할 필드가 없습니다."
            )

        # company_name 중복 체크 (자기 자신 제외)
        if 'company_name' in update_dict:
            duplicate_company = db.query(auth_models.ComCompany).filter(
                auth_models.ComCompany.company_name == update_dict['company_name'],
                auth_models.ComCompany.company_no != company_no
            ).first()

            if duplicate_company:
                raise HTTPException(
                    status_code=400,
                    detail=f"이미 존재하는 회사명입니다: {update_dict['company_name']}"
                )

        # coupang_vendor_id 중복 체크 (자기 자신 제외, 값이 있는 경우만)
        if 'coupang_vendor_id' in update_dict and update_dict['coupang_vendor_id']:
            duplicate_vendor = db.query(auth_models.ComCompany).filter(
                auth_models.ComCompany.coupang_vendor_id == update_dict['coupang_vendor_id'],
                auth_models.ComCompany.company_no != company_no
            ).first()

            if duplicate_vendor:
                raise HTTPException(
                    status_code=400,
                    detail=f"이미 등록된 쿠팡 판매자코드입니다: {update_dict['coupang_vendor_id']}"
                )

        # 기존 레코드 업데이트
        for field, value in update_dict.items():
            if hasattr(existing_company, field):
                setattr(existing_company, field, value)

        # updated_at 필드가 있다면 현재 시간으로 설정
        if hasattr(existing_company, 'updated_at'):
            existing_company.updated_at = datetime.now()

        db.commit()
        db.refresh(existing_company)

        # 업데이트된 데이터 반환
        data = {
            "company_no": existing_company.company_no,
            "company_name": existing_company.company_name,
            "coupang_vendor_id": existing_company.coupang_vendor_id,
            "business_registration_number": existing_company.business_registration_number,
            "company_status_cd": existing_company.company_status_cd,
            "address": existing_company.address,
            "address_dtl": existing_company.address_dtl,
            "updated_at": existing_company.updated_at,
            "updated_fields": list(update_dict.keys())
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="회사가 성공적으로 수정되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"회사 수정 중 오류가 발생했습니다: {str(e)}"
        )


def delete_company(
        company_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """회사 삭제 (물리적 삭제)"""
    try:
        # 삭제할 회사 찾기
        company = db.query(auth_models.ComCompany).filter(
            auth_models.ComCompany.company_no == company_no
        ).first()

        if not company:
            raise HTTPException(
                status_code=400,
                detail=f"삭제할 수 없는 회사입니다. (ID: {company_no})"
            )

        # 해당 회사에 속한 사용자가 있는지 확인
        user_count = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.company_no == company_no
        ).count()

        if user_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"해당 회사에 속한 사용자({user_count}명)가 있어 삭제할 수 없습니다. 먼저 사용자를 삭제하거나 다른 회사로 이동시켜주세요."
            )

        # 물리적 삭제
        db.delete(company)
        db.commit()

        data = {
            "company_no": company_no,
            "deleted": True
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="회사가 성공적으로 삭제되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"회사 삭제 중 오류가 발생했습니다: {str(e)}"
        )


async def approve_user(
        user_no: int,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    """사용자 승인"""
    try:
        current_user_no, _ = get_authenticated_user_no(request)

        # 승인할 사용자 찾기
        user = db.query(auth_models.ComUser).filter(
            auth_models.ComUser.user_no == user_no
        ).first()

        if not user:
            raise HTTPException(
                status_code=400,
                detail=f"ID {user_no}에 해당하는 사용자를 찾을 수 없습니다."
            )

        # 이미 승인된 사용자인지 확인
        if hasattr(user, 'approval_yn') and user.approval_yn == 1:
            raise HTTPException(
                status_code=400,
                detail="이미 승인된 사용자입니다."
            )

        # 사용자 이메일 복호화
        decrypted_email = None
        if user.user_email:
            decrypted_email = crypto_util.decrypt(user.user_email)

        # 1. 사용자 승인 처리
        if hasattr(user, 'approval_yn'):
            user.approval_yn = 1
        user.user_status_cd = 'ACTIVE'
        user.updated_at = datetime.now()

        # 2. 회사 정보 조회 및 상태 활성화
        company = None
        platform_type_cd = None

        if user.company_no:
            company = db.query(auth_models.ComCompany).filter(
                auth_models.ComCompany.company_no == user.company_no
            ).first()

            if company:
                company.company_status_cd = 'ACTIVE'
                company.updated_at = datetime.now()

                # 회사의 platform_type_cd 가져오기
                if hasattr(company, 'platform_type_cd'):
                    platform_type_cd = company.platform_type_cd

            # 3. COM_USER_COMPANY에 데이터 추가 (중복 체크)
            existing_user_company = db.query(auth_models.ComUserCompany).filter(
                auth_models.ComUserCompany.user_no == user_no,
                auth_models.ComUserCompany.company_no == user.company_no
            ).first()

            if not existing_user_company:
                new_user_company = auth_models.ComUserCompany(
                    user_no=user_no,
                    company_no=user.company_no
                )
                db.add(new_user_company)

        # 4. 메뉴 조회
        # 조건 1: basic_yn = 1인 기본 메뉴
        # 조건 2: platform_type_cd가 회사의 platform_type_cd와 일치하는 메뉴
        menu_query = db.query(auth_models.ComMenu).filter(
            or_(
                auth_models.ComMenu.basic_yn == 1,
                auth_models.ComMenu.platform_type_cd == platform_type_cd if platform_type_cd else False
            )
        )

        menus = menu_query.all()

        # 5. 사용자 메뉴 등록
        added_menus = []
        for menu in menus:
            # 중복 체크
            existing_user_menu = db.query(auth_models.ComUserMenu).filter(
                auth_models.ComUserMenu.user_no == user_no,
                auth_models.ComUserMenu.menu_no == menu.menu_no
            ).first()

            # 중복되지 않은 경우만 추가
            if not existing_user_menu:
                new_user_menu = auth_models.ComUserMenu(
                    user_no=user_no,
                    menu_no=menu.menu_no,
                    company_no=user.company_no
                )
                db.add(new_user_menu)
                added_menus.append({
                    "menu_no": menu.menu_no,
                    "menu_name": menu.menu_name,
                    "path": menu.path,
                    "platform_type_cd": menu.platform_type_cd,
                    "is_basic": menu.basic_yn == 1
                })

        # 커밋
        db.commit()
        db.refresh(user)

        # 6. 승인 이메일 발송
        # email_sent = False
        # if decrypted_email:
        #     try:
        #         email_subject = "[9NEWALL] 회원 가입 승인 완료"
        #         email_content = f"""
        #             안녕하세요, {user.user_id}님.
        #
        #             9NEWALL 회원 가입이 승인되었습니다.
        #
        #             이제 로그인하여 서비스를 이용하실 수 있습니다.
        #
        #             승인 일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}
        #             사용자 ID: {user.user_id}
        #             회사명: {company.company_name if company else 'N/A'}
        #
        #             서비스 이용에 문제가 있으시면 언제든지 문의해 주세요.
        #
        #             감사합니다.
        #
        #             9NEWALL 팀 드림
        #         """
        #
        #         email_sent = await email_util.send_email(
        #             email_to=[decrypted_email],
        #             subject=email_subject,
        #             content=email_content
        #         )
        #     except Exception as email_error:
        #         print(f"이메일 발송 실패: {str(email_error)}")
        #         # 이메일 발송 실패해도 승인은 완료

        # 응답 데이터
        data = {
            "user_no": user.user_no,
            "user_id": user.user_id,
            "user_email": decrypted_email
        }

        return common_response.ResponseBuilder.success(
            data=data,
            message="사용자가 성공적으로 승인되었습니다."
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"사용자 승인 중 오류가 발생했습니다: {str(e)}"
        )
