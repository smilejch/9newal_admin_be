from app.core.config_1688 import ALIBABA_1688_API_CONFIG
from app.modules.common import schemas as common_schemas
from app.modules.purchase import models as purchase_models
from collections import defaultdict
from typing import Optional
from googletrans import Translator
from typing import List
from sqlalchemy import and_
from datetime import datetime
import httpx
import json
import asyncio
import re


async def call_1688_api(api_endpoint, params=None):
    config_1688 = ALIBABA_1688_API_CONFIG._get_random_account_config()

    api_path = f"param2/1/{api_endpoint}/{config_1688['app_key']}"
    url = f"{config_1688['base_url']}{api_path}"

    timestamp = ALIBABA_1688_API_CONFIG.get_timestamp()

    base_params = {
        "access_token": config_1688['access_token'],
        "timestamp": timestamp,
        "_aop_timestamp": timestamp
    }

    if params:
        base_params.update(params)

    base_params['_aop_signature'] = ALIBABA_1688_API_CONFIG.generate_signature(api_path, base_params, config_1688)
    headers = ALIBABA_1688_API_CONFIG.get_headers()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=base_params,
                headers=headers,
                timeout=30.0
            )
            return response.json()

    except Exception as e:
        return {"error": str(e)}


def get_product_sku_info(offerId):
    """상품 SKU 정보 조회"""
    params = {
        "offerId": str(offerId)
    }

    return call_1688_api("com.alibaba.product/product.skuinfo.get", params)


async def create_order_preview(request: common_schemas.AlibabaCreateOrderPreviewListRequest):
    cfg = ALIBABA_1688_API_CONFIG._get_random_account_config()

    address_obj = {
        "addressId": cfg["address_id"],
        "fullName": cfg["full_name"],
        "mobile": cfg["mobile"],
        "phone": cfg["phone"],
        "postCode": cfg["post_code"],
        "cityText": cfg["city_text"],
        "provinceText": cfg["province_text"],
        "districtText": cfg["area_text"],
        "townText": cfg["town_text"],
        "address": cfg["address"],
        "districtCode": cfg["district_code"],
    }
    address_json = json.dumps(address_obj, ensure_ascii=False)

    grouped_by_open_uid = defaultdict(list)
    for item in request.requests:
        grouped_by_open_uid[item.openUid].append(item)

    # 모든 API 호출을 동시에 실행
    tasks = []
    for open_uid, items in grouped_by_open_uid.items():
        cargo_list = []

        for item in items:
            obj = {
                "offerId": item.offerId,
                "specId": item.specId,
                "quantity": str(item.quantity)
            }
            cargo_list.append({k: v for k, v in obj.items() if v is not None})

        cargo_json = json.dumps(cargo_list, ensure_ascii=False)

        params = {
            "message": cfg["message"],
            "addressParam": address_json,
            "cargoParamList": cargo_json,
        }

        # 코루틴을 생성하고 메타데이터와 함께 저장
        task = call_1688_api("com.alibaba.trade/alibaba.createOrder.preview", params)
        tasks.append((open_uid, items, task))

    # 모든 API 호출을 동시에 실행
    api_results = await asyncio.gather(*[task for _, _, task in tasks])

    # 결과를 원하는 형태로 매핑
    results = []
    for i, (open_uid, items, _) in enumerate(tasks):
        results.append({
            "openUid": open_uid,
            "items": items,
            "result": api_results[i]
        })

    return results
async def create_order_1688_batch(requests: List[common_schemas.AlibabaFastCreateOrderRequest]):
    """1688 빠른 주문 생성 API - 병렬 처리"""
    cfg = ALIBABA_1688_API_CONFIG._get_random_account_config()

    # addressParam 구조 (모든 요청에 공통으로 사용)
    address_obj = {
        "fullName": cfg["full_name"],
        "mobile": cfg["mobile"],
        "phone": cfg["phone"],
        "postCode": cfg["post_code"],
        "cityText": cfg["city_text"],
        "provinceText": cfg["province_text"],
        "areaText": cfg["area_text"],
        "townText": cfg["town_text"],
        "address": cfg["address"]
    }
    address_json = json.dumps(address_obj, ensure_ascii=False)

    # 모든 API 호출을 동시에 실행
    tasks = []
    for req in requests:
        # cargoParamList 구성
        cargo_list = []
        for item in req.cargoList:
            obj = {
                "offerId": item.offerId,
                "specId": item.specId,
                "quantity": item.quantity
            }
            cargo_list.append({k: v for k, v in obj.items() if v is not None})

        cargo_json = json.dumps(cargo_list, ensure_ascii=False)

        # 파라미터 구성
        params = {
            "flow": req.flow or "general",
            "message": req.message or cfg["message"],
            "addressParam": address_json,
            "cargoParamList": cargo_json,
        }

        # 선택적 파라미터
        if req.tradeType:
            params["tradeType"] = req.tradeType
        if req.outOrderId:
            params["outOrderId"] = req.outOrderId

        # 코루틴을 생성하고 메타데이터와 함께 저장
        task = call_1688_api(
            "com.alibaba.trade/alibaba.trade.fastCreateOrder",
            params
        )
        tasks.append((req, task))

    # 모든 API 호출을 동시에 실행
    api_results = await asyncio.gather(*[task for _, task in tasks])

    # 결과를 원하는 형태로 매핑
    results = []
    for i, (req, _) in enumerate(tasks):
        results.append({
            "request": req,
            "result": api_results[i]
        })

    return results


