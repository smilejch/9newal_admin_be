from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.modules.common import models as common_models


def get_com_code_by_com_name(code_name: str, parent_com_code: str, db: Session, column_name: str = None) -> Optional[str]:
    """
    공통코드명으로 공통코드를 조회하는 함수

    Args:
        code_name: 공통코드명 (예: "소", "중", "대")
        parent_com_code: 부모 공통코드 (예: "PACKAGE_VINYL_SPEC_CD")
        db: 데이터베이스 세션

    Returns:
        com_code 또는 None

    Raises:
        ValueError: code_name이 존재하지만 해당하는 공통코드가 없을 때
    """

    if not code_name or str(code_name).strip() == '' or str(code_name).lower() == 'nan':
        return None

    try:
        # 공백 제거 및 정규화
        normalized_code_name = str(code_name).strip()

        code = db.query(common_models.ComCode).filter(
            and_(
                common_models.ComCode.code_name == normalized_code_name,
                common_models.ComCode.parent_com_code == parent_com_code,
                common_models.ComCode.use_yn == 1,
                common_models.ComCode.del_yn == 0
            )
        ).first()

        # 코드명이 입력되었는데 해당하는 공통코드가 없는 경우 에러 발생

        if code is None:
            # 해당 부모 코드의 사용 가능한 옵션들 조회
            available_codes = db.query(common_models.ComCode).filter(
                and_(
                    common_models.ComCode.parent_com_code == parent_com_code,
                    common_models.ComCode.use_yn == 1,
                    common_models.ComCode.del_yn == 0
                )
            ).all()

            available_names = [code.code_name for code in available_codes]

            raise ValueError(
                f"'{normalized_code_name}'는 유효하지 않은 {column_name if column_name is not None else parent_com_code} 값 입니다."
                f"사용 가능한 값: {', '.join(available_names) if available_names else '없음'}"
            )

        return code.com_code

    except ValueError:
        # ValueError는 다시 던져서 호출하는 곳에서 처리하도록
        raise
    except Exception as e:
        # 기타 예외는 로깅하고 None 반환
        print(f"공통코드 조회 중 예외 발생: {str(e)}")
        return None



def get_code_name_by_com_code(com_code: str, db: Session, parent_com_code: str) -> Optional[str]:
    """
    공통코드로 코드명을 조회하는 함수

    Args:
        com_code: 공통코드값
        db: 데이터베이스 세션

    Returns:
        code_name 또는 None
    """
    if not com_code:
        return None

    try:
        code = db.query(common_models.ComCode).filter(
            and_(
                common_models.ComCode.com_code == com_code,
                common_models.ComCode.parent_com_code == parent_com_code,
                common_models.ComCode.use_yn == 1,
                common_models.ComCode.del_yn == 0
            )
        ).first()

        return code.code_name if code else None
    except Exception:
        return None


def get_multiple_code_names(com_codes: List[str], db: Session) -> Dict[str, str]:
    """
    여러 공통코드를 한번에 조회하는 함수

    Args:
        com_codes: 공통코드 리스트
        db: 데이터베이스 세션

    Returns:
        {com_code: code_name} 딕셔너리
    """
    if not com_codes:
        return {}

    try:
        codes = db.query(common_models.ComCode).filter(
            and_(
                common_models.ComCode.com_code.in_(com_codes),
                common_models.ComCode.use_yn == 1,
                common_models.ComCode.del_yn == 0
            )
        ).all()

        return {code.com_code: code.code_name for code in codes}
    except Exception:
        return {}


def convert_cd_columns_to_names(data: Dict[str, Any], db: Session, cd_columns: List[str] = None) -> Dict[str, Any]:
    """
    데이터 딕셔너리에서 _cd로 끝나는 컬럼들을 자동으로 찾아서 
    해당하는 _name 컬럼을 추가하는 함수

    Args:
        data: 변환할 데이터 딕셔너리
        db: 데이터베이스 세션
        cd_columns: 특정 CD 컬럼들만 지정 (None이면 자동 탐지)

    Returns:
        변환된 데이터 딕셔너리
    """
    if not data:
        return data

    # CD 컬럼 자동 탐지 또는 지정된 컬럼 사용
    if cd_columns is None:
        cd_columns = [key for key in data.keys() if key.endswith('_cd')]

    # CD 컬럼들의 값을 수집
    cd_values = []
    cd_mapping = {}

    for cd_col in cd_columns:
        if cd_col in data and data[cd_col]:
            cd_values.append(data[cd_col])
            cd_mapping[data[cd_col]] = cd_col

    # 한번에 조회
    if cd_values:
        code_names = get_multiple_code_names(cd_values, db)

        # 결과 딕셔너리에 _name 컬럼 추가
        for com_code, code_name in code_names.items():
            cd_col = cd_mapping[com_code]
            name_col = cd_col.replace('_cd', '_name')
            data[name_col] = code_name

        # 값이 없는 CD 컬럼들에 대해서는 None으로 설정
        for cd_col in cd_columns:
            if cd_col in data:
                name_col = cd_col.replace('_cd', '_name')
                if name_col not in data:
                    data[name_col] = None

    return data


def convert_cd_columns_in_list(data_list: List[Dict[str, Any]], db: Session, cd_columns: List[str] = None) -> List[
    Dict[str, Any]]:
    """
    리스트 형태의 데이터에서 CD 컬럼들을 일괄 변환하는 함수

    Args:
        data_list: 변환할 데이터 리스트
        db: 데이터베이스 세션
        cd_columns: 특정 CD 컬럼들만 지정 (None이면 자동 탐지)

    Returns:
        변환된 데이터 리스트
    """
    if not data_list:
        return data_list

    # 모든 CD 값을 수집
    all_cd_values = set()
    if cd_columns is None:
        # 첫 번째 항목에서 CD 컬럼 자동 탐지
        cd_columns = [key for key in data_list[0].keys() if key.endswith('_cd')]

    for data in data_list:
        for cd_col in cd_columns:
            if cd_col in data and data[cd_col]:
                all_cd_values.add(data[cd_col])

    # 한번에 모든 코드명 조회
    code_names = get_multiple_code_names(list(all_cd_values), db)

    # 각 데이터에 코드명 추가
    for data in data_list:
        for cd_col in cd_columns:
            if cd_col in data:
                name_col = cd_col.replace('_cd', '_name')
                if data[cd_col] and data[cd_col] in code_names:
                    data[name_col] = code_names[data[cd_col]]
                else:
                    data[name_col] = None

    return data_list

def get_com_code_info_by_com_code(com_code: str, db: Session, parent_com_code: str) -> Optional[str]:
    if not com_code:
        return None

    try:
        code = db.query(common_models.ComCode).filter(
            and_(
                common_models.ComCode.com_code == com_code,
                common_models.ComCode.parent_com_code == parent_com_code,
                common_models.ComCode.use_yn == 1,
                common_models.ComCode.del_yn == 0
            )
        ).first()

        return code if code else None
    except Exception:
        return None


def get_com_code_dict_by_parent_code(parent_com_code: str, db: Session) -> Optional[Dict]:
    if not parent_com_code:
        return None

    try:
        codes = db.query(common_models.ComCode).filter(
            and_(
                common_models.ComCode.parent_com_code == parent_com_code,
                common_models.ComCode.use_yn == 1,
                common_models.ComCode.del_yn == 0
            )
        ).all()

        if not codes:
            return None

        # code_name을 key로, code 객체 전체를 value로 하는 딕셔너리 생성
        result_dict = {code.com_code: code for code in codes}

        return result_dict

    except Exception:
        return None