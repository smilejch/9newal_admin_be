
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, DECIMAL, ForeignKey, func, Text
from app.core.database import Base


class ComCode(Base):
    __tablename__ = "COM_CODE"

    com_code = Column(String(32), primary_key=True, index=True)
    parent_com_code = Column(String(32), nullable=True)
    code_name = Column(String(128), nullable=False)
    sort_order = Column(Integer, nullable=True)
    keyword1 = Column(String(128), nullable=True)
    keyword2 = Column(String(128), nullable=True)
    keyword3 = Column(String(128), nullable=True)
    use_yn = Column(Boolean, nullable=False, default=True)
    del_yn = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class ComHsCode(Base):
    __tablename__ = "COM_HS_CODE"

    hs_code = Column(String(20), primary_key=True, comment='HS부호')
    apply_start_date = Column(Date, primary_key=True, comment='적용시작일자')
    apply_start_date = Column(Date, nullable=False, comment='적용시작일자')
    apply_end_date = Column(Date, nullable=True, comment='적용종료일자')
    item_name_kr = Column(String(1000), nullable=True, comment='한글품목명')
    item_name_en = Column(String(1000), nullable=True, comment='영문품목명')
    hs_content = Column(Text, nullable=True, comment='HS부호내용')
    ktsn_name = Column(String(255), nullable=True, comment='한국표준무역분류명')
    unit_price_qty = Column(DECIMAL(18, 4), nullable=True, comment='수량단위최대단가')
    unit_price_weight = Column(DECIMAL(18, 4), nullable=True, comment='중량단위최대단가')
    qty_unit_code = Column(String(20), nullable=True, comment='수량단위코드')
    weight_unit_code = Column(String(20), nullable=True, comment='중량단위코드')
    export_type_code = Column(String(20), nullable=True, comment='수출성질코드')
    import_type_code = Column(String(20), nullable=True, comment='수입성질코드')
    item_spec_name = Column(String(1000), nullable=True, comment='품목규격명')
    required_spec_name = Column(String(1000), nullable=True, comment='필수규격명')
    ref_spec_name = Column(String(1000), nullable=True, comment='참고규격명')
    spec_description = Column(Text, nullable=True, comment='규격설명')
    spec_detail = Column(Text, nullable=True, comment='규격사항내용')
    unified_type_code = Column(String(20), nullable=True, comment='성질통합분류코드')
    unified_type_name = Column(String(255), nullable=True, comment='성질통합분류코드명')

class ComAccountInfo1688(Base):
    __tablename__ = "COM_ACCOUNT_INFO_1688"

    # Primary key
    account_info_no_1688 = Column(Integer, primary_key=True, autoincrement=True,comment='1688 계정 정보 번호')

    # Account information
    login_id_1688 = Column(String(255),  nullable=True, default="", comment='1688 로그인 ID')
    base_url = Column(String(500),  nullable=True, default="", comment='API 기본 URL')
    app_key = Column(String(255),  nullable=True, default="", comment='앱 키')
    app_secret = Column(String(255),  nullable=True, default="", comment='앱 시크릿')
    access_token = Column(Text,  nullable=True, default="", comment='액세스 토큰')
    message = Column(Text,  nullable=True, default="", comment='메시지')

    # Address information
    address_id = Column(String(100),  nullable=True, default="", comment='주소 ID')
    full_name = Column(String(100),  nullable=True, default="", comment='전체 이름')
    mobile = Column(String(20),  nullable=True, default="", comment='휴대폰 번호')
    phone = Column(String(20),  nullable=True, default="", comment='전화번호')
    post_code = Column(String(20),  nullable=True, default="", comment='우편번호')
    city_text = Column(String(100),  nullable=True, default="", comment='도시명')
    province_text = Column(String(100),  nullable=True, default="", comment='성/도명')
    area_text = Column(String(100),  nullable=True, default="", comment='지역명')
    town_text = Column(String(100),  nullable=True, default="", comment='마을명')
    address = Column(Text,  nullable=True, default="", comment='주소')
    district_code = Column(String(50),  nullable=True, default="", comment='지구 코드')

    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)