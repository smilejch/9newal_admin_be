# app/core/exceptions.py
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from app.common import response

logger = logging.getLogger(__name__)


class AuthException(StarletteHTTPException):
    """
    인증 전용 예외 (상태코드 401)
    필요하면 서비스에서 `raise AuthException(detail="...")` 사용
    """
    def __init__(self, detail: str = "인증에 실패했습니다"):
        super().__init__(status_code=401, detail=detail)


def setup_global_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        HTTPException (401, 404, 400 등) 처리
        ApiResponse 형식으로 반환
        """
        # exc.detail이 dict / list / str 모두 가능하니 문자열로 안전하게 변환
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

        logger.error(f"HTTP exception on {request.url}: {exc.status_code} - {detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content=response.ApiResponse.error(code=exc.status_code, message=detail).dict()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Pydantic 입력 검증 실패 처리 (422)
        - 첫번째 오류 메시지를 뽑아서 사용자에게 전달
        """
        logger.error(f"Validation error on {request.url}: {exc.errors()}")
        errors = exc.errors()
        message = "입력 데이터가 올바르지 않습니다"
        if errors:
            # 좀 더 읽기 쉬운 메시지 추출
            try:
                first = errors[0]
                loc = ".".join([str(p) for p in first.get("loc", [])])
                msg = first.get("msg", "")
                message = f"{loc}: {msg}" if loc else msg
            except Exception:
                message = "입력 데이터가 올바르지 않습니다"

        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.ApiResponse.error(code=422, message=message).dict()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """
        처리되지 않은 모든 예외(500) 처리
        - 운영 환경에서는 exc 메시지를 그대로 클라이언트에 노출하지 않는 것을 권장
        """
        logger.exception(f"Unhandled exception on {request.url}: {exc}")
        # 운영에서는 message를 일반화. 디버깅 시엔 상세 메시지를 포함하도록 환경변수로 제어 가능
        return JSONResponse(
            status_code=500,
            content=response.ApiResponse.error(code=500, message="서버 내부 오류가 발생했습니다").dict()
        )