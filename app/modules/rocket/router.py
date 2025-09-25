from fastapi import APIRouter
from app.modules.auth import schemas


rocket_router = APIRouter()


# 로그인
@rocket_router.get("/estimate/refreshTokenTest")
def login(
):
    print("TEST")
    return None