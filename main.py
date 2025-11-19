# app/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.dependencies import get_current_user_global
from app.core.database import Base, engine, get_db
from app.core.config_1688 import ALIBABA_1688_API_CONFIG
from app.modules.auth.router import auth_router
from app.modules.dashboard.router import dashboard_router
from app.modules.setting.router import setting_router
from app.modules.common.router import common_router
from app.modules.purchase.router import purchase_router
from app.core.exceptions import setup_global_exception_handlers
from app.scheduler import scheduler_1688
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from contextlib import asynccontextmanager
import platform
import os

# 스케줄러 인스턴스 생성
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application starting...")

    db = next(get_db())
    try:
        ALIBABA_1688_API_CONFIG.load_all_configs(db)
        print("✅ 1688 API config loaded")
    finally:
        db.close()

    # 스케줄러 작업 등록
    scheduler.add_job(
        func=scheduler_1688.sync_1688_order_status, # 1688 구매 상태 배치
        #trigger=CronTrigger(hour=0, minute=22, second=30), # 매일 자정 0시 0분 0초
        trigger=IntervalTrigger(minutes=1),  # N초마다 실행
        id='sync_1688_orders',
        name='1688 주문 동기화'
    )

    scheduler.start()
    print("APScheduler started")

    yield

    print("Application shutting down...")
    scheduler.shutdown()


def create_app():
    app = FastAPI(
        title="ADMIN 9newall Backend API",
        dependencies=[Depends(get_current_user_global)],  # 조건부 글로벌 적용
        lifespan=lifespan
    )

    setup_global_exception_handlers(app)

    # ✅ 올바른 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8080",  # 프론트엔드 주소
            "http://localhost:3000",  # React 기본 포트
            "http://127.0.0.1:8080",
            "http://127.0.0.1:3000",
            "https://9newall.com"
        ],
        allow_credentials=True,  # HttpOnly 쿠키를 위해 필수
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # DB 테이블 생성
    Base.metadata.create_all(bind=engine)

    # OS에 따른 정적 파일 경로 설정
    current_os = platform.system().lower()
    if current_os in ['darwin', 'windows']:  # 로컬 개발환경
        static_directory = "./uploads"
        mount_path = "/static"
    else:  # Linux 서버환경
        static_directory = "/var/www/uploads"
        mount_path = "/uploads"

    # 정적 파일 디렉토리가 존재하지 않으면 생성
    os.makedirs(static_directory, exist_ok=True)

    # 정적 파일 마운트
    app.mount(mount_path, StaticFiles(directory=static_directory), name="static")

    # 기존 라우터들...
    app.include_router(setting_router, prefix="/api/settings", tags=["settings"])

    # 라우터 등록
    # -> /auth/register, /auth/login 등으로 접근 가능
    app.include_router(auth_router, prefix="/auth", tags=["Auth"])
    app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
    app.include_router(setting_router, prefix="/setting", tags=["setting"])
    app.include_router(common_router, prefix="/common", tags=["common"])
    app.include_router(purchase_router, prefix="/purchase", tags=["purchase"])

    return app


app = create_app()
