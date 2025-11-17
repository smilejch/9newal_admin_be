# app/scheduler/scheduler_1688.py
from app.core.database import get_db
from app.core.config_1688 import ALIBABA_1688_API_CONFIG
from app.modules.purchase.models import OrderShipmentDtl
from datetime import datetime
from sqlalchemy import and_, distinct
import httpx


async def sync_1688_order_status():
    """1688 구매요청 물류 상태 동기화 (매일 자정 실행)"""
    print(f"[{datetime.now()}] 1688 주문 상태 동기화 시작...")

    db = next(get_db())
    try:
        # 1. 고유한 구매번호만 조회 (DISTINCT)
        unique_order_numbers = db.query(
            distinct(OrderShipmentDtl.purchase_order_number)
        ).filter(
            and_(
                OrderShipmentDtl.purchase_order_number.isnot(None),
                OrderShipmentDtl.purchase_order_number != '',
                OrderShipmentDtl.del_yn == 0
            )
        ).all()

        # 튜플 리스트를 문자열 리스트로 변환
        order_numbers = [order[0] for order in unique_order_numbers]

        print(f"[{datetime.now()}] 동기화 대상 주문 {len(order_numbers)}건 발견")

        success_count = 0
        fail_count = 0
        not_shipped_count = 0

        # 2. 각 고유 주문 번호에 대해 한 번씩만 API 호출
        for order_number in order_numbers:
            try:
                # 3. 1688 API 호출
                logistics_info = await get_1688_logistics_info(order_number)

                if logistics_info and logistics_info.get('success'):
                    result = logistics_info.get('result', [])

                    if result and len(result) > 0:
                        logistics_data = result[0]

                        # 4. 운송장 번호 추출
                        tracking_number = logistics_data.get('logisticsId')
                        delivery_status = logistics_data.get('status')
                        logistics_company_id = logistics_data.get('logisticsCompanyId')

                        if tracking_number:
                            # 5. 해당 구매번호를 가진 모든 DTL 업데이트
                            updated_count = db.query(OrderShipmentDtl).filter(
                                and_(
                                    OrderShipmentDtl.purchase_order_number == order_number,
                                    OrderShipmentDtl.del_yn == 0
                                )
                            ).update({
                                'purchase_tracking_number': tracking_number,
                                'updated_at': datetime.now()
                            }, synchronize_session=False)

                            print(f"[{datetime.now()}] 주문번호 {order_number}: 운송장번호 업데이트 완료 ({updated_count}건) - {tracking_number}")

                            # 6. 배송 상태 출력 (테이블 구조 확정 후 저장 필요)
                            print(f"[{datetime.now()}] 배송상태: {delivery_status}, 물류사ID: {logistics_company_id}")

                            # 배송 상태 저장 로직 구현 필요
                            # 배송 상태 코드:
                            # - SIGN: 서명완료(배송완료)
                            # - TRANSPORT: 운송중
                            # - 기타 상태는 1688 API 문서 참조
                            #
                            # 배송 상태 테이블 구조 확정 후:
                            # .update({'delivery_status': delivery_status, 'logistics_company_id': logistics_company_id})

                            success_count += 1
                    else:
                        print(f"[{datetime.now()}] 주문번호 {order_number}: 물류 정보 없음")

                elif logistics_info and logistics_info.get('errorCode') == '500_2':
                    # 주문이 아직 발송되지 않음
                    print(f"[{datetime.now()}] 주문번호 {order_number}: 아직 발송되지 않음")
                    not_shipped_count += 1

                else:
                    error_msg = logistics_info.get('errorMessage', 'Unknown error')
                    error_code = logistics_info.get('errorCode', '')
                    print(f"[{datetime.now()}] 주문번호 {order_number} API 호출 실패: [{error_code}] {error_msg}")
                    fail_count += 1

            except Exception as e:
                print(f"[{datetime.now()}] 주문번호 {order_number} 처리 중 오류 발생: {str(e)}")
                fail_count += 1
                continue

        # 7. 변경사항 커밋
        db.commit()
        print(f"[{datetime.now()}] 1688 주문 상태 동기화 완료")
        print(f"[{datetime.now()}] 성공: {success_count}건, 미발송: {not_shipped_count}건, 실패: {fail_count}건")

    except Exception as e:
        print(f"[{datetime.now()}] 1688 주문 상태 동기화 실패: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def get_1688_logistics_info(order_id: str) -> dict:
    """
    1688 물류 정보 조회 API 호출

    Args:
        order_id: 1688 구매 주문 번호

    Returns:
        dict: 물류 정보 응답
    """
    try:
        # 1. 랜덤 계정 설정 가져오기
        config = ALIBABA_1688_API_CONFIG._get_random_account_config()

        # 2. API 엔드포인트 구성
        api_endpoint = "com.alibaba.logistics/alibaba.trade.getLogisticsInfos.buyerView"
        api_path = f"param2/1/{api_endpoint}/{config['app_key']}"
        url = f"{config['base_url']}{api_path}"

        # 3. 타임스탬프 생성
        timestamp = ALIBABA_1688_API_CONFIG.get_timestamp()

        # 4. 요청 파라미터 구성
        params = {
            "access_token": config['access_token'],
            "timestamp": timestamp,
            "_aop_timestamp": timestamp,
            "orderId": str(order_id),
            "fields": "company.name,sender,receiver,sendgood",
            "webSite": "1688"
        }

        # 5. 서명 생성
        signature = ALIBABA_1688_API_CONFIG.generate_signature(api_path, params, config)
        params['_aop_signature'] = signature

        # 6. 헤더 생성
        headers = ALIBABA_1688_API_CONFIG.get_headers()

        # 7. API 호출 (비동기)
        print(f"[{datetime.now()}] 주문번호 {order_id} API 호출 중...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=params,
                headers=headers,
                timeout=30.0
            )
            result = response.json()

        # 8. 응답 로깅
        if result.get('success'):
            print(f"[{datetime.now()}] 주문번호 {order_id} API 호출 성공")
        else:
            error_code = result.get('errorCode', '')
            error_msg = result.get('errorMessage', '')
            if error_code != '500_2':  # "아직 발송 전" 에러는 자세히 출력 안 함
                print(f"[{datetime.now()}] 주문번호 {order_id} API 오류 응답: [{error_code}] {error_msg}")

        return result

    except Exception as e:
        print(f"[{datetime.now()}] 주문번호 {order_id} 처리 중 예외 발생: {str(e)}")
        return {'success': False, 'errorMessage': str(e)}


async def sync_1688_order_status_manual(order_id: str, db):
    """
    특정 주문의 물류 정보 수동 동기화 (API 엔드포인트에서 호출용)

    Args:
        order_id: 1688 구매 주문 번호
        db: DB 세션

    Returns:
        dict: 동기화 결과
    """
    try:
        # 해당 주문번호를 가진 DTL들 조회
        orders = db.query(OrderShipmentDtl).filter(
            and_(
                OrderShipmentDtl.purchase_order_number == order_id,
                OrderShipmentDtl.del_yn == 0
            )
        ).all()

        if not orders:
            return {'success': False, 'message': f'주문번호 {order_id}를 찾을 수 없습니다'}

        # 1688 API 호출
        logistics_info = await get_1688_logistics_info(order_id=order_id)

        if logistics_info and logistics_info.get('success'):
            result = logistics_info.get('result', [])

            if result and len(result) > 0:
                logistics_data = result[0]

                # 운송장 번호 및 배송 상태
                tracking_number = logistics_data.get('logisticsId')
                delivery_status = logistics_data.get('status')
                logistics_company_id = logistics_data.get('logisticsCompanyId')

                if tracking_number:
                    # 모든 관련 DTL 업데이트
                    for order in orders:
                        order.purchase_tracking_number = tracking_number
                        order.updated_at = datetime.now()

                    db.commit()

                    return {
                        'success': True,
                        'tracking_number': tracking_number,
                        'delivery_status': delivery_status,
                        'logistics_company_id': logistics_company_id,
                        'updated_items': len(orders),
                        'logistics_info': logistics_data
                    }

            return {'success': False, 'message': '물류 정보를 가져올 수 없습니다'}
        else:
            return {
                'success': False,
                'message': logistics_info.get('errorMessage'),
                'error_code': logistics_info.get('errorCode')
            }

    except Exception as e:
        db.rollback()
        return {'success': False, 'message': str(e)}