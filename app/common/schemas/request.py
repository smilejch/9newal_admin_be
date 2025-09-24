from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SortOrder(str, Enum):
    """정렬 순서"""
    ASC = "asc"
    DESC = "desc"


class PaginationRequest(BaseModel):
    """페이징 요청 스키마"""
    page: int = Field(default=1, ge=1, description="페이지 번호 (1부터 시작)")
    size: int = Field(default=10, ge=1, le=20000, description="페이지당 항목 수 (최대 100)")
    order_by: Optional[str] = Field(default="created_at", description="정렬 기준 필드")
    sort_by: SortOrder = Field(default=SortOrder.DESC, description="정렬 순서")

    class Config:
        use_enum_values = True