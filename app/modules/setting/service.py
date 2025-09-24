from fastapi import Depends, Request, status, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, or_
from app.utils import file_util, com_code_util
import pandas as pd

import os
import platform
from datetime import datetime
import tempfile

from app.common import response as common_response
from app.common.schemas.request import PaginationRequest
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.setting.schemas import SkuBase, SkuFilterRequest, CenterBase
from app.modules.setting import models as setting_models
from app.modules.common import models as common_models
from typing import Union
from app.utils.auth_util import get_authenticated_user_no
from app.modules.common import service as common_service


def create_sku(
        sku_info: SkuBase,
        request: Request,
        db: Session = Depends(get_db)
) -> common_response.ApiResponse[Union[dict, None]]:
    try:
        user_no, company_no = get_authenticated_user_no(request)

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
        sku_dict = sku_info.dict(exclude_unset=True, exclude={'sku_no', 'option_type'})

        # 검증된 값들 설정
        sku_dict['sku_id'] = sku_id
        sku_dict['bundle'] = bundle
        sku_dict['barcode'] = barcode  # 검증된 바코드 설정

        # 생성자 정보 추가
        sku_dict['created_by'] = user_no
        sku_dict['company_no'] = company_no

        new_sku = setting_models.SetSku(**sku_dict)

        db.add(new_sku)
        db.commit()
        db.refresh(new_sku)

        # 정상적으로 저장된 값 셋팅
        data = {
            "sku_no": new_sku.sku_no,
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

        user_no, company_no = get_authenticated_user_no(request)

        # 포장비닐규격 공통코드 서브쿼리 생성
        package_vinyl_subquery = db.query(common_models.ComCode.code_name).filter(
            common_models.ComCode.com_code == setting_models.SetSku.package_vinyl_spec_cd,
            common_models.ComCode.parent_com_code == "PACKAGE_VINYL_SPEC_CD",
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).scalar_subquery()

        # FTA 공통코드 서브쿼리 생성 (다른 _cd 컬럼이 있다면 추가)
        fta_subquery = db.query(common_models.ComCode.code_name).filter(
            common_models.ComCode.com_code == setting_models.SetSku.fta_cd,
            common_models.ComCode.parent_com_code == "FTA_CD",
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).scalar_subquery()

        # 납품여부 공통코드 서브쿼리 생성 (다른 _cd 컬럼이 있다면 추가)
        delivery_status_subquery = db.query(common_models.ComCode.code_name).filter(
            common_models.ComCode.com_code == setting_models.SetSku.delivery_status_cd,
            common_models.ComCode.parent_com_code == "DELIVERY_STATUS_CD",
            common_models.ComCode.use_yn == 1,
            common_models.ComCode.del_yn == 0
        ).scalar_subquery()

        # 쿼리 생성 및 기본 필터 (서브쿼리 결과를 label로 추가)
        query = db.query(
            setting_models.SetSku,
            package_vinyl_subquery.label("package_vinyl_spec_name"),
            fta_subquery.label("fta_name"),
            delivery_status_subquery.label("delivery_status_name")
        ).filter(
            setting_models.SetSku.del_yn == 0,
            setting_models.SetSku.company_no == company_no
        )

        # SkuFilterRequest 조건 동적 적용 (LIKE 검색)
        for filter_field, filter_value in filter.dict().items():
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
            setting_models.SetSku.del_yn == 0,
            setting_models.SetSku.company_no == company_no
        )

        # 같은 필터 조건 적용
        for filter_field, filter_value in filter.dict().items():
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
            # result.SetSku는 SKU 객체, result.package_vinyl_spec_name은 서브쿼리 결과
            sku = result.SetSku if hasattr(result, 'SetSku') else result[0]
            package_vinyl_spec_name = result.package_vinyl_spec_name if hasattr(result, 'package_vinyl_spec_name') else result[1]
            fta_name = result.fta_name if hasattr(result, 'fta_name') else result[2]
            delivery_status_name = result.delivery_status_name if hasattr(result, 'delivery_status_name') else result[3]

            # SKU를 딕셔너리로 변환
            sku_dict = SkuBase.from_orm(sku).dict()

            # 서브쿼리 결과 추가
            sku_dict['package_vinyl_spec_name'] = package_vinyl_spec_name
            sku_dict['fta_name'] = fta_name
            sku_dict['delivery_status_name'] = delivery_status_name

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
        # ID로 SKU 조회
        sku = db.query(setting_models.SetSku).filter(
            setting_models.SetSku.sku_no == sku_no,
            setting_models.SetSku.del_yn == 0
        ).first()

        if not sku:
            raise HTTPException(
                status_code=400,
                detail=f"ID {sku_no}에 해당하는 SKU를 찾을 수 없습니다."
            )

        # SKU 데이터를 dict로 변환
        data = {
            "sku_no": sku.sku_no,
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
