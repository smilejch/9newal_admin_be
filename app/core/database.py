# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_CONFIG
from sqlalchemy.pool import QueuePool

# SQLite인 경우, connect_args={"check_same_thread": False} 필요
engine = create_engine(
    DATABASE_CONFIG.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_CONFIG.DATABASE_URL else {},
    poolclass=QueuePool,
    pool_size=10,  # 기본 연결 풀 크기
    max_overflow=20,  # 추가로 생성 가능한 연결 수
    pool_pre_ping=True,  # 쿼리 실행 전 연결 확인 (중요!)
    pool_recycle=3600,  # 1시간(3600초)마다 연결 재생성
    echo=False,  # True로 설정하면 SQL 로그 출력
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    FastAPI 의존성 주입용 DB 세션 함수
    엔드포인트에서 Depends(get_db)로 세션을 얻음
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
