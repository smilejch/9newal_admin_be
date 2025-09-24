from app.core.config_1688 import ALIBABA_1688_API_CONFIG
import httpx
from app.modules.common import schemas as common_schemas
import json
from collections import defaultdict
import asyncio


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