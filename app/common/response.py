# common/response.py
# 공통 Resposne Return 값을 셋팅 해주는 response 빌더
from typing import TypeVar, Optional, Any, List
from fastapi import status
from app.common.schemas.response import ApiResponse, PageResponse, PageInfo
import inspect
import re

T = TypeVar('T')


class ResponseBuilder:
    """응답 생성 헬퍼 클래스"""

    DEFAULT_MESSAGES = {
        "GET": "데이터가 정상적으로 출력되었습니다",
        "POST": "데이터가 정상적으로 생성되었습니다",
        "PUT": "데이터가 정상적으로 수정되었습니다",
        "PATCH": "데이터가 정상적으로 수정되었습니다",
        "DELETE": "데이터가 정상적으로 삭제되었습니다"
    }

    @staticmethod
    def _detect_http_method() -> str:
        """스택 트레이스에서 HTTP 메서드 감지"""
        frame = inspect.currentframe()
        try:
            # 스택을 역순으로 탐색하여 라우터 함수 찾기
            while frame:
                frame = frame.f_back
                if frame:
                    # 파일 경로에서 router.py 파일 찾기
                    filename = frame.f_code.co_filename
                    function_name = frame.f_code.co_name

                    if 'router.py' in filename or 'routers' in filename:
                        # 함수명에서 HTTP 메서드 패턴 찾기
                        method = ResponseBuilder._extract_method_from_function(function_name)
                        if method:
                            return method

                        # 파일 내용에서 데코레이터 찾기 (더 정확한 방법)
                        method = ResponseBuilder._extract_method_from_decorator(filename, function_name)
                        if method:
                            return method

        except Exception:
            pass
        finally:
            del frame

        return "GET"  # 기본값

    @staticmethod
    def _extract_method_from_function(function_name: str) -> Optional[str]:
        """함수명에서 HTTP 메서드 추출"""
        function_name = function_name.lower()

        # 일반적인 함수명 패턴
        if function_name.startswith('get_') or 'list' in function_name or 'find' in function_name:
            return "GET"
        elif function_name.startswith('post_') or function_name.startswith('create_') or 'add' in function_name:
            return "POST"
        elif function_name.startswith('put_') or function_name.startswith('update_') or 'modify' in function_name:
            return "PUT"
        elif function_name.startswith('delete_') or function_name.startswith('remove_') or 'del' in function_name:
            return "DELETE"
        elif function_name.startswith('patch_'):
            return "PATCH"

        return None

    @staticmethod
    def _extract_method_from_decorator(filename: str, function_name: str) -> Optional[str]:
        """파일에서 데코레이터를 읽어 HTTP 메서드 추출"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()

            # 함수 위의 데코레이터 찾기
            pattern = rf'@\w+\.(?P<method>get|post|put|delete|patch)\([^)]*\)\s*(?:async\s+)?def\s+{function_name}'
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)

            if match:
                return match.group('method').upper()

        except Exception:
            pass

        return None

    @staticmethod
    def _get_default_message(message: Optional[str] = None) -> str:
        """HTTP 메서드에 따른 기본 메시지 반환"""
        if message is not None:
            return message

        method = ResponseBuilder._detect_http_method()
        return ResponseBuilder.DEFAULT_MESSAGES.get(method, "처리가 완료되었습니다")

    @staticmethod
    def error(
            message: str,
            code: int = status.HTTP_400_BAD_REQUEST,
            data: Optional[Any] = None
    ) -> ApiResponse[None]:
        """에러 응답"""
        return ApiResponse(
            code=code,
            message=message,
            data=data
        )

    @staticmethod
    def success(
            data: Optional[T] = None,
            message: Optional[str] = None,
            code: int = status.HTTP_200_OK
    ) -> ApiResponse[T]:
        """성공 응답"""
        return ApiResponse(
            code=code,
            message=ResponseBuilder._get_default_message(message),
            data=data
        )

    @staticmethod
    def paged_success(
            content: List[T],
            page: int,
            size: int,
            total_elements: int,
            message: Optional[str] = None
    ) -> ApiResponse[PageResponse[T]]:
        """페이징 성공 응답"""
        total_pages = (total_elements + size - 1) // size if size > 0 else 0

        page_info = PageInfo(
            page=page,
            size=size,
            total_elements=total_elements,
            total_pages=total_pages,
            has_next=page < total_pages - 1,
            has_previous=page > 0
        )

        page_response = PageResponse(
            content=content,
            page_info=page_info
        )

        return ApiResponse(
            code=status.HTTP_200_OK,
            message=ResponseBuilder._get_default_message(message),
            data=page_response
        )