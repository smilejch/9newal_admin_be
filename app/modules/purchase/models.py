from sqlalchemy import Column, Integer, String, DECIMAL, CHAR, DateTime, func, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, DECIMAL, ForeignKey, func
from app.core.database import Base

Base = declarative_base()

class OrderMst(Base):
    __tablename__ = "ORDER_MST"

    order_mst_no = Column(Integer, primary_key=True, index=True)
    company_no = Column(Integer, nullable=False)
    order_date = Column(String(10), nullable=False)
    order_memo = Column(String(500), nullable=False)
    order_mst_status_cd = Column(String(10), nullable=False, default='REQUEST')
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    del_yn = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_by = Column(Integer)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class OrderDtl(Base):
    __tablename__ = "ORDER_DTL"

    order_dtl_no = Column(Integer, primary_key=True, index=True)
    order_mst_no = Column(Integer,  nullable=False)
    company_no = Column(Integer, nullable=False)

    order_number = Column(String(50), nullable=True)
    order_type = Column(String(50), nullable=True)
    order_status = Column(String(50), nullable=True)
    sku_id = Column(String(50), nullable=True)
    sku_name = Column(String(500), nullable=True)
    sku_barcode = Column(String(100), nullable=True)
    warehouse = Column(String(100), nullable=True)
    expected_receipt_date = Column(Date, nullable=True)
    order_date = Column(Date, nullable=True)
    order_quantity = Column(Integer, nullable=True)
    confirmed_quantity = Column(Integer, nullable=True)
    received_quantity = Column(Integer, nullable=True)
    purchase_type = Column(String(50), nullable=True)
    tax_exempt = Column(String(50), default=False, nullable=True)
    production_year = Column(String(4), nullable=True)
    manufacture_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    purchase_price = Column(DECIMAL(12, 2), nullable=True)
    supply_price = Column(DECIMAL(12, 2), nullable=True)
    tax_amount = Column(DECIMAL(12, 2), nullable=True)
    total_order_purchase_amount = Column(DECIMAL(14, 2), nullable=True)
    receipt_amount = Column(DECIMAL(14, 2), nullable=True)
    xdock = Column(String(50), default=False, nullable=True)
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    del_yn = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class OrderPurchase(Base):
    __tablename__ = "ORDER_PURCHASE"

    order_purchase_no = Column(Integer, primary_key=True, autoincrement=True, comment="로켓 주문 구매 번호 (자동증가)")
    order_mst_no = Column(Integer, nullable=False, comment="로켓 주문 mst 번호")
    order_dtl_no = Column(Integer, nullable=False, comment="로켓 주문 상세 번호")
    company_no = Column(Integer, comment="회사 인덱스 (PK)")
    order_number = Column(String(100), nullable=False, comment="주문 번호")
    sku_name = Column(String(500), comment="상품명")
    sku_id = Column(String(50), nullable=False, comment="SKU ID")
    sku_barcode = Column(String(100), nullable=True)
    bundle = Column(String(10), comment="묶음")
    confirmed_quantity = Column(Integer, nullable=True)
    multiple_value = Column(Integer, default=1, comment="판매 구성 수량")
    order_quantity = Column(Integer, nullable=True)
    purchase_quantity = Column(Integer, comment="구매 수량")
    purchase_order_number = Column(String(100), comment="1688 구매 번호")
    purchase_tracking_number = Column(String(100), comment="1688 운송장 번호")
    purchase_payment_link = Column(String(100), comment="1688 구매 링크")
    purchase_status_cd = Column(String(100), default="PENDING", nullable=False, comment="구매 진행 상태")
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    del_yn = Column(Integer, default=0, comment="삭제여부 (0: 미삭제, 1: 삭제)")
    created_at = Column(DateTime, server_default=func.now(), comment="생성일시")
    created_by = Column(Integer, comment="생성자")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="수정일시")
    updated_by = Column(Integer, comment="수정자")


