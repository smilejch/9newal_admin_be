import requests
from sqlalchemy.orm import Session
import time
import os
from typing import Dict
from app.modules.common import models as common_models
import datetime

def request_cj_logistics_api(db: Session, process: str, params: Dict = None):
    time.sleep(1)
    token = get_cj_logistics_token(db)

    if not token:  # 토큰이 없으면 에러 처리
        raise ValueError("CJ Logistics token을 가져올 수 없습니다")

    if params is None:  # mutable default argument 방지
        params = {}

    params['TOKEN_NUM'] = token
    params = {"DATA": params}

    cj_logistics_base_url = os.getenv('CJ_LOGISTICS_BASE_URL')
    cj_logistics_url = cj_logistics_base_url + process

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "CJ-Gateway-APIKey": token
    }

    try:
        response = requests.post(cj_logistics_url, json=params, headers=headers, timeout=30)
        response.raise_for_status()  # HTTP 에러 체크
        return response.json()
    except requests.exceptions.RequestException as e:
        # 로깅 추가 권장
        raise Exception(f"CJ Logistics API 요청 실패: {str(e)}")


def get_cj_logistics_token(db: Session):
    token_info = db.query(common_models.ComToken).filter(common_models.ComToken.token_type == 'cj_logistics').first()

    if token_info and token_info.token_expire_date:
        expire_date_str = token_info.token_expire_date
        try:
            expire_date = datetime.strptime(expire_date_str, '%Y%m%d%H%M%S')
            now = datetime.now()
            time_remaining = expire_date - now
            if time_remaining.total_seconds() > 300:
                return token_info.token_value if hasattr(token_info, 'token_value') else token_info.token
        except ValueError:
            pass

    # 토큰 갱신
    process = 'ReqOneDayToken'
    cj_logistics_url = os.getenv('CJ_LOGISTICS_BASE_URL') + process
    params = {
        "DATA": {
            "CUST_ID": os.getenv('CJ_LOGISTICS_CUST_ID', ''),
            "BIZ_REG_NUM": os.getenv('CJ_LOGISTICS_BIZ_REG_NUM', '')
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(cj_logistics_url, json=params, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get('RESULT_CD') == 'S' and 'DATA' in result:
            token = result['DATA'].get('TOKEN_NUM', '')
            token_expire_date = result['DATA'].get('TOKEN_EXPRTN_DTM', '')

            if token_info:
                # token과 token_value 필드명 통일 필요
                db.query(common_models.ComToken).filter(common_models.ComToken.token_type == 'cj_logistics').update({
                    'token': token,  # token_value로 통일
                    'token_expire_date': token_expire_date
                })
            else:
                new_com_token = common_models.ComToken(
                    token_type='cj_logistics',
                    token=token,
                    token_expire_date=token_expire_date
                )
                db.add(new_com_token)
            db.commit()

            return token
    except requests.exceptions.RequestException as e:
        # 로깅 추가 권장
        pass

    # 기존 토큰이라도 반환
    if token_info:
        return token_info.token_value if hasattr(token_info, 'token_value') else token_info.token

    return None