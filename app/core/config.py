# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드

class DATABASE_CONFIG:
    # .env 파일에서 데이터베이스 관련 정보 불러오기
    DATABASE_USER = os.getenv("DATABASE_USER", "default_user")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "default_password")
    DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT = os.getenv("DATABASE_PORT", "3306")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "default_dbname")

    # MySQL 연결 문자열 예시 (pymysql 사용)
    DATABASE_URL = (
        f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASSWORD}@"
        f"{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    )

class TOKEN_CONFIG:
    # 기타 보안 관련 설정값 불러오기
    ACCESS_TOKEN_SECRET_KEY = os.getenv("ACCESS_TOKEN_SECRET_KEY", "your-secret-key")
    REFRESH_TOKEN_SECRET_KEY = os.getenv("REFRESH_TOKEN_SECRET_KEY", "your-secret-key")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 1
    REFRESH_TOKEN_EXPIRE_DAYS = 7

class CRYPTO_CONFIG:
    AES_KEY = os.getenv("AES_KEY", "")

class GMAIL_CONFIG:
    GMAIL_ID = os.getenv("GMAIL_ID", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))         # Gmail STARTTLS
    SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
    MAIL_FROM = os.getenv("MAIL_FROM", GMAIL_ID or "")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Mailer")
    MAIL_TIMEOUT = int(os.getenv("MAIL_TIMEOUT", "30"))
    MAIL_RETRY = int(os.getenv("MAIL_RETRY", "2"))