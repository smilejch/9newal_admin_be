# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_CONFIG

# SQLite인 경우, connect_args={"check_same_thread": False} 필요
engine = create_engine(
    DATABASE_CONFIG.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_CONFIG.DATABASE_URL else {}
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
