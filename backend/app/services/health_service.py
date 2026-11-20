import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.health_repository import DatabaseHealthRepository

logger = logging.getLogger(__name__)


def database_is_healthy(session: Session) -> bool:
    try:
        DatabaseHealthRepository.ping(session)
    except SQLAlchemyError:
        logger.warning("Database health check failed.")
        return False
    return True
