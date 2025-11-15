from app.core.config_1688 import ALIBABA_1688_API_CONFIG
import httpx
from app.modules.common import schemas as common_schemas
import json
from collections import defaultdict
import asyncio
from typing import Optional
import re
from googletrans import Translator
from typing import List


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