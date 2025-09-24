import math
import pandas as pd
import numpy as np
from fastapi import HTTPException
from typing import List, Union
from sqlalchemy.orm import Session
from app.common import response as common_response


def handle_error(db: Union[Session, None], message: str, error_details: list = None, error_count: int = 0):
    """공통 에러 처리 함수"""

    if db:
        db.rollback()

    return common_response.ResponseBuilder.error(
        message=message,
        data={
            "error_details": error_details or [],
            "error_count": error_count
        } if error_details else None
    )


def add_error(error_list: list, row_index: int, message: str) -> int:
    """에러 추가 헬퍼 함수"""
    error_list.append(f"행 {row_index + 2}: {message}")
    return len(error_list)


def clean_value(value):
    """값 정제 함수 - JSON 직렬화 가능하도록 변환"""
    # None 처리
    if value is None:
        return None

    # pandas NA 처리
    if pd.isna(value):
        return None

    # 숫자 타입 처리
    if isinstance(value, (int, float, np.integer, np.floating)):
        # NaN 체크
        if pd.isna(value):
            return None

        # 무한대 체크
        if math.isinf(value):
            return None

        # numpy 타입을 파이썬 기본 타입으로 변환
        if isinstance(value, np.integer):
            return int(value)
        elif isinstance(value, np.floating):
            if math.isnan(value):
                return None
            return float(value)

        # 일반 float/int 체크
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return value

        return value

    # 문자열 처리
    if isinstance(value, str):
        return value.strip() if value.strip() else None

    # datetime 처리 (만약 있다면)
    if hasattr(value, 'isoformat'):
        return value.isoformat()

    # 기타 타입은 문자열로 변환
    return str(value)

def validate_headers(actual_headers: List[str], expected_headers: List[str]):
    try:
        actual_clean = []
        for h in actual_headers:
            if h is not None and not pd.isna(h):
                actual_clean.append(str(h).strip())
            else:
                actual_clean.append("")

        expected_clean = [str(h).strip() for h in expected_headers]

        missing_headers = [exp for exp in expected_clean if exp not in actual_clean]

        if missing_headers:
            raise HTTPException(
                status_code=400,
                detail=f"필수 헤더가 누락되었습니다: {missing_headers}."
            )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"헤더 검증 중 오류: {str(e)}"
        )

def clean_price_field(value):
    """가격 필드에서 콤마를 제거하고 숫자로 변환"""
    if pd.isna(value) or str(value).strip() == "" or value == 'nan':
        return None

    # 문자열로 변환 후 콤마 제거
    cleaned_value = str(value).replace(',', '').strip()

    # 빈 문자열인 경우 None 반환
    if not cleaned_value:
        return None

    try:
        # 소수점이 있으면 float으로, 없으면 int로 변환
        if '.' in cleaned_value:
            return float(cleaned_value)
        else:
            return int(cleaned_value)
    except (ValueError, TypeError):
        # 숫자, 빈값 아닐 경우 기본 값을 내보내어 에러 처리
        return value