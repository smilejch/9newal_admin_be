# app/scheduler/scheduler_1688.py
from app.core.database import get_db
from app.core.config_1688 import ALIBABA_1688_API_CONFIG
from app.modules.purchase.models import OrderShipmentDtl, OrderShipmentEstimate, OrderMst, OrderShipmentMst
from datetime import datetime
from sqlalchemy import and_, distinct
from app.utils import alibaba_1688_util
from app.modules.purchase import models as purchase_models
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
                # 2-1. 해당 주문번호의 account_info_no_1688 조회
                account_no = db.query(OrderShipmentEstimate.account_info_no_1688).join(
                    OrderMst, OrderShipmentEstimate.order_mst_no == OrderMst.order_mst_no
                ).join(
                    OrderShipmentMst, OrderMst.order_mst_no == OrderShipmentMst.order_mst_no
                ).join(
                    OrderShipmentDtl, OrderShipmentMst.order_shipment_mst_no == OrderShipmentDtl.order_shipment_mst_no
                ).filter(
                    and_(
                        OrderShipmentDtl.purchase_order_number == order_number,
                        OrderShipmentDtl.del_yn == 0,
                        OrderShipmentEstimate.del_yn == 0
                    )
                ).first()

                # account_no가 있으면 해당 계정 사용, 없으면 None (랜덤)
                account_info_no = account_no[0] if account_no else None

                # 3. 1688 API 호출 (계정 번호 전달)
                logistics_info = await get_1688_logistics_info(order_number, account_info_no)

                if logistics_info and logistics_info.get('success'):
                    result = logistics_info.get('result', [])

                    if result and len(result) > 0:
                        logistics_data = result[0]

                        # 4. 운송장 번호 및 배송 상태 추출
                        tracking_number = logistics_data.get('logisticsId')
                        delivery_status = logistics_data.get('status')
                        logistics_company_id = logistics_data.get('logisticsCompanyId')

                        if tracking_number:
                            # 5. 해당 구매번호를 가진 모든 DTL 업데이트 (운송장번호 + 배송상태)
                            updated_count = db.query(OrderShipmentDtl).filter(
                                and_(
                                    OrderShipmentDtl.purchase_order_number == order_number,
                                    OrderShipmentDtl.del_yn == 0
                                )
                            ).update({
                                'purchase_tracking_number': tracking_number,
                                'delivery_status': delivery_status,
                                'updated_at': datetime.now()
                            }, synchronize_session=False)

                            print(f"[{datetime.now()}] 주문번호 {order_number}: 업데이트 완료 ({updated_count}건)")
                            print(f"[{datetime.now()}] - 운송장번호: {tracking_number}")
                            print(f"[{datetime.now()}] - 배송상태: {delivery_status}")
                            print(f"[{datetime.now()}] - 물류사ID: {logistics_company_id}")

                            success_count += 1
                    else:
                        print(f"[{datetime.now()}] 주문번호 {order_number}: 물류 정보 없음")

                elif logistics_info and logistics_info.get('errorCode') == '500_2':
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

        # 6. 변경사항 커밋
        db.commit()
        print(f"[{datetime.now()}] 1688 주문 상태 동기화 완료")
        print(f"[{datetime.now()}] 성공: {success_count}건, 미발송: {not_shipped_count}건, 실패: {fail_count}건")

    except Exception as e:
        print(f"[{datetime.now()}] 1688 주문 상태 동기화 실패: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def get_1688_logistics_info(order_id: str, account_no: int = None) -> dict:
    """
    1688 물류 정보 조회 API 호출

    Args:
        order_id: 1688 구매 주문 번호
        account_no: 1688 계정 번호 (없으면 랜덤 선택)

    Returns:
        dict: 물류 정보 응답
    """
    try:
        # 1. 계정 설정 가져오기 (account_no가 있으면 해당 계정, 없으면 랜덤)
        config = ALIBABA_1688_API_CONFIG._get_account_config(account_no)

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
            if error_code != '500_2':
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

        # account_info_no_1688 조회
        account_no = db.query(OrderShipmentEstimate.account_info_no_1688).join(
            OrderMst, OrderShipmentEstimate.order_mst_no == OrderMst.order_mst_no
        ).join(
            OrderShipmentMst, OrderMst.order_mst_no == OrderShipmentMst.order_mst_no
        ).join(
            OrderShipmentDtl, OrderShipmentMst.order_shipment_mst_no == OrderShipmentDtl.order_shipment_mst_no
        ).filter(
            and_(
                OrderShipmentDtl.purchase_order_number == order_id,
                OrderShipmentDtl.del_yn == 0,
                OrderShipmentEstimate.del_yn == 0
            )
        ).first()

        account_info_no = account_no[0] if account_no else None

        # 1688 API 호출
        logistics_info = await get_1688_logistics_info(order_id=order_id, account_no=account_info_no)

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

        print("TEST123")
        print("CONFIG -> ", config)

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
            translated_message = await alibaba_1688_util.translate_chinese_to_korean(error_msg)
            error_code = result.get('errorCode', '')
            print(f"[{datetime.now()}] 결제 링크 생성 실패: [{error_code}] {translated_message}")
            return {
                'success': False,
                'message': f'결제 링크 생성에 실패했습니다: {translated_message}',
                'error_code': error_code
            }

    except Exception as e:
        print(f"[{datetime.now()}] 결제 링크 생성 중 예외 발생: {str(e)}")
        return {
            'success': False,
            'message': f'결제 링크 생성 중 오류 발생: {str(e)}'
        }


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
        valid_orders = db.query(OrderShipmentDtl).filter(
            and_(
                OrderShipmentDtl.purchase_order_number.in_(order_numbers),
                OrderShipmentDtl.del_yn == 0
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

        # 3. OrderShipmentDtl 업데이트 (결제 링크 저장)
        # 주의: OrderShipmentDtl 모델에 pay_link_1688 컬럼이 있다고 가정
        updated_count = db.query(OrderShipmentDtl).filter(
            and_(
                OrderShipmentDtl.purchase_order_number.in_(valid_order_numbers),
                OrderShipmentDtl.del_yn == 0
            )
        ).update({
            'pay_link_1688': pay_url,  # 컬럼명은 실제 스키마에 맞게 수정 필요
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
    수동으로 특정 주문들의 결제 링크 생성 (API 엔드포인트에서 호출용)

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


async def sync_1688_payment_links():
    """
    1688 결제 링크 동기화 스케줄러
    purchase_order_number는 있지만 purchase_pay_link가 없는 주문들의 결제 링크를 생성
    (매일 정기적으로 실행)
    """
    print(f"[{datetime.now()}] 1688 결제 링크 동기화 시작...")

    db = next(get_db())
    try:
        # 1. purchase_order_number는 있지만 purchase_pay_link가 없는 주문 조회
        missing_payment_links = db.query(
            distinct(purchase_models.OrderShipmentEstimateProduct.purchase_order_number)
        ).filter(
            and_(
                purchase_models.OrderShipmentEstimateProduct.purchase_order_number.isnot(None),
                purchase_models.OrderShipmentEstimateProduct.purchase_order_number != '',
                purchase_models.OrderShipmentEstimateProduct.purchase_pay_link.is_(None),
                purchase_models.OrderShipmentEstimateProduct.del_yn == 0
            )
        ).all()

        # 튜플 리스트를 문자열 리스트로 변환
        order_numbers = [order[0] for order in missing_payment_links]

        if not order_numbers:
            print(f"[{datetime.now()}] 결제 링크가 필요한 주문이 없습니다.")
            return

        print(f"[{datetime.now()}] 결제 링크 생성 대상 주문 {len(order_numbers)}건 발견")

        success_count = 0
        fail_count = 0

        # 2. 주문번호를 그룹으로 묶어서 처리 (최대 20개씩)
        batch_size = 20
        for i in range(0, len(order_numbers), batch_size):
            batch = order_numbers[i:i + batch_size]

            try:
                # 2-1. 해당 주문번호들의 account_info_no_1688 조회 (첫 번째 주문 기준)
                account_no = db.query(purchase_models.OrderShipmentEstimate.account_info_no_1688).join(
                    purchase_models.OrderMst,
                    purchase_models.OrderShipmentEstimate.order_mst_no == purchase_models.OrderMst.order_mst_no
                ).join(
                    purchase_models.OrderShipmentMst,
                    purchase_models.OrderMst.order_mst_no == purchase_models.OrderShipmentMst.order_mst_no
                ).join(
                    purchase_models.OrderShipmentDtl,
                    purchase_models.OrderShipmentMst.order_shipment_mst_no == purchase_models.OrderShipmentDtl.order_shipment_mst_no
                ).filter(
                    and_(
                        purchase_models.OrderShipmentDtl.purchase_order_number == batch[0],
                        purchase_models.OrderShipmentDtl.del_yn == 0,
                        purchase_models.OrderShipmentEstimate.del_yn == 0
                    )
                ).first()

                account_info_no = account_no[0] if account_no else None

                # 3. 결제 링크 생성 API 호출
                payment_result = await create_payment_link_by_order_numbers(
                    order_numbers=batch,
                    account_no=account_info_no
                )

                if payment_result.get('success'):
                    pay_url = payment_result.get('pay_url')

                    # 4. OrderShipmentEstimateProduct 업데이트
                    updated_count = db.query(purchase_models.OrderShipmentEstimateProduct).filter(
                        and_(
                            purchase_models.OrderShipmentEstimateProduct.purchase_order_number.in_(batch),
                            purchase_models.OrderShipmentEstimateProduct.del_yn == 0
                        )
                    ).update({
                        'purchase_pay_link': pay_url,
                        'updated_at': datetime.now()
                    }, synchronize_session=False)

                    print(f"[{datetime.now()}] 배치 {i // batch_size + 1}: 결제 링크 업데이트 완료 ({updated_count}건)")
                    print(f"[{datetime.now()}] - 주문번호: {', '.join(batch)}")
                    print(f"[{datetime.now()}] - 결제 링크: {pay_url}")

                    success_count += len(batch)
                else:
                    error_msg = payment_result.get('message', 'Unknown error')
                    print(f"[{datetime.now()}] 배치 {i // batch_size + 1} 결제 링크 생성 실패: {error_msg}")
                    fail_count += len(batch)

            except Exception as e:
                print(f"[{datetime.now()}] 배치 {i // batch_size + 1} 처리 중 오류 발생: {str(e)}")
                fail_count += len(batch)
                continue

        # 5. 변경사항 커밋
        db.commit()
        print(f"[{datetime.now()}] 1688 결제 링크 동기화 완료")
        print(f"[{datetime.now()}] 성공: {success_count}건, 실패: {fail_count}건")

    except Exception as e:
        print(f"[{datetime.now()}] 1688 결제 링크 동기화 실패: {str(e)}")
        db.rollback()
    finally:
        db.close()