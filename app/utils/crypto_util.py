from app.core.config import CRYPTO_CONFIG
from cryptography.fernet import Fernet


def encrypt(data: str) -> str:
    """데이터를 암호화합니다."""
    AES_KEY = CRYPTO_CONFIG.AES_KEY

    if not data:
        return ""

    cipher_suite = Fernet(AES_KEY)

    encrypted_data = cipher_suite.encrypt(data.encode('utf-8'))
    return encrypted_data.decode('utf-8')


def decrypt(encrypted_data: str) -> str:
    """데이터를 복호화합니다."""
    AES_KEY = CRYPTO_CONFIG.AES_KEY

    if not encrypted_data:
        return ""

    try:
        cipher_suite = Fernet(AES_KEY)

        decrypted_data = cipher_suite.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_data.decode('utf-8')
    except Exception as e:
        raise ValueError(f"복호화 실패: {str(e)}")