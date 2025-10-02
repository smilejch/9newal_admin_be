import aiosmtplib
from email.message import EmailMessage
import ssl
import certifi
import os
from typing import List


async def send_email(
        email_to: List[str],  # 이메일 주소 배열
        subject: str,  # 이메일 제목
        content: str  # 이메일 내용
):
    """
    이메일 발송 함수

    Args:
        email_to: 수신자 이메일 주소 리스트
        subject: 이메일 제목
        content: 이메일 본문
    """
    try:
        # 환경변수에서 이메일 설정 가져오기
        gmail_id = os.getenv('GMAIL_ID', '9newall@gmail.com')
        gmail_app_password = os.getenv('GMAIL_APP_PASSWORD', 'test1')
        mail_from = os.getenv('MAIL_FROM', '9newall@gmail.com')
        mail_from_name = os.getenv('MAIL_FROM_NAME', '9NEWALL')
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))

        # 이메일 메시지 생성
        msg = EmailMessage()
        msg["From"] = f"{mail_from_name} <{mail_from}>"
        msg["To"] = ", ".join(email_to)  # 여러 수신자를 콤마로 구분
        msg["Subject"] = subject
        msg.set_content(content)

        print(f"Sending email to: {', '.join(email_to)}")

        # SSL 컨텍스트 생성
        context = ssl.create_default_context(cafile=certifi.where())

        # 이메일 발송
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            start_tls=True,
            username=gmail_id,
            password=gmail_app_password,
            tls_context=context
        )

        print(f"Email sent successfully to: {', '.join(email_to)}")
        return True

    except Exception as e:
        print(f"Email send error: {e}")
        # 이메일 발송 실패해도 사용자 승인은 완료되도록 예외를 발생시키지 않음
        return False
