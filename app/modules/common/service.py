from app.utils import alibaba_1688_util
from fastapi import HTTPException, UploadFile, Request, status
from app.common.response import ResponseBuilder
from typing import Union, List
import pandas as pd
from io import BytesIO, StringIO
import numpy as np
from app.utils import file_util
from sqlalchemy.orm import Session
from datetime import datetime
from app.common.response import ApiResponse
from app.modules.common import models as common_models
from app.modules.common import schemas as common_schemas
from app.modules.auth import models as auth_models
from app.modules.setting.models import SetSku
from app.utils.auth_util import get_authenticated_user_no
from app.core.config import GMAIL_CONFIG
from email.message import EmailMessage
import aiosmtplib
import ssl
import certifi
import json
from app.core.config_1688 import ALIBABA_1688_API_CONFIG

async def fetch_alibaba_product_options(offer_id: Union[str, int]) -> dict:
    response_data = await alibaba_1688_util.get_product_sku_info(str(offer_id))

    if "error" in response_data:
        raise HTTPException(status_code=400, detail=response_data["error"])
    formatted_data = []
    if response_data["result"]["success"]:
        result = response_data["result"]["result"]
        sku_simple_infos = result["skuSimpleInfos"]
        open_uid = result["openUid"]

        for item in sku_simple_infos:
            sku_id = item["skuId"]
            spec_id = item["specId"]
            option_value = ", ".join(
                attr["attributeValue"]
                for attr in item["attributes"]
            )

            linked_option = ", ".join(
                f'{attr["attributeName"]}: {attr["attributeValue"]}'
                for attr in item["attributes"]
            )

            formatted_data.append({
                "linked_spec_id": spec_id,
                "linked_sku_id": sku_id,
                "linked_open_uid": open_uid,
                "linked_option": linked_option,
                "option_value": option_value
            })

        return ResponseBuilder.success(
            data=formatted_data,
            message="SKU 상세 조회가 완료되었습니다."
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"연동옵션 불러오는데 실패했습니다.\n({response_data['result']['code']})"
        )


async def read_excel_file(
        file: UploadFile,
        expected_headers: List[str] = None,
        column_mapping: dict = None
) -> List[dict]:
    """엑셀 파일 읽기 및 헤더 검증 후 DB 저장용 데이터 반환"""
    try:
        contents = await file.read()

        with BytesIO(contents) as excel_buffer:
            df = pd.read_excel(excel_buffer)

        await file.seek(0)

        if expected_headers:
            file_util.validate_headers(df.columns.tolist(), expected_headers)

        df = df.replace([np.inf, -np.inf], np.nan)

        df = df.where(pd.notnull(df), None)

        if column_mapping:
            # column_mapping에 있는 컬럼만 선택
            existing_cols = [col for col in df.columns if col in column_mapping]
            df = df[existing_cols]
            df = df.rename(columns=column_mapping)

        records = []
        for _, row in df.iterrows():
            record = {}
            for col, value in row.items():
                record[col] = file_util.clean_value(value)
            records.append(record)

        return records

    except HTTPException:
        raise
    except Exception as e:
        return file_util.handle_error(
            db=None,
            message='엑셀 파일 처리 중 오류가 발생했습니다',
            error_details=[str(e)],
            error_count=1
        )


async def read_csv_file(
        file: UploadFile,
        expected_headers: List[str] = None,
        column_mapping: dict = None
) -> List[dict]:
    """CSV 파일 읽기 및 헤더 검증 후 DB 저장용 데이터 반환"""
    try:
        contents = await file.read()

        # 인코딩 시도 (한글 파일 대응)
        try:
            content_str = contents.decode('utf-8')
        except UnicodeDecodeError:
            # UTF-8이 안되면 CP949(한글 윈도우) 시도
            try:
                content_str = contents.decode('cp949')
            except UnicodeDecodeError:
                # 그래도 안되면 latin-1로 시도
                content_str = contents.decode('latin-1')

        with StringIO(content_str) as csv_buffer:
            df = pd.read_csv(csv_buffer)

        await file.seek(0)

        if expected_headers:
            file_util.validate_headers(df.columns.tolist(), expected_headers)

        df = df.replace([np.inf, -np.inf], np.nan)

        df = df.where(pd.notnull(df), None)

        if column_mapping:
            df = df.rename(columns=column_mapping)

        records = []
        for _, row in df.iterrows():
            record = {}
            for col, value in row.items():
                record[col] = file_util.clean_value(value)
            records.append(record)

        return records

    except HTTPException:
        raise
    except Exception as e:
        return file_util.handle_error(
            db=None,
            message='엑셀 파일 처리 중 오류가 발생했습니다',
            error_details=[str(e)],
            error_count=1
        )

async def fetch_common_codes(parent_com_code: str, db: Session) -> ApiResponse[list]:
    common_codes = (
        db.query(common_models.ComCode)
        .filter(
            common_models.ComCode.parent_com_code == parent_com_code,
            common_models.ComCode.del_yn == 0,
            common_models.ComCode.use_yn == 1)
        .order_by(common_models.ComCode.sort_order)
        .all()
    )

    common_codes_schema = [common_schemas.ComCodeResponse.from_orm(code) for code in common_codes]

    return ResponseBuilder.success(
        data=common_codes_schema,
        message="조회가 완료되었습니다."
    )