class OrderShipmentMst(Base):
   __tablename__ = 'ORDER_SHIPMENT_MST'

   order_shipment_mst_no = Column(Integer, primary_key=True, autoincrement=True, comment='쉽먼트마스터')
   order_mst_no = Column(Integer, nullable=False, comment='발주마스터번호')
   company_no = Column(Integer, nullable=False)
   inbound_id = Column(String(200), nullable=False, comment='입고처리 ID(그로스용)')
   inbound_no = Column(String(50), nullable=False, comment='쿠팡에서 발급 된 입고 NO(그로스용)')
   display_center_name = Column(String(50), nullable=False, comment='센터이름')
   center_no = Column(String(20), nullable=False, comment='센터번호')
   edd = Column(String(8), nullable=True, comment='입고예정일')
   order_shipment_mst_status_cd = Column(String(10), nullable=False, comment='상태')
   estimated_yn = Column(Integer, nullable=False, default=0, comment='견적생성 여부(0: 미생성, 1:생성)')
   platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
   del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
   created_by = Column(Integer, nullable=False, comment='생성자ID')
   created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
   updated_by = Column(Integer, nullable=True, comment='수정자ID')
   updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')


class OrderShipmentDtl(Base):
    __tablename__ = "ORDER_SHIPMENT_DTL"

    order_shipment_dtl_no = Column(Integer, primary_key=True, autoincrement=True, comment='쉽먼트상세번호')
    order_shipment_mst_no = Column(Integer, nullable=False, comment='쉽먼트마스터번호')
    order_shipment_packing_mst_no = Column(Integer, nullable=True, comment='포장 박스 No')
    company_no = Column(Integer, nullable=True, comment='회사 no')
    order_number = Column(String(50), nullable=True, comment='발주번호')
    transport_type = Column(String(20), nullable=True, comment='입고유형')
    sku_id = Column(String(50), nullable=False, comment='SKU ID')
    sku_barcode = Column(String(100), nullable=True, comment='SKU 바코드')
    sku_name = Column(String(200), nullable=False, comment='SKU명')
    confirmed_quantity = Column(Integer, nullable=False, default=0, comment='확정수량')
    shipped_quantity = Column(Integer, nullable=False, default=0, comment='납품수량')
    link = Column(String(1000), nullable=True, comment='1688 링크')
    option_type = Column(String(10), nullable=True, comment='수동/자동 옵션 타입(MANUAL/AUTO)')
    option_value = Column(String(200), nullable=True, comment='옵션텍스트')
    linked_option = Column(String(200), nullable=True, comment='연동옵션텍스트')
    linked_spec_id = Column(String(100), nullable=True, comment='연동 spec_id')
    linked_sku_id = Column(String(30), nullable=True, comment='연동 sku_id')
    linked_open_uid = Column(String(25), nullable=True, comment='연동 open_uid')
    multiple_value = Column(Integer, nullable=True, comment='판매 구성 수량')
    length_mm = Column(DECIMAL(10, 2), nullable=True, comment='길이(mm)')
    width_mm = Column(DECIMAL(10, 2), nullable=True, comment='넓이(mm)')
    height_mm = Column(DECIMAL(10, 2), nullable=True, comment='높이(mm)')
    weight_g = Column(DECIMAL(10, 2), nullable=True, comment='중량(g)')
    purchase_order_number = Column(String(100), comment="1688 구매 번호")
    purchase_tracking_number = Column(String(100), comment="1688 운송장 번호")
    inspected_quantity = Column(Integer, nullable=True, comment='검수수량')
    virtual_packed_yn = Column(Integer, default=0, nullable=True, comment='가상 포장 여부 , 포장완료 1, 포장미완료 0')
    package_vinyl_spec_cd = Column(String(6), comment="포장비닐 규격")
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    coupang_option_name = Column(String(50), comment="쿠팡 옵션명(그로스용)")
    coupang_product_id = Column(String(50), comment="쿠팡 등록상품 ID(그로스용)")
    coupang_option_id = Column(String(50), comment="쿠팡 옵션 ID(그로스용)")
    delivery_status = Column(String(50), comment="배송상태(1688 -> CJ -> 물류센터)")
    del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
    created_by = Column(Integer, nullable=False, comment='생성자ID')
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
    updated_by = Column(Integer, nullable=True, comment='수정자ID')
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')


class OrderShipmentPackingMst(Base):
    __tablename__ = "ORDER_SHIPMENT_PACKING_MST"

    order_shipment_packing_mst_no = Column(Integer, primary_key=True, autoincrement=True, comment='Packing MST No')
    order_shipment_mst_no = Column(Integer, nullable=False, comment='쉽먼트마스터번호')
    company_no = Column(Integer, comment='회사 no')
    box_name = Column(String(50), comment='박스 명칭(center-박스총갯수-N번째박스-박스사이즈(S/M/L))')
    package_box_spec_cd = Column(String(10), comment='박스 사이즈')
    tracking_number = Column(String(100), nullable=True, comment='CJ 송장번호')
    del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    created_by = Column(Integer, nullable=False, comment='생성자ID')
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
    updated_by = Column(Integer, nullable=True, comment='수정자ID')
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')


class OrderShipmentPackingDtl(Base):
    __tablename__ = "ORDER_SHIPMENT_PACKING_DTL"

    order_shipment_packing_dtl_no = Column(Integer, primary_key=True, autoincrement=True, comment='포장 상세 번호')
    order_shipment_packing_mst_no = Column(Integer, nullable=False, comment='포장 번호')
    order_shipment_dtl_no = Column(Integer, nullable=False, comment='쉽먼트 DTL')
    company_no = Column(Integer, comment='회사 no')
    order_number = Column(String(50), nullable=True, comment='발주번호')
    sku_id = Column(String(50), nullable=False, comment='SKU ID')
    sku_name = Column(String(200), nullable=False, comment='SKU명')
    packing_quantity = Column(Integer, nullable=False, default=0, comment='포장 수량')
    length_mm = Column(DECIMAL(10, 2), nullable=True, comment='길이(mm)')
    width_mm = Column(DECIMAL(10, 2), nullable=True, comment='넓이(mm)')
    height_mm = Column(DECIMAL(10, 2), nullable=True, comment='높이(mm)')
    weight_g = Column(DECIMAL(10, 2), nullable=True, comment='중량(g)')
    box_name = Column(String(50), comment='박스 명칭(center-박스총갯수-N번째박스-박스사이즈(S/M/L))')
    tracking_number = Column(String(100), nullable=True, comment='CJ 송장번호')
    actual_packed_yn = Column(Integer, default=0, nullable=True, comment='실제 포장 여부, 포장완료 1, 포장미완료 0')
    shipping_status_cd = Column(String(20), comment='1688 ~ CJ 배송상태')
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
    created_by = Column(Integer, nullable=False, comment='생성자ID')
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')
    updated_by = Column(Integer, nullable=True, comment='수정자ID')

class OrderShipmentEstimate(Base):
    __tablename__ = "ORDER_SHIPMENT_ESTIMATE"

    order_shipment_estimate_no = Column(Integer, primary_key=True, autoincrement=True, comment='견적서 번호')
    order_mst_no = Column(Integer, comment="발주서 번호")
    company_no = Column(Integer, nullable=False, comment='회사 번호')
    estimate_id = Column(String(100), nullable=False, comment='견적서 ID')
    estimate_date = Column(String(10), nullable=False, comment='견적일자')
    product_total_amount = Column(DECIMAL(14, 2), nullable=True, default=0.00, comment='제품 총액')
    vinyl_total_amount = Column(DECIMAL(14, 2), nullable=True, default=0.00, comment='포장비닐 총액')
    box_total_amount = Column(DECIMAL(14, 2), nullable=True, default=0.00, comment='박스 총액')
    estimate_total_amount = Column(DECIMAL(14, 2), nullable=False, default=0.00, comment='견적 총 금액')
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    deposit_yn = Column(Integer, nullable=False, default=0, comment='입금확인여부(0:미확인, 1:확인)')
    completed_yn = Column(Integer, nullable=False, default=0, comment='견적 완료 여부 (0 : 미완료, 1: 완료)')
    account_info_no_1688 = Column(Integer, comment='1688 계정 정보 번호')
    del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
    created_by = Column(Integer, nullable=False, comment='생성자ID')
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')
    updated_by = Column(Integer, nullable=True, comment='수정자ID')


class OrderShipmentEstimateProduct(Base):
    __tablename__ = "ORDER_SHIPMENT_ESTIMATE_PRODUCT"

    order_shipment_estimate_product_no = Column(Integer, primary_key=True, autoincrement=True, comment='견적서 제품 번호')
    order_shipment_estimate_no = Column(Integer, nullable=False, comment='견적서 번호')
    order_shipment_mst_no = Column(Integer, nullable=True, comment='쉽먼트 Mst no')
    order_shipment_dtl_no = Column(Integer, nullable=True, comment='쉽먼트 Dtl No')
    company_no = Column(Integer, nullable=False, comment='회사 번호')
    center_no = Column(String(20), nullable=False, comment='센터번호')
    sku_id = Column(String(50), nullable=False, comment='SKU ID')
    sku_name = Column(String(200), nullable=False, comment='SKU명')
    bundle = Column(String(10), comment='묶음')
    purchase_quantity = Column(Integer, nullable=False, default=0, comment='구매 수량')
    product_unit_price = Column(DECIMAL(12, 2), nullable=False, default=0.00, comment='제품 단가')
    product_total_amount = Column(DECIMAL(14, 2), nullable=False, default=0.00, comment='제품 총 금액')
    package_vinyl_spec_cd = Column(String(6), nullable=True, comment='포장비닐 규격')
    package_vinyl_spec_total_amount = Column(DECIMAL(14, 2), nullable=False, default=0.00, comment='포장비닐 총 금액')
    package_vinyl_spec_unit_price = Column(DECIMAL(12, 2), nullable=False, default=0.00, comment='포장비닐 단가')
    fail_yn = Column(Integer, nullable=False, default=0, comment='가구매 견적 실패 여부 (0: 성공, 1: 실패)')
    total_amount = Column(DECIMAL(14, 2), nullable=False, default=0.00, comment='총 금액')
    purchase_order_number = Column(String(100), comment="1688 구매 번호")
    purchase_tracking_number = Column(String(100), comment="1688 운송장 번호")
    remark = Column(String(500), nullable=True, comment='비고')
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
    created_by = Column(Integer, nullable=False, comment='생성자ID')
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')
    updated_by = Column(Integer, nullable=True, comment='수정자ID')


class OrderShipmentEstimateBox(Base):
    __tablename__ = "ORDER_SHIPMENT_ESTIMATE_BOX"

    order_shipment_estimate_box_no = Column(Integer, primary_key=True, autoincrement=True, comment='견적서 박스 번호')
    order_shipment_estimate_no = Column(Integer, nullable=False, comment='견적서 번호')
    company_no = Column(Integer, nullable=False, comment='회사 번호')
    center_no = Column(String(20), nullable=False, comment='센터번호')
    package_box_spec_cd = Column(String(10), nullable=False, comment='박스 사이즈')
    package_box_spec_unit_price = Column(DECIMAL(12, 2), nullable=False, default=0.00, comment='박스 단가')
    box_quantity = Column(Integer, nullable=False, default=0, comment='박스 개수')
    total_amount = Column(DECIMAL(14, 2), nullable=False, default=0.00, comment='총 금액')
    platform_type_cd = Column(String(50), comment="플랫폼 구분(ROCKET : 로켓, GROWTH : 그로스)")
    del_yn = Column(Integer, nullable=False, default=0, comment='삭제여부(0:미삭제, 1:삭제)')
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='생성일시')
    created_by = Column(Integer, nullable=False, comment='생성자ID')
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now(), comment='수정일시')
    updated_by = Column(Integer, nullable=True, comment='수정자ID')

