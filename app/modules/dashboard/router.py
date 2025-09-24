# app/modules/auth/router.py
import time
from app.common.response import ApiResponse, ResponseBuilder

from fastapi import APIRouter
dashboard_router = APIRouter()


@dashboard_router.get("/dataList")
def get_data_list() -> ApiResponse[str]:
    time.sleep(3)
    return ResponseBuilder.success(data="test")