# 기존 단일 요청 함수도 유지 (하위 호환성)
async def create_order_1688(request: common_schemas.AlibabaFastCreateOrderRequest):
    """1688 빠른 주문 생성 API - 단일 요청"""
    results = await create_order_1688_batch([request])
    return results[0]["result"]

def extract_offer_id_from_link(link: str) -> Optional[str]:
    """1688 링크에서 offer_id 추출"""
    if not link:
        return None

    # /offer/{offer_id}.html 패턴 매칭
    pattern = r'/offer/(\d+)\.html'
    match = re.search(pattern, link)
    if match:
        return match.group(1)
    return None

async def translate_chinese_to_korean(text: str) -> str:
    """중국어를 한국어로 번역"""
    try:
        translator = Translator()
        result = await translator.translate(text, src='zh-cn', dest='ko')
        return result.text
    except Exception as e:
        print(f"번역 실패: {str(e)}")

        return text  # 번역 실패 시 원본 텍스트 반환


async def sync_payment_link_to_shipment_dtl(db, order_numbers: list, account_no: int = None) -> dict:
    """
    구매번호 리스트로 결제 링크를 생성하고 OrderShipmentDtl에 업데이트

    Args:
        db: DB 세션
        order_numbers: 1688 구매 주문 번호 리스트
        account_no: 1688 계정 번호 (없으면 랜덤 선택)

    Returns:
        dict: 처리 결과
    """
    try:
        # 1. 유효한 주문번호 확인
        valid_orders = db.query(purchase_models.OrderShipmentEstimateProduct).filter(
            and_(
                purchase_models.OrderShipmentEstimateProduct.purchase_order_number.in_(order_numbers),
                purchase_models.OrderShipmentEstimateProduct.del_yn == 0
            )
        ).all()

        if not valid_orders:
            return {
                'success': False,
                'message': '유효한 주문을 찾을 수 없습니다.'
            }

        valid_order_numbers = list(set([order.purchase_order_number for order in valid_orders]))

        # 2. 결제 링크 생성 API 호출
        payment_result = await create_payment_link_by_order_numbers(
            order_numbers=valid_order_numbers,
            account_no=account_no
        )

        if not payment_result.get('success'):
            return payment_result

        pay_url = payment_result.get('pay_url')

        # 3. OrderShipmentEstimateProduct 업데이트 (결제 링크 저장)
        updated_count = db.query(purchase_models.OrderShipmentEstimateProduct).filter(
            and_(
                purchase_models.OrderShipmentEstimateProduct.purchase_order_number.in_(valid_order_numbers),
                purchase_models.OrderShipmentEstimateProduct.del_yn == 0
            )
        ).update({
            'purchase_pay_link': pay_url,  # 컬럼명은 실제 스키마에 맞게 수정 필요
            'updated_at': datetime.now()
        }, synchronize_session=False)

        db.commit()

        print(f"[{datetime.now()}] 결제 링크 업데이트 완료: {updated_count}건")

        return {
            'success': True,
            'pay_url': pay_url,
            'updated_count': updated_count,
            'order_numbers': valid_order_numbers,
            'message': f'결제 링크가 {updated_count}건의 주문에 저장되었습니다.'
        }

    except Exception as e:
        db.rollback()
        print(f"[{datetime.now()}] 결제 링크 업데이트 중 오류 발생: {str(e)}")
        return {
            'success': False,
            'message': f'결제 링크 업데이트 실패: {str(e)}'
        }


async def create_payment_link_manual(order_numbers: list, account_no: int = None, db=None) -> dict:
    """
    수동으로 특정 주문들의 결제 링크 생성

    Args:
        order_numbers: 1688 구매 주문 번호 리스트
        account_no: 1688 계정 번호 (없으면 랜덤 선택)
        db: DB 세션 (옵션, 제공시 DB 업데이트까지 수행)

    Returns:
        dict: 결제 링크 생성 결과
    """
    if not order_numbers or len(order_numbers) == 0:
        return {
            'success': False,
            'message': '주문번호가 제공되지 않았습니다.'
        }

    # DB 세션이 제공된 경우 DB 업데이트까지 수행
    if db:
        return await sync_payment_link_to_shipment_dtl(db, order_numbers, account_no)

    # DB 세션이 없으면 결제 링크만 반환
    return await create_payment_link_by_order_numbers(order_numbers, account_no)


