# common/schemas/response.py
#
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel, Field

DataType = TypeVar('DataType')


class ApiResponse(BaseModel, Generic[DataType]):
    """표준 API 응답 형식"""
    code: int = Field(description="응답 코드")
    message: str = Field(description="응답 메시지")
    data: Optional[DataType] = Field(default=None, description="응답 데이터")

    @classmethod
    def error(cls, code: int, message: str):
        return cls(code=code, message=message, data=None)


class PageInfo(BaseModel):
    """페이징 정보"""
    page: int = Field(description="현재 페이지")
    size: int = Field(description="페이지 크기")
    total_elements: int = Field(description="전체 요소 수")
    total_pages: int = Field(description="전체 페이지 수")
    has_next: bool = Field(description="다음 페이지 존재 여부")
    has_previous: bool = Field(description="이전 페이지 존재 여부")


class PageResponse(BaseModel, Generic[DataType]):
    """페이징 응답 데이터"""
    content: list[DataType] = Field(description="데이터 목록")
    page_info: PageInfo = Field(description="페이징 정보")
