import random
import hmac
import hashlib
import time

class ALIBABA_1688_API_CONFIG:
    _all_configs = {}

    @classmethod
    def load_all_configs(cls, db_session):
        """모든 1688 계정 설정을 메모리에 로드"""
        from app.modules.common.models import ComAccountInfo1688

        accounts = db_session.query(ComAccountInfo1688).all()

        cls._all_configs = {}
        for account in accounts:
            cls._all_configs[account.account_info_no_1688] = {
                'app_key': account.app_key or '',
                'app_secret': account.app_secret or '',
                'access_token': account.access_token or '',
                'base_url': account.base_url or '',
                'login_id': account.login_id_1688 or '',
                'message': account.message or '',
                'address_id': account.address_id or '',
                'full_name': account.full_name or '',
                'mobile': account.mobile or '',
                'phone': account.phone or '',
                'post_code': account.post_code or '',
                'city_text': account.city_text or '',
                'province_text': account.province_text or '',
                'area_text': account.area_text or '',
                'town_text': account.town_text or '',
                'address': account.address or '',
                'district_code': account.district_code or '',
            }

    @classmethod
    def _get_random_account_config(cls):
        """매번 랜덤 계정 선택"""
        if not cls._all_configs:
            raise ValueError("설정이 로드되지 않았습니다. load_all_configs()를 먼저 호출하세요.")

        account_no = random.choice(list(cls._all_configs.keys()))
        config = cls._all_configs[account_no].copy()
        config['account_no'] = account_no

        return config

    @classmethod
    def generate_signature(cls, url_path, params, config):

        param_pairs = []
        for key, value in sorted(params.items()):
            if key != '_aop_signature':
                param_pairs.append(f"{key}{value}")
        param_string = ''.join(param_pairs)

        string_to_sign = url_path + param_string

        hmac_obj = hmac.new(
            config['app_secret'].encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        )
        signature = hmac_obj.hexdigest().upper()

        print(f"사용된 계정: {config['account_no']} ({config['login_id']})")
        return signature

    @classmethod
    def get_headers(cls, content_type="application/x-www-form-urlencoded"):
        return {
            'Content-Type': content_type
        }

    @classmethod
    def get_timestamp(cls):
        return str(int(time.time() * 1000))