async def create_payment_link_by_order_numbers(order_numbers: list, account_no: int = None) -> dict:
    """
    1688 구매 주문번호 리스트로 조합 결제 링크 생성

    Args:
        order_numbers: 1688 구매 주문 번호 리스트
        account_no: 1688 계정 번호 (없으면 랜덤 선택)

    Returns:
        dict: 결제 링크 생성 결과
    """
    try:
        # 1. 계정 설정 가져오기
        config = ALIBABA_1688_API_CONFIG._get_account_config(account_no)
        print("TEST CONFIG")
        print(config)

        # 2. API 엔드포인트 구성
        api_endpoint = "com.alibaba.trade/alibaba.trade.grouppay.url.get"
        api_path = f"param2/1/{api_endpoint}/{config['app_key']}"
        url = f"{config['base_url']}{api_path}"

        # 3. 타임스탬프 생성
        timestamp = ALIBABA_1688_API_CONFIG.get_timestamp()

        # 4. 요청 파라미터 구성
        params = {
            "access_token": config['access_token'],
            "orderIds": str(order_numbers),  # 리스트를 문자열로 변환
            "payPlatformType": "PC",
            "timestamp": timestamp,
            "_aop_timestamp": timestamp
        }

        # 5. 서명 생성
        signature = ALIBABA_1688_API_CONFIG.generate_signature(api_path, params, config)
        params['_aop_signature'] = signature

        # 6. 헤더 생성
        headers = ALIBABA_1688_API_CONFIG.get_headers()

        # 7. API 호출 (비동기)
        print(f"[{datetime.now()}] 결제 링크 생성 API 호출 중... (주문 {len(order_numbers)}건)")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=params,
                headers=headers,
                timeout=30.0
            )
            result = response.json()

        # 8. 응답 처리
        if result.get('success'):
            pay_url = result.get('payUrl')
            print(f"[{datetime.now()}] 결제 링크 생성 성공: {pay_url}")
            return {
                'success': True,
                'pay_url': pay_url,
                'order_count': len(order_numbers),
                'message': '정상적으로 결제 링크 생성에 성공했습니다.'
            }
        else:
            error_msg = result.get('errorMessage', result.get('errorInfo', 'Unknown error'))
            error_code = result.get('errorCode', '')
            print(f"[{datetime.now()}] 결제 링크 생성 실패: [{error_code}] {error_msg}")
            return {
                'success': False,
                'message': f'결제 링크 생성에 실패했습니다: {error_msg}',
                'error_code': error_code
            }

    except Exception as e:
        print(f"[{datetime.now()}] 결제 링크 생성 중 예외 발생: {str(e)}")
        return {
            'success': False,
            'message': f'결제 링크 생성 중 오류 발생: {str(e)}'
        }


# def create_new_po_purchase_group_pay_url(db:Session, request: NewPoPurchaseGroupPayUrlListRequest):
#     API_PATH = f"param2/1/com.alibaba.trade/alibaba.trade.grouppay.url.get/{os.getenv('APP_KEY')}"
#     URL = f"{os.getenv('BASE_URL')}{API_PATH}"
#
#     timestamp = str(int(time.time() * 1000))
#     order_1688_Ids = list({item.order_no_1688 for item in request.new_po_purchase_group_pay_url_list})
#
#     params = {
#         "access_token": os.getenv('ACCESS_TOKEN'),
#         "orderIds": json.dumps(order_1688_Ids, ensure_ascii=False),
#         "payPlatformType": 'PC',
#         "timestamp": timestamp,
#         "_aop_timestamp": timestamp
#     }
#
#
#     signature = generate_signature(API_PATH, params)
#     params['_aop_signature'] = signature
#
#     try:
#         response = requests.post(URL, data=params, headers={'Content-Type': 'application/x-www-form-urlencoded'})
#
#         response_data = response.json()
#         result_yn = response_data['success']
#         pay_link_1688 = None
#         if result_yn:
#             pay_link_1688 = response_data.get("payUrl")
#
#             if response.status_code != 200:
#                 status = 2
#                 description = '결제 링크 생성에 실패했습니다. [구분 : 결제링크생성]'
#             else:
#                 status = 3
#                 description = '정상적으로 결제 링크 생성에 성공했습니다. [구분 : 결제링크생성]'
#         else:
#             status = 2
#             # translated_text = translator.translate(str(response_data['errorInfo']), src='zh-cn', dest='ko')
#             # description = translated_text.text
#             description = str(response_data['errorInfo'])
#
#         for order_no_1688 in order_1688_Ids:
#             new_po_purchase_infos = db.query(NewPoPurchase).filter(NewPoPurchase.order_no_1688 == order_no_1688).all()
#             for new_po_purchase_info in new_po_purchase_infos:
#                 new_po_purchase_info.pay_link_1688 = pay_link_1688
#                 new_po_purchase_info.description = description
#                 new_po_purchase_info.status = status
#
#             db.commit()