async def update_linked_options_info(
        sku_no: int,
        linked_options_request: common_schemas.LinkedOptionsRequest,
        db: Session,
        request: Request
) -> ApiResponse[list]:  # 리스트 타입으로 변경
    try:
        user_no, company_no = get_authenticated_user_no(request)

        # sku_no로 기존 SKU 데이터 조회
        existing_sku = db.query(SetSku).filter(
            SetSku.sku_no == sku_no,
            SetSku.del_yn == 0
        ).first()

        if not existing_sku:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="해당 SKU를 찾을 수 없습니다."
            )

        # 연동 옵션 정보 업데이트
        update_fields = {}

        if linked_options_request.linked_option is None:
            print("option X!")
            # option_value 업데이트
            existing_sku.linked_option = linked_options_request.linked_option
            update_fields["linked_option"] = linked_options_request.linked_option

            existing_sku.linked_spec_id = None
            update_fields["linked_spec_id"] = None

            existing_sku.linked_sku_id = None
            update_fields["linked_sku_id"] = None

            existing_sku.linked_open_uid = None
            update_fields["linked_open_uid"] = None

            existing_sku.option_type = "MANUAL"
            update_fields["option_type"] = "MANUAL"
        else:

            # option_value 업데이트
            existing_sku.linked_option = linked_options_request.linked_option
            update_fields["linked_option"] = linked_options_request.linked_option

            existing_sku.linked_spec_id = linked_options_request.linked_spec_id
            update_fields["linked_spec_id"] = linked_options_request.linked_spec_id

            existing_sku.linked_sku_id = linked_options_request.linked_sku_id
            update_fields["linked_sku_id"] = linked_options_request.linked_sku_id

            existing_sku.linked_open_uid = linked_options_request.linked_open_uid
            update_fields["linked_open_uid"] = linked_options_request.linked_open_uid

            existing_sku.option_type = "AUTO"
            update_fields["option_type"] = "AUTO"

        # 업데이트할 필드가 없는 경우
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="업데이트할 데이터가 없습니다."
            )

        # 공통 업데이트 정보 설정
        existing_sku.updated_by = user_no
        existing_sku.updated_at = datetime.now()

        # 변경사항 커밋
        db.commit()

        return ResponseBuilder.success(
            data=[update_fields],  # 딕셔너리를 리스트로 감싸기
            message="연동 옵션 정보가 성공적으로 업데이트되었습니다."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"연동 옵션 정보 업데이트 중 오류가 발생했습니다: {str(e)}"
        )

def fetch_hs_codes(db: Session):
    try:
        result = db.query(common_models.ComHsCode).all()
        hs_codes_schema = [common_schemas.ComHsCodeResponse.from_orm(hs_code) for hs_code in result]

        return ResponseBuilder.success(
            data=hs_codes_schema,
            message="HS 코드 목록을 성공적으로 조회했습니다."
        )
    except Exception as e:
        return ResponseBuilder.error(f"HS 코드 조회 중 오류가 발생했습니다: {str(e)}")


async def send_mail(mailTo: str, subject: str, content: str):
    try:
        msg = EmailMessage()
        msg["From"] = GMAIL_CONFIG.MAIL_FROM
        msg["To"] = mailTo
        msg["Subject"] = subject
        msg.set_content(content)
        print(f"Sending email to: {mailTo}")

        context = ssl.create_default_context(cafile=certifi.where())

        await aiosmtplib.send(
            msg,
            hostname=GMAIL_CONFIG.SMTP_HOST,
            port=GMAIL_CONFIG.SMTP_PORT,
            start_tls=True,
            username=GMAIL_CONFIG.GMAIL_ID,
            password=GMAIL_CONFIG.GMAIL_APP_PASSWORD,
            tls_context=context
        )

    except Exception as e:
        print(f"Email send error: {e}")
        raise

async def create_order_preview(request: common_schemas.AlibabaCreateOrderPreviewListRequest):
    response_data = await alibaba_1688_util.create_order_preview(request)

def update_company_profile(company_request: common_schemas.CompanyUpdateRequest, request: Request, db: Session):
    user_no, company_no = get_authenticated_user_no(request)

    existing_company = db.query(auth_models.ComCompany).filter(auth_models.ComCompany.company_no == company_no).first()

    if not existing_company:
        raise HTTPException(
            status_code=400,
            detail=f"해당하는 업체를 찾을 수 없습니다."
        )

    existing_company.business_registration_number = company_request.business_registration_number
    existing_company.address = company_request.address
    existing_company.address_dtl = company_request.address_dtl

    db.commit()

    return existing_company

def fetch_company_profile(request: Request, db: Session, company_no):
    company_profile = db.query(auth_models.ComCompany).filter(auth_models.ComCompany.company_no == company_no).first()

    return common_schemas.CompanyProfileResponse(
        company_name=company_profile.company_name,
        coupang_vendor_id=company_profile.coupang_vendor_id,
        business_registration_number=company_profile.business_registration_number,
        address=company_profile.address,
        address_dtl=company_profile.address_dtl,
    )


def fetch_company_list(db: Session):
    try:
        # 회사 목록 조회
        companies = db.query(
            auth_models.ComCompany.company_no,
            auth_models.ComCompany.company_name
        ).order_by(
            auth_models.ComCompany.company_name
        ).all()

        # 결과를 딕셔너리 리스트로 변환
        company_list = [
            {
                "company_no": company.company_no,
                "company_name": company.company_name
            }
            for company in companies
        ]

        return ResponseBuilder.success(
            data=company_list,
            message="회사 목록 조회가 완료되었습니다."
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"회사 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )
