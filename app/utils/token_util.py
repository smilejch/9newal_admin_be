# utils/token_util.py
from sqlalchemy.orm import Session
from app.modules.auth import models
import logging

logger = logging.getLogger(__name__)


def delete_refresh_token_from_db(db: Session, refresh_token: str) -> bool:
    """DB에서 리프레시 토큰 삭제"""
    try:
        deleted_count = (
            db.query(models.ComUserTokenAuth)
            .filter(models.ComUserTokenAuth.refresh_token == refresh_token)
            .delete()
        )
        db.commit()

        if deleted_count > 0:
            logger.info(f"Deleted refresh token from database: {refresh_token[:10]}...")
            return True
        else:
            logger.warning("No refresh token found to delete")
            return False

    except Exception as e:
        logger.error(f"Error deleting token: {e}")
        db.rollback()
        return False